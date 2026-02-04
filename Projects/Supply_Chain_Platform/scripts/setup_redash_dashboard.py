"""Setup Redash dashboard queries and visualizations.

This script creates the DOH overview dashboard queries in Redash
using the Redash API. It is idempotent - running multiple times
will update existing queries rather than creating duplicates.

Usage:
    poetry run python scripts/setup_redash_dashboard.py

Environment variables:
    REDASH_URL: Base URL of Redash instance
    REDASH_API_KEY: API key for Redash admin user
"""

import os
import sys
from typing import Any, cast

import httpx

# Redash instance URL (from Task 1.6.1)
DEFAULT_REDASH_URL = "https://redash-server-production-920f.up.railway.app"

# SQL query for DOH Overview
DOH_OVERVIEW_QUERY = """
-- DOH Overview: Days on Hand metrics for all SKUs
-- Shows current inventory, 30-day and 90-day DOH, plus status indicators
SELECT
    p.sku,
    p.name as product_name,
    w.name as warehouse,
    m.current_inventory as on_hand,
    m.depletions_30d,
    m.depletions_90d,
    m.doh_t30,
    m.doh_t90,
    CASE
        WHEN m.doh_t30 IS NULL THEN 'NO SALES'
        WHEN m.doh_t30 < 14 THEN 'CRITICAL'
        WHEN m.doh_t30 < 30 THEN 'WARNING'
        ELSE 'OK'
    END as status,
    m.calculated_at
FROM mv_doh_metrics m
JOIN products p ON m.sku_id = p.id
JOIN warehouses w ON m.warehouse_id = w.id
ORDER BY
    CASE
        WHEN m.doh_t30 IS NULL THEN 2
        WHEN m.doh_t30 < 14 THEN 0
        WHEN m.doh_t30 < 30 THEN 1
        ELSE 3
    END,
    m.doh_t30 ASC NULLS LAST;
"""

# SQL query for DOH by SKU (aggregated across warehouses)
DOH_BY_SKU_QUERY = """
-- DOH by SKU: Aggregated DOH metrics across all warehouses
SELECT
    p.sku,
    p.name as product_name,
    SUM(m.current_inventory) as total_on_hand,
    SUM(m.depletions_30d) as total_depletions_30d,
    SUM(m.depletions_90d) as total_depletions_90d,
    CASE
        WHEN SUM(m.depletions_30d) > 0
        THEN ROUND(SUM(m.current_inventory)::NUMERIC / (SUM(m.depletions_30d)::NUMERIC / 30), 1)
        ELSE NULL
    END as doh_t30,
    CASE
        WHEN SUM(m.depletions_90d) > 0
        THEN ROUND(SUM(m.current_inventory)::NUMERIC / (SUM(m.depletions_90d)::NUMERIC / 90), 1)
        ELSE NULL
    END as doh_t90,
    CASE
        WHEN SUM(m.depletions_30d) = 0 THEN 'NO SALES'
        WHEN SUM(m.current_inventory)::NUMERIC / (SUM(m.depletions_30d)::NUMERIC / 30) < 14 THEN 'CRITICAL'
        WHEN SUM(m.current_inventory)::NUMERIC / (SUM(m.depletions_30d)::NUMERIC / 30) < 30 THEN 'WARNING'
        ELSE 'OK'
    END as status
FROM mv_doh_metrics m
JOIN products p ON m.sku_id = p.id
GROUP BY p.sku, p.name
ORDER BY
    CASE
        WHEN SUM(m.depletions_30d) = 0 THEN 2
        WHEN SUM(m.current_inventory)::NUMERIC / (SUM(m.depletions_30d)::NUMERIC / 30) < 14 THEN 0
        WHEN SUM(m.current_inventory)::NUMERIC / (SUM(m.depletions_30d)::NUMERIC / 30) < 30 THEN 1
        ELSE 3
    END,
    doh_t30 ASC NULLS LAST;
"""

