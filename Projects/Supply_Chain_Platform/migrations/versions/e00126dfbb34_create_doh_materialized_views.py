"""create_doh_materialized_views

Revision ID: e00126dfbb34
Revises: 52fa8d4129df
Create Date: 2026-02-03 20:20:05.173857

Creates materialized views for DOH (Days on Hand) metrics:
- mv_daily_metrics: Daily aggregates of shipments and depletions
- mv_doh_metrics: DOH_T30 and DOH_T90 calculations per SKU/warehouse

Since TimescaleDB is not available on Railway, we use standard PostgreSQL
materialized views instead of continuous aggregates. These views should be
refreshed on a schedule (e.g., every 15 minutes via Celery).
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "e00126dfbb34"
down_revision: str | Sequence[str] | None = "52fa8d4129df"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create materialized views for DOH metrics."""
    connection = op.get_bind()

    # Create mv_daily_metrics: Daily aggregates of shipments and depletions
    # This view aggregates inventory events by day, SKU, and warehouse
    connection.execute(
        text("""
            CREATE MATERIALIZED VIEW mv_daily_metrics AS
            SELECT
                DATE(time AT TIME ZONE 'UTC') AS day,
                sku_id,
                warehouse_id,
                SUM(CASE WHEN event_type = 'shipment' THEN quantity ELSE 0 END)
                    AS shipments,
                SUM(CASE WHEN event_type = 'depletion' THEN ABS(quantity) ELSE 0 END)
                    AS depletions,
                SUM(CASE WHEN event_type = 'adjustment' THEN quantity ELSE 0 END)
                    AS adjustments
            FROM inventory_events
            GROUP BY DATE(time AT TIME ZONE 'UTC'), sku_id, warehouse_id
            WITH NO DATA
        """)
    )

    # Create index on mv_daily_metrics for efficient lookups
    connection.execute(
        text("""
            CREATE UNIQUE INDEX idx_mv_daily_metrics_day_sku_wh
            ON mv_daily_metrics (day, sku_id, warehouse_id)
        """)
    )
    connection.execute(
        text("""
            CREATE INDEX idx_mv_daily_metrics_sku
            ON mv_daily_metrics (sku_id)
        """)
    )
    connection.execute(
        text("""
            CREATE INDEX idx_mv_daily_metrics_day
            ON mv_daily_metrics (day)
        """)
    )

    # Create mv_doh_metrics: DOH_T30 and DOH_T90 calculations
    # This view calculates Days on Hand metrics using trailing 30/90 day windows
    # DOH = current_inventory / (trailing_depletions / days)
    # Note: current_inventory is calculated as cumulative sum of all events
    connection.execute(
        text("""
            CREATE MATERIALIZED VIEW mv_doh_metrics AS
            WITH current_inventory AS (
                -- Calculate current inventory as sum of all events
                -- Shipments add, depletions subtract
                SELECT
                    sku_id,
                    warehouse_id,
                    SUM(
                        CASE
                            WHEN event_type = 'shipment' THEN quantity
                            WHEN event_type = 'depletion' THEN -ABS(quantity)
                            WHEN event_type = 'adjustment' THEN quantity
                            ELSE 0
                        END
                    ) AS on_hand
                FROM inventory_events
                GROUP BY sku_id, warehouse_id
            ),
            trailing_30d AS (
                -- Sum depletions and shipments over last 30 days
                SELECT
                    sku_id,
                    warehouse_id,
                    COALESCE(SUM(depletions), 0) AS depletions_30d,
                    COALESCE(SUM(shipments), 0) AS shipments_30d
                FROM mv_daily_metrics
                WHERE day > CURRENT_DATE - INTERVAL '30 days'
                GROUP BY sku_id, warehouse_id
            ),
            trailing_90d AS (
                -- Sum depletions and shipments over last 90 days
                SELECT
                    sku_id,
                    warehouse_id,
                    COALESCE(SUM(depletions), 0) AS depletions_90d,
                    COALESCE(SUM(shipments), 0) AS shipments_90d
                FROM mv_daily_metrics
                WHERE day > CURRENT_DATE - INTERVAL '90 days'
                GROUP BY sku_id, warehouse_id
            )
            SELECT
                ci.sku_id,
                ci.warehouse_id,
                ci.on_hand AS current_inventory,
                t30.depletions_30d,
                t30.shipments_30d,
                t90.depletions_90d,
                t90.shipments_90d,
                -- DOH_T30: Days on Hand based on 30-day depletion rate
                -- Handle zero depletion gracefully with NULLIF
                CASE
                    WHEN t30.depletions_30d > 0
                    THEN ROUND(
                        ci.on_hand::NUMERIC / (t30.depletions_30d::NUMERIC / 30),
                        1
                    )
                    ELSE NULL  -- NULL indicates infinite DOH (no depletion)
                END AS doh_t30,
                -- DOH_T90: Days on Hand based on 90-day depletion rate
                CASE
                    WHEN t90.depletions_90d > 0
                    THEN ROUND(
                        ci.on_hand::NUMERIC / (t90.depletions_90d::NUMERIC / 90),
                        1
                    )
                    ELSE NULL  -- NULL indicates infinite DOH (no depletion)
                END AS doh_t90,
                -- A30_Ship:A30_Dep ratio (shipments to depletions over 30 days)
                CASE
                    WHEN t30.depletions_30d > 0
                    THEN ROUND(
                        t30.shipments_30d::NUMERIC / t30.depletions_30d::NUMERIC,
                        2
                    )
                    ELSE NULL
                END AS a30_ship_dep_ratio,
                -- A90_Ship:A90_Dep ratio (shipments to depletions over 90 days)
                CASE
                    WHEN t90.depletions_90d > 0
                    THEN ROUND(
                        t90.shipments_90d::NUMERIC / t90.depletions_90d::NUMERIC,
                        2
                    )
                    ELSE NULL
                END AS a90_ship_dep_ratio,
                -- A30:A90_Dep velocity trend (>1 = accelerating, <1 = decelerating)
                CASE
                    WHEN t90.depletions_90d > 0
                    THEN ROUND(
                        (t30.depletions_30d::NUMERIC / 30) /
                        (t90.depletions_90d::NUMERIC / 90),
                        2
                    )
                    ELSE NULL
                END AS velocity_trend_dep,
                -- A30:A90_Ship velocity trend for shipments
                CASE
                    WHEN t90.shipments_90d > 0
                    THEN ROUND(
                        (t30.shipments_30d::NUMERIC / 30) /
                        (t90.shipments_90d::NUMERIC / 90),
                        2
                    )
                    ELSE NULL
                END AS velocity_trend_ship,
                CURRENT_TIMESTAMP AS calculated_at
            FROM current_inventory ci
            LEFT JOIN trailing_30d t30
                ON ci.sku_id = t30.sku_id AND ci.warehouse_id = t30.warehouse_id
            LEFT JOIN trailing_90d t90
                ON ci.sku_id = t90.sku_id AND ci.warehouse_id = t90.warehouse_id
            WITH NO DATA
        """)
    )

    # Create indexes on mv_doh_metrics
    connection.execute(
        text("""
            CREATE UNIQUE INDEX idx_mv_doh_metrics_sku_wh
            ON mv_doh_metrics (sku_id, warehouse_id)
        """)
    )
    connection.execute(
        text("""
            CREATE INDEX idx_mv_doh_metrics_sku
            ON mv_doh_metrics (sku_id)
        """)
    )

    # Create a function to refresh both materialized views in order
    # mv_daily_metrics must be refreshed before mv_doh_metrics
    connection.execute(
        text("""
            CREATE OR REPLACE FUNCTION refresh_doh_metrics()
            RETURNS void AS $$
            BEGIN
                -- Refresh daily metrics first (mv_doh_metrics depends on it)
                REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_metrics;
                -- Then refresh DOH metrics
                REFRESH MATERIALIZED VIEW CONCURRENTLY mv_doh_metrics;
            END;
            $$ LANGUAGE plpgsql
        """)
    )


def downgrade() -> None:
    """Drop materialized views and refresh function."""
    connection = op.get_bind()

    # Drop the refresh function
    connection.execute(text("DROP FUNCTION IF EXISTS refresh_doh_metrics()"))

    # Drop indexes and materialized views in reverse order
    connection.execute(text("DROP INDEX IF EXISTS idx_mv_doh_metrics_sku"))
    connection.execute(text("DROP INDEX IF EXISTS idx_mv_doh_metrics_sku_wh"))
    connection.execute(text("DROP MATERIALIZED VIEW IF EXISTS mv_doh_metrics"))

    connection.execute(text("DROP INDEX IF EXISTS idx_mv_daily_metrics_day"))
    connection.execute(text("DROP INDEX IF EXISTS idx_mv_daily_metrics_sku"))
    connection.execute(text("DROP INDEX IF EXISTS idx_mv_daily_metrics_day_sku_wh"))
    connection.execute(text("DROP MATERIALIZED VIEW IF EXISTS mv_daily_metrics"))