# SQL query for Shipment:Depletion Ratio
SHIP_DEP_RATIO_QUERY = """
-- Shipment:Depletion Ratio: Supply/demand balance metrics for all SKUs
-- Ratio > 1 means more shipments than depletions (building inventory)
-- Ratio < 1 means more depletions than shipments (drawing down inventory)
SELECT
    p.sku,
    p.name as product_name,
    w.name as warehouse,
    m.shipments_30d,
    m.depletions_30d,
    m.shipments_90d,
    m.depletions_90d,
    m.a30_ship_dep_ratio,
    m.a90_ship_dep_ratio,
    CASE
        WHEN m.a30_ship_dep_ratio IS NULL THEN 'NO SALES'
        WHEN m.a30_ship_dep_ratio > 2.0 THEN 'OVERSUPPLY'
        WHEN m.a30_ship_dep_ratio < 0.5 THEN 'UNDERSUPPLY'
        ELSE 'BALANCED'
    END as status_30d,
    CASE
        WHEN m.a90_ship_dep_ratio IS NULL THEN 'NO SALES'
        WHEN m.a90_ship_dep_ratio > 2.0 THEN 'OVERSUPPLY'
        WHEN m.a90_ship_dep_ratio < 0.5 THEN 'UNDERSUPPLY'
        ELSE 'BALANCED'
    END as status_90d,
    m.calculated_at
FROM mv_doh_metrics m
JOIN products p ON m.sku_id = p.id
JOIN warehouses w ON m.warehouse_id = w.id
ORDER BY
    CASE
        WHEN m.a30_ship_dep_ratio IS NULL THEN 2
        WHEN m.a30_ship_dep_ratio < 0.5 THEN 0
        WHEN m.a30_ship_dep_ratio > 2.0 THEN 1
        ELSE 3
    END,
    m.a30_ship_dep_ratio ASC NULLS LAST;
"""

# SQL query for Shipment:Depletion Ratio by SKU (aggregated)
SHIP_DEP_RATIO_BY_SKU_QUERY = """
-- Shipment:Depletion Ratio by SKU: Aggregated supply/demand balance
SELECT
    p.sku,
    p.name as product_name,
    SUM(m.shipments_30d) as total_shipments_30d,
    SUM(m.depletions_30d) as total_depletions_30d,
    SUM(m.shipments_90d) as total_shipments_90d,
    SUM(m.depletions_90d) as total_depletions_90d,
    CASE
        WHEN SUM(m.depletions_30d) > 0
        THEN ROUND(SUM(m.shipments_30d)::NUMERIC / SUM(m.depletions_30d)::NUMERIC, 2)
        ELSE NULL
    END as a30_ship_dep_ratio,
    CASE
        WHEN SUM(m.depletions_90d) > 0
        THEN ROUND(SUM(m.shipments_90d)::NUMERIC / SUM(m.depletions_90d)::NUMERIC, 2)
        ELSE NULL
    END as a90_ship_dep_ratio,
    CASE
        WHEN SUM(m.depletions_30d) = 0 THEN 'NO SALES'
        WHEN SUM(m.shipments_30d)::NUMERIC / SUM(m.depletions_30d)::NUMERIC > 2.0 THEN 'OVERSUPPLY'
        WHEN SUM(m.shipments_30d)::NUMERIC / SUM(m.depletions_30d)::NUMERIC < 0.5 THEN 'UNDERSUPPLY'
        ELSE 'BALANCED'
    END as status_30d,
    CASE
        WHEN SUM(m.depletions_90d) = 0 THEN 'NO SALES'
        WHEN SUM(m.shipments_90d)::NUMERIC / SUM(m.depletions_90d)::NUMERIC > 2.0 THEN 'OVERSUPPLY'
        WHEN SUM(m.shipments_90d)::NUMERIC / SUM(m.depletions_90d)::NUMERIC < 0.5 THEN 'UNDERSUPPLY'
        ELSE 'BALANCED'
    END as status_90d
FROM mv_doh_metrics m
JOIN products p ON m.sku_id = p.id
GROUP BY p.sku, p.name
ORDER BY
    CASE
        WHEN SUM(m.depletions_30d) = 0 THEN 2
        WHEN SUM(m.shipments_30d)::NUMERIC / SUM(m.depletions_30d)::NUMERIC < 0.5 THEN 0
        WHEN SUM(m.shipments_30d)::NUMERIC / SUM(m.depletions_30d)::NUMERIC > 2.0 THEN 1
        ELSE 3
    END,
    a30_ship_dep_ratio ASC NULLS LAST;
"""

# SQL query for Stock-Out Risk Alert (DOH_T30 < 14)
STOCKOUT_ALERT_QUERY = """
-- Stock-Out Risk Alert: Triggers when DOH_T30 < 14 days
-- Alert fires when any SKU has less than 14 days of inventory on hand
SELECT
    p.sku,
    p.name as product_name,
    w.name as warehouse,
    m.current_inventory as on_hand,
    m.depletions_30d,
    ROUND(m.doh_t30, 1) as doh_t30,
    14 as threshold_days,
    ROUND(14 - m.doh_t30, 1) as days_below_threshold,
    m.calculated_at
FROM mv_doh_metrics m
JOIN products p ON m.sku_id = p.id
JOIN warehouses w ON m.warehouse_id = w.id
WHERE
    m.doh_t30 IS NOT NULL
    AND m.doh_t30 < 14
ORDER BY
    m.doh_t30 ASC;
"""


class RedashClient:
    """Client for Redash API operations."""

    def __init__(self, base_url: str, api_key: str):
        """Initialize the Redash client.

        Args:
            base_url: Base URL of the Redash instance
            api_key: API key for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = {"Authorization": f"Key {api_key}"}

    def get_data_sources(self) -> list[dict[str, Any]]:
        """Get list of data sources.

        Returns:
            List of data source dictionaries
        """
        response = httpx.get(
            f"{self.base_url}/api/data_sources",
            headers=self.headers,
            timeout=30.0,
        )
        response.raise_for_status()
        return cast(list[dict[str, Any]], response.json())

    def get_queries(self) -> list[dict[str, Any]]:
        """Get list of queries.

        Returns:
            List of query dictionaries
        """
        response = httpx.get(
            f"{self.base_url}/api/queries",
            headers=self.headers,
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        return cast(list[dict[str, Any]], data.get("results", []))

    def create_query(
        self,
        name: str,
        query: str,
        data_source_id: int,
        description: str = "",
    ) -> dict[str, Any]:
        """Create a new query.

        Args:
            name: Query name
            query: SQL query text
            data_source_id: ID of the data source
            description: Optional query description

        Returns:
            Created query dictionary
        """
        response = httpx.post(
            f"{self.base_url}/api/queries",
            headers=self.headers,
            json={
                "name": name,
                "query": query,
                "data_source_id": data_source_id,
                "description": description,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    def update_query(
        self,
        query_id: int,
        name: str,
        query: str,
        description: str = "",
    ) -> dict[str, Any]:
        """Update an existing query.

        Args:
            query_id: ID of the query to update
            name: Query name
            query: SQL query text
            description: Optional query description

        Returns:
            Updated query dictionary
        """
        response = httpx.post(
            f"{self.base_url}/api/queries/{query_id}",
            headers=self.headers,
            json={
                "name": name,
                "query": query,
                "description": description,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    def execute_query(self, query_id: int) -> dict[str, Any]:
        """Execute a query and wait for results.

        Args:
            query_id: ID of the query to execute

        Returns:
            Query result dictionary
        """
        # Trigger execution
        response = httpx.post(
            f"{self.base_url}/api/queries/{query_id}/results",
            headers=self.headers,
            json={"max_age": 0},  # Force fresh execution
            timeout=60.0,
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    def get_dashboards(self) -> list[dict[str, Any]]:
        """Get list of dashboards.

        Returns:
            List of dashboard dictionaries
        """
        response = httpx.get(
            f"{self.base_url}/api/dashboards",
            headers=self.headers,
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        return cast(list[dict[str, Any]], data.get("results", []))

    def create_dashboard(self, name: str) -> dict[str, Any]:
        """Create a new dashboard.

        Args:
            name: Dashboard name

        Returns:
            Created dashboard dictionary
        """
        response = httpx.post(
            f"{self.base_url}/api/dashboards",
            headers=self.headers,
            json={"name": name},
            timeout=30.0,
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    def add_widget_to_dashboard(
        self,
        dashboard_id: int,
        visualization_id: int,
        options: dict[str, Any] | None = None,
        width: int = 3,
        text: str = "",
    ) -> dict[str, Any]:
        """Add a widget to a dashboard.

        Args:
            dashboard_id: ID of the dashboard
            visualization_id: ID of the visualization to add
            options: Widget options
            width: Widget width (1-6)
            text: Text content (for text widgets)

        Returns:
            Created widget dictionary
        """
        response = httpx.post(
            f"{self.base_url}/api/dashboards/{dashboard_id}/widgets",
            headers=self.headers,
            json={
                "visualization_id": visualization_id,
                "options": options or {},
                "width": width,
                "text": text,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    def create_visualization(
        self,
        query_id: int,
        name: str,
        vis_type: str,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a visualization for a query.

        Args:
            query_id: ID of the query
            name: Visualization name
            vis_type: Type of visualization (CHART, TABLE, COUNTER, etc.)
            options: Visualization options (chart type, columns, colors, etc.)

        Returns:
            Created visualization dictionary
        """
        response = httpx.post(
            f"{self.base_url}/api/visualizations",
            headers=self.headers,
            json={
                "query_id": query_id,
                "name": name,
                "type": vis_type,
                "options": options,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    def get_query(self, query_id: int) -> dict[str, Any]:
        """Get a query by ID.

        Args:
            query_id: ID of the query

        Returns:
            Query dictionary including visualizations
        """
        response = httpx.get(
            f"{self.base_url}/api/queries/{query_id}",
            headers=self.headers,
            timeout=30.0,
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    def publish_dashboard(self, dashboard_id: int) -> dict[str, Any]:
        """Publish a dashboard to make it visible.

        Args:
            dashboard_id: ID of the dashboard

        Returns:
            Updated dashboard dictionary
        """
        response = httpx.post(
            f"{self.base_url}/api/dashboards/{dashboard_id}",
            headers=self.headers,
            json={"is_draft": False},
            timeout=30.0,
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    def get_alerts(self) -> list[dict[str, Any]]:
        """Get list of alerts.

        Returns:
            List of alert dictionaries
        """
        response = httpx.get(
            f"{self.base_url}/api/alerts",
            headers=self.headers,
            timeout=30.0,
        )
        response.raise_for_status()
        return cast(list[dict[str, Any]], response.json())

    def get_alert(self, alert_id: int) -> dict[str, Any]:
        """Get an alert by ID.

        Args:
            alert_id: ID of the alert

        Returns:
            Alert dictionary
        """
        response = httpx.get(
            f"{self.base_url}/api/alerts/{alert_id}",
            headers=self.headers,
            timeout=30.0,
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    def create_alert(
        self,
        name: str,
        query_id: int,
        options: dict[str, Any],
        rearm: int | None = None,
    ) -> dict[str, Any]:
        """Create a new alert.

        Args:
            name: Alert name
            query_id: ID of the query to monitor
            options: Alert options including:
                - column: Column name to check
                - op: Comparison operator (greater than, less than, equals, etc.)
                - value: Threshold value
                - custom_subject: Custom email subject
                - custom_body: Custom alert message body
            rearm: Seconds before alert can fire again (None for one-time)

        Returns:
            Created alert dictionary
        """
        payload: dict[str, Any] = {
            "name": name,
            "query_id": query_id,
            "options": options,
        }
        if rearm is not None:
            payload["rearm"] = rearm

        response = httpx.post(
            f"{self.base_url}/api/alerts",
            headers=self.headers,
            json=payload,
            timeout=30.0,
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    def update_alert(
        self,
        alert_id: int,
        name: str | None = None,
        options: dict[str, Any] | None = None,
        rearm: int | None = None,
    ) -> dict[str, Any]:
        """Update an existing alert.

        Args:
            alert_id: ID of the alert to update
            name: New alert name (optional)
            options: New alert options (optional)
            rearm: New rearm value (optional)

        Returns:
            Updated alert dictionary
        """
        payload: dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if options is not None:
            payload["options"] = options
        if rearm is not None:
            payload["rearm"] = rearm

        response = httpx.post(
            f"{self.base_url}/api/alerts/{alert_id}",
            headers=self.headers,
            json=payload,
            timeout=30.0,
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    def get_alert_subscriptions(self, alert_id: int) -> list[dict[str, Any]]:
        """Get subscriptions for an alert.

        Args:
            alert_id: ID of the alert

        Returns:
            List of subscription dictionaries
        """
        response = httpx.get(
            f"{self.base_url}/api/alerts/{alert_id}/subscriptions",
            headers=self.headers,
            timeout=30.0,
        )
        response.raise_for_status()
        return cast(list[dict[str, Any]], response.json())

    def add_alert_subscription(
        self,
        alert_id: int,
        destination_id: int | None = None,
    ) -> dict[str, Any]:
        """Add a subscription to an alert.

        Args:
            alert_id: ID of the alert
            destination_id: ID of the notification destination (None for email to self)

        Returns:
            Created subscription dictionary
        """
        payload: dict[str, Any] = {}
        if destination_id is not None:
            payload["destination_id"] = destination_id

        response = httpx.post(
            f"{self.base_url}/api/alerts/{alert_id}/subscriptions",
            headers=self.headers,
            json=payload,
            timeout=30.0,
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    def get_destinations(self) -> list[dict[str, Any]]:
        """Get list of notification destinations.

        Returns:
            List of destination dictionaries (Slack, email, webhooks, etc.)
        """
        response = httpx.get(
            f"{self.base_url}/api/destinations",
            headers=self.headers,
            timeout=30.0,
        )
        response.raise_for_status()
        return cast(list[dict[str, Any]], response.json())

    def create_destination(
        self,
        name: str,
        destination_type: str,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a new notification destination.

        Args:
            name: Destination name (e.g., "Slack - Supply Chain Alerts")
            destination_type: Type of destination ("slack", "email", "webhook")
            options: Destination-specific options:
                - For Slack: {"url": "https://hooks.slack.com/services/..."}
                - For Email: {"addresses": "email@example.com"}
                - For Webhook: {"url": "https://..."}

        Returns:
            Created destination dictionary
        """
        response = httpx.post(
            f"{self.base_url}/api/destinations",
            headers=self.headers,
            json={
                "name": name,
                "type": destination_type,
                "options": options,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    def update_destination(
        self,
        destination_id: int,
        name: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Update an existing notification destination.

        Args:
            destination_id: ID of the destination to update
            name: New destination name (optional)
            options: New destination options (optional)

        Returns:
            Updated destination dictionary
        """
        payload: dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if options is not None:
            payload["options"] = options

        response = httpx.post(
            f"{self.base_url}/api/destinations/{destination_id}",
            headers=self.headers,
            json=payload,
            timeout=30.0,
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    def remove_alert_subscription(
        self,
        alert_id: int,
        subscription_id: int,
    ) -> None:
        """Remove a subscription from an alert.

        Args:
            alert_id: ID of the alert
            subscription_id: ID of the subscription to remove
        """
        response = httpx.delete(
            f"{self.base_url}/api/alerts/{alert_id}/subscriptions/{subscription_id}",
            headers=self.headers,
            timeout=30.0,
        )
        response.raise_for_status()


def find_query_by_name(queries: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    """Find a query by name.

    Args:
        queries: List of query dictionaries
        name: Query name to find

    Returns:
        Query dictionary if found, None otherwise
    """
    for query in queries:
        if query.get("name") == name:
            return query
    return None


def find_dashboard_by_name(
    dashboards: list[dict[str, Any]], name: str
) -> dict[str, Any] | None:
    """Find a dashboard by name.

    Args:
        dashboards: List of dashboard dictionaries
        name: Dashboard name to find

    Returns:
        Dashboard dictionary if found, None otherwise
    """
    for dashboard in dashboards:
        if dashboard.get("name") == name:
            return dashboard
    return None


def find_alert_by_name(
    alerts: list[dict[str, Any]], name: str
) -> dict[str, Any] | None:
    """Find an alert by name.

    Args:
        alerts: List of alert dictionaries
        name: Alert name to find

    Returns:
        Alert dictionary if found, None otherwise
    """
    for alert in alerts:
        if alert.get("name") == name:
            return alert
    return None


def find_destination_by_name(
    destinations: list[dict[str, Any]], name: str
) -> dict[str, Any] | None:
    """Find a notification destination by name.

    Args:
        destinations: List of destination dictionaries
        name: Destination name to find

    Returns:
        Destination dictionary if found, None otherwise
    """
    for dest in destinations:
        if dest.get("name") == name:
            return dest
    return None


def find_subscription_by_destination(
    subscriptions: list[dict[str, Any]], destination_id: int
) -> dict[str, Any] | None:
    """Find a subscription by destination ID.

    Args:
        subscriptions: List of subscription dictionaries
        destination_id: ID of the destination to find

    Returns:
        Subscription dictionary if found, None otherwise
    """
    for sub in subscriptions:
        dest = sub.get("destination")
        if dest and dest.get("id") == destination_id:
            return sub
    return None


def setup_doh_queries(client: RedashClient, data_source_id: int) -> dict[str, int]:
    """Set up DOH overview queries in Redash.

    Args:
        client: Redash API client
        data_source_id: ID of the data source to use

    Returns:
        Dictionary mapping query names to query IDs
    """
    queries_to_create = [
        {
            "name": "DOH Overview",
            "query": DOH_OVERVIEW_QUERY,
            "description": "Days on Hand overview for all SKUs by warehouse. "
            "Shows DOH_T30, DOH_T90, and status indicators (CRITICAL/WARNING/OK).",
        },
        {
            "name": "DOH by SKU",
            "query": DOH_BY_SKU_QUERY,
            "description": "Days on Hand metrics aggregated by SKU across all warehouses.",
        },
        {
            "name": "Shipment:Depletion Ratio",
            "query": SHIP_DEP_RATIO_QUERY,
            "description": "Supply/demand balance ratios (A30, A90) for all SKUs by warehouse. "
            "Shows OVERSUPPLY (>2.0), UNDERSUPPLY (<0.5), or BALANCED status.",
        },
        {
            "name": "Shipment:Depletion Ratio by SKU",
            "query": SHIP_DEP_RATIO_BY_SKU_QUERY,
            "description": "Supply/demand balance ratios aggregated by SKU across all warehouses.",
        },
    ]

    # Get existing queries
    existing_queries = client.get_queries()
    created_queries: dict[str, int] = {}

    for query_def in queries_to_create:
        existing = find_query_by_name(existing_queries, query_def["name"])

        if existing:
            # Update existing query
            print(f"Updating existing query: {query_def['name']} (ID: {existing['id']})")
            result = client.update_query(
                query_id=existing["id"],
                name=query_def["name"],
                query=query_def["query"],
                description=query_def["description"],
            )
            created_queries[query_def["name"]] = existing["id"]
        else:
            # Create new query
            print(f"Creating query: {query_def['name']}")
            result = client.create_query(
                name=query_def["name"],
                query=query_def["query"],
                data_source_id=data_source_id,
                description=query_def["description"],
            )
            created_queries[query_def["name"]] = result["id"]
            print(f"  Created with ID: {result['id']}")

    return created_queries


def setup_ratio_visualizations(
    client: RedashClient, query_ids: dict[str, int]
) -> dict[str, int]:
    """Set up visualizations for shipment:depletion ratio queries.

    Creates bar charts with color coding for ratio values:
    - Red: UNDERSUPPLY (< 0.5)
    - Yellow: OVERSUPPLY (> 2.0)
    - Green: BALANCED (0.5 - 2.0)

    Args:
        client: Redash API client
        query_ids: Dictionary mapping query names to IDs

    Returns:
        Dictionary mapping visualization names to visualization IDs
    """
    created_visualizations: dict[str, int] = {}

    # Visualization for Shipment:Depletion Ratio by SKU (bar chart)
    if "Shipment:Depletion Ratio by SKU" in query_ids:
        query_id = query_ids["Shipment:Depletion Ratio by SKU"]

        # Check if visualization already exists
        query_data = client.get_query(query_id)
        existing_vis = None
        for vis in query_data.get("visualizations", []):
            if vis.get("name") == "Ratio Chart":
                existing_vis = vis
                break

        if existing_vis:
            print(f"  Visualization 'Ratio Chart' already exists (ID: {existing_vis['id']})")
            created_visualizations["Ratio Chart"] = existing_vis["id"]
        else:
            print("Creating visualization: Ratio Chart for Shipment:Depletion Ratio by SKU")

            # Bar chart options for Redash
            # Color coding based on status_30d column
            chart_options = {
                "globalSeriesType": "column",
                "columnMapping": {
                    "sku": "x",
                    "a30_ship_dep_ratio": "y",
                    "status_30d": "series",
                },
                "xAxis": {
                    "type": "-",
                    "labels": {"enabled": True},
                },
                "yAxis": [
                    {
                        "type": "linear",
                        "title": {"text": "Shipment:Depletion Ratio (30d)"},
                    }
                ],
                "seriesOptions": {
                    "UNDERSUPPLY": {"color": "#E74C3C", "type": "column"},
                    "BALANCED": {"color": "#2ECC71", "type": "column"},
                    "OVERSUPPLY": {"color": "#F39C12", "type": "column"},
                    "NO SALES": {"color": "#95A5A6", "type": "column"},
                },
                "legend": {"enabled": True, "placement": "auto"},
                "showDataLabels": True,
                "numberFormat": "0.00",
                "percentFormat": "0%",
            }

            try:
                vis = client.create_visualization(
                    query_id=query_id,
                    name="Ratio Chart",
                    vis_type="CHART",
                    options=chart_options,
                )
                created_visualizations["Ratio Chart"] = vis["id"]
                print(f"  Created with ID: {vis['id']}")
            except httpx.HTTPStatusError as e:
                print(f"  Warning: Could not create visualization: {e}")

    return created_visualizations


def setup_stockout_alert(
    client: RedashClient, data_source_id: int
) -> dict[str, Any] | None:
    """Set up stock-out risk alert in Redash.

    Creates an alert that fires when DOH_T30 < 14 days for any SKU.
    The alert is configured to monitor the query result count -
    if any rows are returned (meaning SKUs below threshold), the alert fires.

    Args:
        client: Redash API client
        data_source_id: ID of the data source to use

    Returns:
        Alert dictionary if created/updated, None if creation failed
    """
    alert_name = "Stock-Out Risk Alert"
    query_name = "Stock-Out Risk Alert Query"

    # First, create/update the alert query
    existing_queries = client.get_queries()
    existing_query = find_query_by_name(existing_queries, query_name)

    if existing_query:
        print(f"Updating existing query: {query_name} (ID: {existing_query['id']})")
        client.update_query(
            query_id=existing_query["id"],
            name=query_name,
            query=STOCKOUT_ALERT_QUERY,
            description="Returns SKUs at critical stock-out risk (DOH_T30 < 14 days). "
            "Used for alert configuration - alert fires when query returns rows.",
        )
        query_id = existing_query["id"]
    else:
        print(f"Creating query: {query_name}")
        result = client.create_query(
            name=query_name,
            query=STOCKOUT_ALERT_QUERY,
            data_source_id=data_source_id,
            description="Returns SKUs at critical stock-out risk (DOH_T30 < 14 days). "
            "Used for alert configuration - alert fires when query returns rows.",
        )
        query_id = result["id"]
        print(f"  Created with ID: {query_id}")

    # Execute the query once to initialize it (required for alert creation)
    print("  Executing query to initialize...")
    try:
        client.execute_query(query_id)
    except httpx.HTTPStatusError as e:
        print(f"  Warning: Query execution returned error (may be expected if no data): {e}")

    # Now create/update the alert
    existing_alerts = client.get_alerts()
    existing_alert = find_alert_by_name(existing_alerts, alert_name)

    # Alert options: fires when query returns any rows (count > 0)
    # Redash alerts monitor a specific column value
    # We use the 'sku' column and check if it's not empty (any value triggers)
    alert_options = {
        "column": "sku",
        "op": "greater than",  # Fires when there's at least one SKU
        "value": 0,  # Actually, we need to check row count
        "custom_subject": "CRITICAL: Stock-Out Risk Detected",
        "custom_body": (
            "One or more SKUs have fallen below the 14-day stock threshold.\n\n"
            "Action Required: Review inventory levels and consider placing orders.\n\n"
            "View details: {{query_url}}"
        ),
    }

    # For row count based alerts, Redash uses a special approach
    # We check the row count using the built-in functionality
    # The "greater than 0" check on any column will fire if rows exist
    alert_options = {
        "column": "doh_t30",
        "op": "less than",
        "value": 14,
        "custom_subject": "CRITICAL: Stock-Out Risk - DOH Below 14 Days",
        "custom_body": (
            "Stock-out risk detected!\n\n"
            "One or more SKUs have Days on Hand (DOH_T30) below 14 days.\n\n"
            "Immediate action may be required to prevent stock-outs.\n\n"
            "View full details: {{query_url}}"
        ),
    }

    # Rearm after 1 hour (3600 seconds) - prevents alert spam
    rearm_seconds = 3600

    if existing_alert:
        print(f"Updating existing alert: {alert_name} (ID: {existing_alert['id']})")
        result = client.update_alert(
            alert_id=existing_alert["id"],
            name=alert_name,
            options=alert_options,
            rearm=rearm_seconds,
        )
        print("  Updated alert")
        return result
    else:
        print(f"Creating alert: {alert_name}")
        try:
            result = client.create_alert(
                name=alert_name,
                query_id=query_id,
                options=alert_options,
                rearm=rearm_seconds,
            )
            print(f"  Created with ID: {result['id']}")
            return result
        except httpx.HTTPStatusError as e:
            print(f"  Error creating alert: {e.response.status_code} - {e.response.text}")
            return None


def setup_slack_notification(
    client: RedashClient,
    alert_id: int,
    slack_webhook_url: str | None = None,
) -> dict[str, Any] | None:
    """Set up Slack notification for an alert.

    Creates or updates a Slack destination and subscribes the alert to it.
    The Slack webhook URL can be provided directly or via SLACK_WEBHOOK_URL
    environment variable.

    Args:
        client: Redash API client
        alert_id: ID of the alert to configure
        slack_webhook_url: Slack incoming webhook URL (optional, uses env var if not provided)

    Returns:
        Subscription dictionary if successful, None if setup failed
    """
    # Get Slack webhook URL from parameter or environment
    webhook_url = slack_webhook_url or os.environ.get("SLACK_WEBHOOK_URL")

    if not webhook_url:
        print("  Skipping Slack notification: SLACK_WEBHOOK_URL not configured")
        print("  Set SLACK_WEBHOOK_URL environment variable to enable Slack alerts")
        return None

    destination_name = "Slack - Supply Chain Alerts"

    # Check if destination already exists
    existing_destinations = client.get_destinations()
    existing_dest = find_destination_by_name(existing_destinations, destination_name)

    if existing_dest:
        print(f"  Slack destination already exists: {destination_name} (ID: {existing_dest['id']})")
        # Update webhook URL if it changed
        try:
            client.update_destination(
                destination_id=existing_dest["id"],
                options={"url": webhook_url},
            )
            print("  Updated Slack webhook URL")
        except httpx.HTTPStatusError as e:
            print(f"  Warning: Could not update destination: {e}")
        destination_id = existing_dest["id"]
    else:
        # Create new Slack destination
        print(f"  Creating Slack destination: {destination_name}")
        try:
            dest = client.create_destination(
                name=destination_name,
                destination_type="slack",
                options={"url": webhook_url},
            )
            destination_id = dest["id"]
            print(f"  Created Slack destination with ID: {destination_id}")
        except httpx.HTTPStatusError as e:
            print(f"  Error creating Slack destination: {e.response.status_code} - {e.response.text}")
            return None

    # Check if alert is already subscribed to this destination
    existing_subscriptions = client.get_alert_subscriptions(alert_id)
    existing_sub = find_subscription_by_destination(existing_subscriptions, destination_id)

    if existing_sub:
        print(f"  Alert already subscribed to Slack destination (subscription ID: {existing_sub['id']})")
        return existing_sub

    # Subscribe alert to Slack destination
    print("  Subscribing alert to Slack destination...")
    try:
        subscription = client.add_alert_subscription(
            alert_id=alert_id,
            destination_id=destination_id,
        )
        print(f"  Created subscription with ID: {subscription['id']}")
        return subscription
    except httpx.HTTPStatusError as e:
        print(f"  Error creating subscription: {e.response.status_code} - {e.response.text}")
        return None


def setup_doh_dashboard(
    client: RedashClient, query_ids: dict[str, int]
) -> dict[str, Any]:
    """Set up DOH overview dashboard in Redash.

    Args:
        client: Redash API client
        query_ids: Dictionary mapping query names to IDs

    Returns:
        Dashboard dictionary
    """
    dashboard_name = "Supply Chain Overview"

    # Get existing dashboards
    existing_dashboards = client.get_dashboards()
    existing = find_dashboard_by_name(existing_dashboards, dashboard_name)

    if existing:
        print(f"Dashboard already exists: {dashboard_name} (ID: {existing['id']})")
        return existing

    # Create new dashboard
    print(f"Creating dashboard: {dashboard_name}")
    dashboard = client.create_dashboard(dashboard_name)
    dashboard_id = dashboard["id"]
    print(f"  Created with ID: {dashboard_id}")

    # Add widgets for each query
    # Note: We need to get the visualization IDs from the queries
    # Each query has a default "Table" visualization created automatically

    # Publish dashboard
    client.publish_dashboard(dashboard_id)
    print("  Published dashboard")

    return dashboard


def main() -> int:
    """Main entry point for setting up Redash dashboard.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Get configuration from environment
    redash_url = os.environ.get("REDASH_URL", DEFAULT_REDASH_URL)
    api_key = os.environ.get("REDASH_API_KEY")

    if not api_key:
        print("Error: REDASH_API_KEY environment variable is required")
        print("You can get an API key from Redash settings page")
        return 1

    print(f"Connecting to Redash at: {redash_url}")

    try:
        client = RedashClient(redash_url, api_key)

        # Get data sources
        data_sources = client.get_data_sources()
        if not data_sources:
            print("Error: No data sources configured in Redash")
            return 1

        # Find the Une Femme data source (or use the first one)
        data_source = None
        for ds in data_sources:
            if "Une Femme" in ds.get("name", ""):
                data_source = ds
                break
        if not data_source:
            data_source = data_sources[0]

        print(f"Using data source: {data_source['name']} (ID: {data_source['id']})")

        # Set up queries
        query_ids = setup_doh_queries(client, data_source["id"])
        print(f"\nCreated/updated {len(query_ids)} queries")

        # Set up ratio visualizations with color coding
        print("\nSetting up visualizations...")
        vis_ids = setup_ratio_visualizations(client, query_ids)
        print(f"Created/updated {len(vis_ids)} visualizations")

        # Set up dashboard
        dashboard = setup_doh_dashboard(client, query_ids)
        print(f"\nDashboard URL: {redash_url}/dashboards/{dashboard['id']}")

        # Set up stock-out alert
        print("\nSetting up alerts...")
        stockout_alert = setup_stockout_alert(client, data_source["id"])
        if stockout_alert:
            print(f"Stock-Out Alert ID: {stockout_alert['id']}")

            # Set up Slack notification for the alert
            print("\nSetting up Slack notification...")
            slack_sub = setup_slack_notification(client, stockout_alert["id"])
            if slack_sub:
                print("Slack notification configured successfully")
        else:
            print("Warning: Stock-out alert setup failed or skipped")

        print("\nSetup complete!")
        print("\nNext steps:")
        print("1. Open the queries in Redash and verify they work")
        print("2. Add visualizations (charts) to the queries")
        print("3. Add the visualizations to the dashboard")
        print("4. Set up auto-refresh schedule (5 minutes)")
        print("5. Set SLACK_WEBHOOK_URL environment variable if not already configured")

        return 0

    except httpx.HTTPStatusError as e:
        print(f"HTTP Error: {e.response.status_code} - {e.response.text}")
        return 1
    except httpx.RequestError as e:
        print(f"Request Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
