"""Tests for Redash dashboard SQL queries.

These tests verify the SQL queries used in Redash dashboards are syntactically
correct and contain the expected elements.
"""

from pathlib import Path

import pytest

# Path to SQL files
SQL_DIR = Path(__file__).parent.parent / "sql" / "redash"


@pytest.fixture
def doh_overview_query() -> str:
    """Load DOH overview SQL query."""
    query_path = SQL_DIR / "doh_overview.sql"
    return query_path.read_text()


@pytest.fixture
def doh_by_sku_query() -> str:
    """Load DOH by SKU SQL query."""
    query_path = SQL_DIR / "doh_by_sku.sql"
    return query_path.read_text()


@pytest.fixture
def doh_overview_direct_query() -> str:
    """Load DOH overview direct SQL query."""
    query_path = SQL_DIR / "doh_overview_direct.sql"
    return query_path.read_text()


class TestDOHOverviewQuery:
    """Tests for DOH Overview query using materialized view."""

    def test_query_file_exists(self, doh_overview_query: str):
        """Test that DOH overview SQL file exists and has content."""
        assert len(doh_overview_query) > 100

    def test_query_has_select(self, doh_overview_query: str):
        """Test that query has SELECT statement."""
        assert "SELECT" in doh_overview_query

    def test_query_uses_materialized_view(self, doh_overview_query: str):
        """Test that query uses mv_doh_metrics materialized view."""
        assert "mv_doh_metrics" in doh_overview_query

    def test_query_includes_doh_t30(self, doh_overview_query: str):
        """Test that query includes DOH_T30 metric."""
        assert "doh_t30" in doh_overview_query.lower()

    def test_query_includes_doh_t90(self, doh_overview_query: str):
        """Test that query includes DOH_T90 metric."""
        assert "doh_t90" in doh_overview_query.lower()

    def test_query_includes_sku(self, doh_overview_query: str):
        """Test that query includes SKU column."""
        assert "p.sku" in doh_overview_query

    def test_query_includes_status_indicator(self, doh_overview_query: str):
        """Test that query includes status indicator (CRITICAL/WARNING/OK)."""
        assert "CRITICAL" in doh_overview_query
        assert "WARNING" in doh_overview_query
        assert "OK" in doh_overview_query

    def test_query_includes_no_sales_status(self, doh_overview_query: str):
        """Test that query handles zero depletion with NO SALES status."""
        assert "NO SALES" in doh_overview_query

    def test_query_joins_products(self, doh_overview_query: str):
        """Test that query joins products table."""
        assert "JOIN products" in doh_overview_query or "products p" in doh_overview_query

    def test_query_joins_warehouses(self, doh_overview_query: str):
        """Test that query joins warehouses table."""
        assert "JOIN warehouses" in doh_overview_query or "warehouses w" in doh_overview_query

    def test_query_has_order_by(self, doh_overview_query: str):
        """Test that query has ORDER BY clause."""
        assert "ORDER BY" in doh_overview_query


class TestDOHBySkuQuery:
    """Tests for DOH by SKU aggregated query."""

    def test_query_file_exists(self, doh_by_sku_query: str):
        """Test that DOH by SKU SQL file exists and has content."""
        assert len(doh_by_sku_query) > 100

    def test_query_has_select(self, doh_by_sku_query: str):
        """Test that query has SELECT statement."""
        assert "SELECT" in doh_by_sku_query

    def test_query_has_group_by(self, doh_by_sku_query: str):
        """Test that query aggregates by SKU."""
        assert "GROUP BY" in doh_by_sku_query

    def test_query_uses_sum_aggregation(self, doh_by_sku_query: str):
        """Test that query uses SUM aggregation for totals."""
        assert "SUM(" in doh_by_sku_query

    def test_query_includes_doh_calculations(self, doh_by_sku_query: str):
        """Test that query calculates DOH metrics."""
        assert "doh_t30" in doh_by_sku_query.lower()
        assert "doh_t90" in doh_by_sku_query.lower()

    def test_query_includes_status_indicator(self, doh_by_sku_query: str):
        """Test that query includes status indicator."""
        assert "CRITICAL" in doh_by_sku_query
        assert "WARNING" in doh_by_sku_query

    def test_query_calculates_total_on_hand(self, doh_by_sku_query: str):
        """Test that query calculates total on hand inventory."""
        assert "total_on_hand" in doh_by_sku_query or "SUM(m.current_inventory)" in doh_by_sku_query


class TestDOHOverviewDirectQuery:
    """Tests for DOH Overview Direct query using inventory_events table."""

    def test_query_file_exists(self, doh_overview_direct_query: str):
        """Test that DOH overview direct SQL file exists and has content."""
        assert len(doh_overview_direct_query) > 100

    def test_query_has_select(self, doh_overview_direct_query: str):
        """Test that query has SELECT statement."""
        assert "SELECT" in doh_overview_direct_query

    def test_query_uses_inventory_events(self, doh_overview_direct_query: str):
        """Test that query uses inventory_events table directly."""
        assert "inventory_events" in doh_overview_direct_query

    def test_query_has_cte_for_current_inventory(self, doh_overview_direct_query: str):
        """Test that query uses CTE for current inventory calculation."""
        assert "WITH current_inventory AS" in doh_overview_direct_query

    def test_query_handles_snapshot_events(self, doh_overview_direct_query: str):
        """Test that query handles snapshot event type."""
        assert "snapshot" in doh_overview_direct_query

    def test_query_handles_depletion_events(self, doh_overview_direct_query: str):
        """Test that query handles depletion event type."""
        assert "depletion" in doh_overview_direct_query

    def test_query_handles_shipment_events(self, doh_overview_direct_query: str):
        """Test that query handles shipment event type."""
        assert "shipment" in doh_overview_direct_query

    def test_query_calculates_30day_window(self, doh_overview_direct_query: str):
        """Test that query calculates 30-day depletion window."""
        assert "30 days" in doh_overview_direct_query

    def test_query_calculates_90day_window(self, doh_overview_direct_query: str):
        """Test that query calculates 90-day depletion window."""
        assert "90 days" in doh_overview_direct_query

    def test_query_includes_status_indicator(self, doh_overview_direct_query: str):
        """Test that query includes status indicator."""
        assert "CRITICAL" in doh_overview_direct_query
        assert "WARNING" in doh_overview_direct_query
        assert "OK" in doh_overview_direct_query


class TestRedashSetupScript:
    """Tests for Redash setup script."""

    def test_script_file_exists(self):
        """Test that the setup script exists."""
        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        assert script_path.exists()

    def test_script_imports_work(self):
        """Test that the script's imports are valid."""
        import importlib.util

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        # This will raise if there are syntax errors
        spec.loader.exec_module(module)

        # Check key items exist
        assert hasattr(module, "RedashClient")
        assert hasattr(module, "DOH_OVERVIEW_QUERY")
        assert hasattr(module, "DOH_BY_SKU_QUERY")
        assert hasattr(module, "main")

    def test_script_has_doh_overview_query(self):
        """Test that script contains DOH overview query."""
        import importlib.util

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        query = module.DOH_OVERVIEW_QUERY
        assert "SELECT" in query
        assert "doh_t30" in query.lower()
        assert "doh_t90" in query.lower()

    def test_script_has_redash_client_class(self):
        """Test that script contains RedashClient class with required methods."""
        import importlib.util

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        client_class = module.RedashClient
        # Check required methods exist
        assert hasattr(client_class, "get_data_sources")
        assert hasattr(client_class, "get_queries")
        assert hasattr(client_class, "create_query")
        assert hasattr(client_class, "create_dashboard")


class TestSQLSyntax:
    """Tests for SQL syntax validation."""

    def test_doh_overview_no_unclosed_strings(self, doh_overview_query: str):
        """Test that DOH overview query has no unclosed strings."""
        # Remove comments first, then count quotes
        clean = self._remove_comments(doh_overview_query)
        quote_count = clean.count("'")
        assert quote_count % 2 == 0, "Unclosed string literal detected"

    def test_doh_by_sku_no_unclosed_strings(self, doh_by_sku_query: str):
        """Test that DOH by SKU query has no unclosed strings."""
        clean = self._remove_comments(doh_by_sku_query)
        quote_count = clean.count("'")
        assert quote_count % 2 == 0, "Unclosed string literal detected"

    def test_doh_overview_direct_no_unclosed_strings(self, doh_overview_direct_query: str):
        """Test that DOH overview direct query has no unclosed strings."""
        clean = self._remove_comments(doh_overview_direct_query)
        quote_count = clean.count("'")
        assert quote_count % 2 == 0, "Unclosed string literal detected"

    def _remove_comments(self, sql: str) -> str:
        """Remove SQL comments from query."""
        import re
        return re.sub(r"--.*$", "", sql, flags=re.MULTILINE)

    def test_doh_overview_balanced_parentheses(self, doh_overview_query: str):
        """Test that DOH overview query has balanced parentheses."""
        # Remove strings and comments for accurate count
        clean = self._remove_strings_and_comments(doh_overview_query)
        assert clean.count("(") == clean.count(")"), "Unbalanced parentheses detected"

    def test_doh_by_sku_balanced_parentheses(self, doh_by_sku_query: str):
        """Test that DOH by SKU query has balanced parentheses."""
        clean = self._remove_strings_and_comments(doh_by_sku_query)
        assert clean.count("(") == clean.count(")"), "Unbalanced parentheses detected"

    def test_doh_overview_direct_balanced_parentheses(self, doh_overview_direct_query: str):
        """Test that DOH overview direct query has balanced parentheses."""
        clean = self._remove_strings_and_comments(doh_overview_direct_query)
        assert clean.count("(") == clean.count(")"), "Unbalanced parentheses detected"

    def _remove_strings_and_comments(self, sql: str) -> str:
        """Remove string literals and comments from SQL for syntax checking."""
        import re

        # Remove single-line comments
        sql = re.sub(r"--.*$", "", sql, flags=re.MULTILINE)
        # Remove string literals (simplified - doesn't handle escaped quotes)
        sql = re.sub(r"'[^']*'", "''", sql)
        return sql


# Fixtures for shipment:depletion ratio queries
@pytest.fixture
def ship_dep_ratio_query() -> str:
    """Load shipment:depletion ratio SQL query."""
    query_path = SQL_DIR / "ship_dep_ratio.sql"
    return query_path.read_text()


@pytest.fixture
def ship_dep_ratio_by_sku_query() -> str:
    """Load shipment:depletion ratio by SKU SQL query."""
    query_path = SQL_DIR / "ship_dep_ratio_by_sku.sql"
    return query_path.read_text()


@pytest.fixture
def ship_dep_ratio_direct_query() -> str:
    """Load shipment:depletion ratio direct SQL query."""
    query_path = SQL_DIR / "ship_dep_ratio_direct.sql"
    return query_path.read_text()


class TestShipDepRatioQuery:
    """Tests for Shipment:Depletion Ratio query using materialized view."""

    def test_query_file_exists(self, ship_dep_ratio_query: str):
        """Test that ship:dep ratio SQL file exists and has content."""
        assert len(ship_dep_ratio_query) > 100

    def test_query_has_select(self, ship_dep_ratio_query: str):
        """Test that query has SELECT statement."""
        assert "SELECT" in ship_dep_ratio_query

    def test_query_uses_materialized_view(self, ship_dep_ratio_query: str):
        """Test that query uses mv_doh_metrics materialized view."""
        assert "mv_doh_metrics" in ship_dep_ratio_query

    def test_query_includes_a30_ship_dep_ratio(self, ship_dep_ratio_query: str):
        """Test that query includes A30 ship:dep ratio."""
        assert "a30_ship_dep_ratio" in ship_dep_ratio_query.lower()

    def test_query_includes_a90_ship_dep_ratio(self, ship_dep_ratio_query: str):
        """Test that query includes A90 ship:dep ratio."""
        assert "a90_ship_dep_ratio" in ship_dep_ratio_query.lower()

    def test_query_includes_sku(self, ship_dep_ratio_query: str):
        """Test that query includes SKU column."""
        assert "p.sku" in ship_dep_ratio_query

    def test_query_includes_status_30d(self, ship_dep_ratio_query: str):
        """Test that query includes 30-day status indicator."""
        assert "status_30d" in ship_dep_ratio_query

    def test_query_includes_status_90d(self, ship_dep_ratio_query: str):
        """Test that query includes 90-day status indicator."""
        assert "status_90d" in ship_dep_ratio_query

    def test_query_includes_oversupply_status(self, ship_dep_ratio_query: str):
        """Test that query includes OVERSUPPLY status (ratio > 2.0)."""
        assert "OVERSUPPLY" in ship_dep_ratio_query

    def test_query_includes_undersupply_status(self, ship_dep_ratio_query: str):
        """Test that query includes UNDERSUPPLY status (ratio < 0.5)."""
        assert "UNDERSUPPLY" in ship_dep_ratio_query

    def test_query_includes_balanced_status(self, ship_dep_ratio_query: str):
        """Test that query includes BALANCED status."""
        assert "BALANCED" in ship_dep_ratio_query

    def test_query_includes_no_sales_status(self, ship_dep_ratio_query: str):
        """Test that query handles zero depletion with NO SALES status."""
        assert "NO SALES" in ship_dep_ratio_query

    def test_query_joins_products(self, ship_dep_ratio_query: str):
        """Test that query joins products table."""
        assert "JOIN products" in ship_dep_ratio_query or "products p" in ship_dep_ratio_query

    def test_query_joins_warehouses(self, ship_dep_ratio_query: str):
        """Test that query joins warehouses table."""
        assert "JOIN warehouses" in ship_dep_ratio_query or "warehouses w" in ship_dep_ratio_query

    def test_query_has_order_by(self, ship_dep_ratio_query: str):
        """Test that query has ORDER BY clause."""
        assert "ORDER BY" in ship_dep_ratio_query


class TestShipDepRatioBySkuQuery:
    """Tests for Shipment:Depletion Ratio by SKU aggregated query."""

    def test_query_file_exists(self, ship_dep_ratio_by_sku_query: str):
        """Test that ship:dep ratio by SKU SQL file exists and has content."""
        assert len(ship_dep_ratio_by_sku_query) > 100

    def test_query_has_select(self, ship_dep_ratio_by_sku_query: str):
        """Test that query has SELECT statement."""
        assert "SELECT" in ship_dep_ratio_by_sku_query

    def test_query_has_group_by(self, ship_dep_ratio_by_sku_query: str):
        """Test that query aggregates by SKU."""
        assert "GROUP BY" in ship_dep_ratio_by_sku_query

    def test_query_uses_sum_aggregation(self, ship_dep_ratio_by_sku_query: str):
        """Test that query uses SUM aggregation for totals."""
        assert "SUM(" in ship_dep_ratio_by_sku_query

    def test_query_includes_ratio_calculations(self, ship_dep_ratio_by_sku_query: str):
        """Test that query calculates ratio metrics."""
        assert "a30_ship_dep_ratio" in ship_dep_ratio_by_sku_query.lower()
        assert "a90_ship_dep_ratio" in ship_dep_ratio_by_sku_query.lower()

    def test_query_includes_status_indicators(self, ship_dep_ratio_by_sku_query: str):
        """Test that query includes status indicators."""
        assert "OVERSUPPLY" in ship_dep_ratio_by_sku_query
        assert "UNDERSUPPLY" in ship_dep_ratio_by_sku_query
        assert "BALANCED" in ship_dep_ratio_by_sku_query

    def test_query_calculates_total_shipments(self, ship_dep_ratio_by_sku_query: str):
        """Test that query calculates total shipments."""
        assert "total_shipments_30d" in ship_dep_ratio_by_sku_query or "SUM(m.shipments_30d)" in ship_dep_ratio_by_sku_query


class TestShipDepRatioDirectQuery:
    """Tests for Shipment:Depletion Ratio Direct query using inventory_events table."""

    def test_query_file_exists(self, ship_dep_ratio_direct_query: str):
        """Test that ship:dep ratio direct SQL file exists and has content."""
        assert len(ship_dep_ratio_direct_query) > 100

    def test_query_has_select(self, ship_dep_ratio_direct_query: str):
        """Test that query has SELECT statement."""
        assert "SELECT" in ship_dep_ratio_direct_query

    def test_query_uses_inventory_events(self, ship_dep_ratio_direct_query: str):
        """Test that query uses inventory_events table directly."""
        assert "inventory_events" in ship_dep_ratio_direct_query

    def test_query_has_cte_for_shipments(self, ship_dep_ratio_direct_query: str):
        """Test that query uses CTE for shipments calculation."""
        assert "shipments_30d" in ship_dep_ratio_direct_query

    def test_query_has_cte_for_depletions(self, ship_dep_ratio_direct_query: str):
        """Test that query uses CTE for depletions calculation."""
        assert "depletions_30d" in ship_dep_ratio_direct_query

    def test_query_handles_shipment_events(self, ship_dep_ratio_direct_query: str):
        """Test that query handles shipment event type."""
        assert "shipment" in ship_dep_ratio_direct_query

    def test_query_handles_depletion_events(self, ship_dep_ratio_direct_query: str):
        """Test that query handles depletion event type."""
        assert "depletion" in ship_dep_ratio_direct_query

    def test_query_calculates_30day_window(self, ship_dep_ratio_direct_query: str):
        """Test that query calculates 30-day window."""
        assert "30 days" in ship_dep_ratio_direct_query

    def test_query_calculates_90day_window(self, ship_dep_ratio_direct_query: str):
        """Test that query calculates 90-day window."""
        assert "90 days" in ship_dep_ratio_direct_query

    def test_query_includes_status_indicators(self, ship_dep_ratio_direct_query: str):
        """Test that query includes status indicators."""
        assert "OVERSUPPLY" in ship_dep_ratio_direct_query
        assert "UNDERSUPPLY" in ship_dep_ratio_direct_query
        assert "BALANCED" in ship_dep_ratio_direct_query


class TestShipDepRatioSQLSyntax:
    """Tests for SQL syntax validation for ratio queries."""

    def test_ship_dep_ratio_no_unclosed_strings(self, ship_dep_ratio_query: str):
        """Test that ship:dep ratio query has no unclosed strings."""
        clean = self._remove_comments(ship_dep_ratio_query)
        quote_count = clean.count("'")
        assert quote_count % 2 == 0, "Unclosed string literal detected"

    def test_ship_dep_ratio_by_sku_no_unclosed_strings(self, ship_dep_ratio_by_sku_query: str):
        """Test that ship:dep ratio by SKU query has no unclosed strings."""
        clean = self._remove_comments(ship_dep_ratio_by_sku_query)
        quote_count = clean.count("'")
        assert quote_count % 2 == 0, "Unclosed string literal detected"

    def test_ship_dep_ratio_direct_no_unclosed_strings(self, ship_dep_ratio_direct_query: str):
        """Test that ship:dep ratio direct query has no unclosed strings."""
        clean = self._remove_comments(ship_dep_ratio_direct_query)
        quote_count = clean.count("'")
        assert quote_count % 2 == 0, "Unclosed string literal detected"

    def _remove_comments(self, sql: str) -> str:
        """Remove SQL comments from query."""
        import re
        return re.sub(r"--.*$", "", sql, flags=re.MULTILINE)

    def test_ship_dep_ratio_balanced_parentheses(self, ship_dep_ratio_query: str):
        """Test that ship:dep ratio query has balanced parentheses."""
        clean = self._remove_strings_and_comments(ship_dep_ratio_query)
        assert clean.count("(") == clean.count(")"), "Unbalanced parentheses detected"

    def test_ship_dep_ratio_by_sku_balanced_parentheses(self, ship_dep_ratio_by_sku_query: str):
        """Test that ship:dep ratio by SKU query has balanced parentheses."""
        clean = self._remove_strings_and_comments(ship_dep_ratio_by_sku_query)
        assert clean.count("(") == clean.count(")"), "Unbalanced parentheses detected"

    def test_ship_dep_ratio_direct_balanced_parentheses(self, ship_dep_ratio_direct_query: str):
        """Test that ship:dep ratio direct query has balanced parentheses."""
        clean = self._remove_strings_and_comments(ship_dep_ratio_direct_query)
        assert clean.count("(") == clean.count(")"), "Unbalanced parentheses detected"

    def _remove_strings_and_comments(self, sql: str) -> str:
        """Remove string literals and comments from SQL for syntax checking."""
        import re

        # Remove single-line comments
        sql = re.sub(r"--.*$", "", sql, flags=re.MULTILINE)
        # Remove string literals (simplified - doesn't handle escaped quotes)
        sql = re.sub(r"'[^']*'", "''", sql)
        return sql


# Fixtures for stock-out alert query
@pytest.fixture
def stockout_alert_query() -> str:
    """Load stock-out alert SQL query."""
    query_path = SQL_DIR / "stockout_alert.sql"
    return query_path.read_text()


class TestStockoutAlertQuery:
    """Tests for Stock-Out Alert query."""

    def test_query_file_exists(self, stockout_alert_query: str):
        """Test that stockout alert SQL file exists and has content."""
        assert len(stockout_alert_query) > 100

    def test_query_has_select(self, stockout_alert_query: str):
        """Test that query has SELECT statement."""
        assert "SELECT" in stockout_alert_query

    def test_query_uses_materialized_view(self, stockout_alert_query: str):
        """Test that query uses mv_doh_metrics materialized view."""
        assert "mv_doh_metrics" in stockout_alert_query

    def test_query_filters_doh_below_14(self, stockout_alert_query: str):
        """Test that query filters for DOH_T30 < 14."""
        assert "doh_t30" in stockout_alert_query.lower()
        assert "< 14" in stockout_alert_query

    def test_query_includes_threshold(self, stockout_alert_query: str):
        """Test that query includes threshold value of 14 days."""
        assert "14" in stockout_alert_query
        assert "threshold" in stockout_alert_query.lower()

    def test_query_includes_sku(self, stockout_alert_query: str):
        """Test that query includes SKU column."""
        assert "p.sku" in stockout_alert_query

    def test_query_includes_warehouse(self, stockout_alert_query: str):
        """Test that query includes warehouse information."""
        assert "warehouse" in stockout_alert_query.lower()

    def test_query_includes_on_hand(self, stockout_alert_query: str):
        """Test that query includes on-hand inventory."""
        assert "on_hand" in stockout_alert_query or "current_inventory" in stockout_alert_query

    def test_query_joins_products(self, stockout_alert_query: str):
        """Test that query joins products table."""
        assert "JOIN products" in stockout_alert_query or "products p" in stockout_alert_query

    def test_query_joins_warehouses(self, stockout_alert_query: str):
        """Test that query joins warehouses table."""
        assert "JOIN warehouses" in stockout_alert_query or "warehouses w" in stockout_alert_query

    def test_query_has_where_clause(self, stockout_alert_query: str):
        """Test that query has WHERE clause for filtering."""
        assert "WHERE" in stockout_alert_query

    def test_query_excludes_null_doh(self, stockout_alert_query: str):
        """Test that query excludes NULL DOH values (no sales)."""
        assert "IS NOT NULL" in stockout_alert_query

    def test_query_has_order_by(self, stockout_alert_query: str):
        """Test that query has ORDER BY clause."""
        assert "ORDER BY" in stockout_alert_query


class TestStockoutAlertSQLSyntax:
    """Tests for SQL syntax validation for stock-out alert query."""

    def test_stockout_alert_no_unclosed_strings(self, stockout_alert_query: str):
        """Test that stockout alert query has no unclosed strings."""
        clean = self._remove_comments(stockout_alert_query)
        quote_count = clean.count("'")
        assert quote_count % 2 == 0, "Unclosed string literal detected"

    def _remove_comments(self, sql: str) -> str:
        """Remove SQL comments from query."""
        import re
        return re.sub(r"--.*$", "", sql, flags=re.MULTILINE)

    def test_stockout_alert_balanced_parentheses(self, stockout_alert_query: str):
        """Test that stockout alert query has balanced parentheses."""
        clean = self._remove_strings_and_comments(stockout_alert_query)
        assert clean.count("(") == clean.count(")"), "Unbalanced parentheses detected"

    def _remove_strings_and_comments(self, sql: str) -> str:
        """Remove string literals and comments from SQL for syntax checking."""
        import re

        # Remove single-line comments
        sql = re.sub(r"--.*$", "", sql, flags=re.MULTILINE)
        # Remove string literals (simplified - doesn't handle escaped quotes)
        sql = re.sub(r"'[^']*'", "''", sql)
        return sql


class TestRedashSetupScriptAlerts:
    """Tests for Redash setup script alert functionality."""

    def test_script_has_stockout_alert_query(self):
        """Test that script contains stock-out alert query."""
        import importlib.util

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert hasattr(module, "STOCKOUT_ALERT_QUERY")
        query = module.STOCKOUT_ALERT_QUERY
        assert "SELECT" in query
        assert "doh_t30" in query.lower()
        assert "< 14" in query

    def test_script_has_setup_stockout_alert_function(self):
        """Test that script has setup_stockout_alert function."""
        import importlib.util

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert hasattr(module, "setup_stockout_alert")

    def test_script_has_find_alert_by_name_function(self):
        """Test that script has find_alert_by_name helper function."""
        import importlib.util

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert hasattr(module, "find_alert_by_name")

    def test_redash_client_has_alert_methods(self):
        """Test that RedashClient has alert-related methods."""
        import importlib.util

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        client_class = module.RedashClient
        assert hasattr(client_class, "get_alerts")
        assert hasattr(client_class, "get_alert")
        assert hasattr(client_class, "create_alert")
        assert hasattr(client_class, "update_alert")
        assert hasattr(client_class, "get_alert_subscriptions")
        assert hasattr(client_class, "add_alert_subscription")
        assert hasattr(client_class, "get_destinations")

    def test_find_alert_by_name_finds_existing_alert(self):
        """Test that find_alert_by_name finds an alert by name."""
        import importlib.util

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        alerts = [
            {"id": 1, "name": "Alert 1"},
            {"id": 2, "name": "Stock-Out Risk Alert"},
            {"id": 3, "name": "Alert 3"},
        ]
        result = module.find_alert_by_name(alerts, "Stock-Out Risk Alert")
        assert result is not None
        assert result["id"] == 2

    def test_find_alert_by_name_returns_none_for_missing(self):
        """Test that find_alert_by_name returns None when alert not found."""
        import importlib.util

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        alerts = [
            {"id": 1, "name": "Alert 1"},
            {"id": 2, "name": "Alert 2"},
        ]
        result = module.find_alert_by_name(alerts, "Nonexistent Alert")
        assert result is None


class TestRedashSetupScriptRatios:
    """Tests for Redash setup script ratio queries."""

    def test_script_has_ship_dep_ratio_query(self):
        """Test that script contains ship:dep ratio query."""
        import importlib.util

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert hasattr(module, "SHIP_DEP_RATIO_QUERY")
        query = module.SHIP_DEP_RATIO_QUERY
        assert "SELECT" in query
        assert "a30_ship_dep_ratio" in query.lower()
        assert "a90_ship_dep_ratio" in query.lower()

    def test_script_has_ship_dep_ratio_by_sku_query(self):
        """Test that script contains ship:dep ratio by SKU query."""
        import importlib.util

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert hasattr(module, "SHIP_DEP_RATIO_BY_SKU_QUERY")
        query = module.SHIP_DEP_RATIO_BY_SKU_QUERY
        assert "SELECT" in query
        assert "GROUP BY" in query

    def test_script_has_visualization_setup_function(self):
        """Test that script has setup_ratio_visualizations function."""
        import importlib.util

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert hasattr(module, "setup_ratio_visualizations")

    def test_redash_client_has_create_visualization_method(self):
        """Test that RedashClient has create_visualization method."""
        import importlib.util

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        client_class = module.RedashClient
        assert hasattr(client_class, "create_visualization")
        assert hasattr(client_class, "get_query")


class TestRedashSetupScriptSlackNotification:
    """Tests for Redash setup script Slack notification functionality."""

    def test_script_has_setup_slack_notification_function(self):
        """Test that script has setup_slack_notification function."""
        import importlib.util

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert hasattr(module, "setup_slack_notification")

    def test_script_has_find_destination_by_name_function(self):
        """Test that script has find_destination_by_name helper function."""
        import importlib.util

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert hasattr(module, "find_destination_by_name")

    def test_script_has_find_subscription_by_destination_function(self):
        """Test that script has find_subscription_by_destination helper function."""
        import importlib.util

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert hasattr(module, "find_subscription_by_destination")

    def test_redash_client_has_destination_methods(self):
        """Test that RedashClient has destination-related methods."""
        import importlib.util

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        client_class = module.RedashClient
        assert hasattr(client_class, "get_destinations")
        assert hasattr(client_class, "create_destination")
        assert hasattr(client_class, "update_destination")
        assert hasattr(client_class, "remove_alert_subscription")

    def test_find_destination_by_name_finds_existing_destination(self):
        """Test that find_destination_by_name finds a destination by name."""
        import importlib.util

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        destinations = [
            {"id": 1, "name": "Email Alerts"},
            {"id": 2, "name": "Slack - Supply Chain Alerts"},
            {"id": 3, "name": "Webhook"},
        ]
        result = module.find_destination_by_name(destinations, "Slack - Supply Chain Alerts")
        assert result is not None
        assert result["id"] == 2

    def test_find_destination_by_name_returns_none_for_missing(self):
        """Test that find_destination_by_name returns None when destination not found."""
        import importlib.util

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        destinations = [
            {"id": 1, "name": "Email Alerts"},
            {"id": 2, "name": "Webhook"},
        ]
        result = module.find_destination_by_name(destinations, "Slack - Supply Chain Alerts")
        assert result is None

    def test_find_subscription_by_destination_finds_existing_subscription(self):
        """Test that find_subscription_by_destination finds a subscription by destination ID."""
        import importlib.util

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        subscriptions = [
            {"id": 1, "destination": {"id": 10, "name": "Email"}},
            {"id": 2, "destination": {"id": 20, "name": "Slack"}},
            {"id": 3, "destination": {"id": 30, "name": "Webhook"}},
        ]
        result = module.find_subscription_by_destination(subscriptions, 20)
        assert result is not None
        assert result["id"] == 2

    def test_find_subscription_by_destination_returns_none_for_missing(self):
        """Test that find_subscription_by_destination returns None when not found."""
        import importlib.util

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        subscriptions = [
            {"id": 1, "destination": {"id": 10, "name": "Email"}},
            {"id": 2, "destination": {"id": 20, "name": "Slack"}},
        ]
        result = module.find_subscription_by_destination(subscriptions, 99)
        assert result is None

    def test_find_subscription_by_destination_handles_missing_destination_key(self):
        """Test that find_subscription_by_destination handles missing destination key."""
        import importlib.util

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        subscriptions = [
            {"id": 1},  # No destination key
            {"id": 2, "destination": None},  # None destination
            {"id": 3, "destination": {"id": 30, "name": "Webhook"}},
        ]
        result = module.find_subscription_by_destination(subscriptions, 30)
        assert result is not None
        assert result["id"] == 3

    def test_find_destination_by_name_empty_list(self):
        """Test that find_destination_by_name handles empty list."""
        import importlib.util

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        result = module.find_destination_by_name([], "Any Name")
        assert result is None

    def test_find_subscription_by_destination_empty_list(self):
        """Test that find_subscription_by_destination handles empty list."""
        import importlib.util

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        result = module.find_subscription_by_destination([], 1)
        assert result is None


class TestRedashSetupScriptEmailNotification:
    """Tests for Redash setup script email notification functionality."""

    def test_script_has_setup_email_notification_function(self):
        """Test that script has setup_email_notification function."""
        import importlib.util

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert hasattr(module, "setup_email_notification")

    def test_setup_email_notification_uses_environment_variable(self):
        """Test that setup_email_notification uses ALERT_EMAIL_ADDRESSES env var."""
        import importlib.util
        import inspect

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Check function signature includes email_addresses parameter
        sig = inspect.signature(module.setup_email_notification)
        assert "email_addresses" in sig.parameters

        # Check function body references ALERT_EMAIL_ADDRESSES
        source = inspect.getsource(module.setup_email_notification)
        assert "ALERT_EMAIL_ADDRESSES" in source

    def test_setup_email_notification_creates_email_destination(self):
        """Test that setup_email_notification creates email destination type."""
        import importlib.util
        import inspect

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Check function creates email type destination
        source = inspect.getsource(module.setup_email_notification)
        assert 'destination_type="email"' in source or "destination_type='email'" in source

    def test_setup_email_notification_has_destination_name(self):
        """Test that setup_email_notification uses correct destination name."""
        import importlib.util
        import inspect

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Check function uses appropriate destination name
        source = inspect.getsource(module.setup_email_notification)
        assert "Email - Supply Chain Alerts" in source

    def test_setup_email_notification_uses_addresses_option(self):
        """Test that setup_email_notification passes addresses in options."""
        import importlib.util
        import inspect

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Check function uses "addresses" option key for email
        source = inspect.getsource(module.setup_email_notification)
        assert '"addresses"' in source or "'addresses'" in source

    def test_setup_email_notification_reuses_existing_destination(self):
        """Test that setup_email_notification reuses existing destination."""
        import importlib.util
        import inspect

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Check function looks for existing destinations
        source = inspect.getsource(module.setup_email_notification)
        assert "find_destination_by_name" in source
        assert "get_destinations" in source

    def test_setup_email_notification_checks_existing_subscription(self):
        """Test that setup_email_notification checks for existing subscription."""
        import importlib.util
        import inspect

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Check function looks for existing subscriptions
        source = inspect.getsource(module.setup_email_notification)
        assert "find_subscription_by_destination" in source
        assert "get_alert_subscriptions" in source

    def test_setup_email_notification_returns_none_without_config(self):
        """Test that setup_email_notification returns None when not configured."""
        import importlib.util
        import inspect

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Check function returns None early when no addresses configured
        source = inspect.getsource(module.setup_email_notification)
        assert "return None" in source
        assert "Skipping email notification" in source

    def test_main_calls_setup_email_notification(self):
        """Test that main() calls setup_email_notification."""
        import importlib.util
        import inspect

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Check main function calls setup_email_notification
        source = inspect.getsource(module.main)
        assert "setup_email_notification" in source

    def test_main_prints_email_env_var_hint(self):
        """Test that main() prints hint about ALERT_EMAIL_ADDRESSES env var."""
        import importlib.util
        import inspect

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Check main function mentions ALERT_EMAIL_ADDRESSES in next steps
        source = inspect.getsource(module.main)
        assert "ALERT_EMAIL_ADDRESSES" in source


# Fixtures for forecast queries
@pytest.fixture
def forecast_overview_query() -> str:
    """Load forecast overview SQL query."""
    query_path = SQL_DIR / "forecast_overview.sql"
    return query_path.read_text()


@pytest.fixture
def forecast_by_sku_query() -> str:
    """Load forecast by SKU SQL query."""
    query_path = SQL_DIR / "forecast_by_sku.sql"
    return query_path.read_text()


@pytest.fixture
def forecast_vs_actuals_query() -> str:
    """Load forecast vs actuals SQL query."""
    query_path = SQL_DIR / "forecast_vs_actuals.sql"
    return query_path.read_text()


class TestForecastOverviewQuery:
    """Tests for Forecast Overview query."""

    def test_query_file_exists(self, forecast_overview_query: str):
        """Test that forecast overview SQL file exists and has content."""
        assert len(forecast_overview_query) > 100

    def test_query_has_select(self, forecast_overview_query: str):
        """Test that query has SELECT statement."""
        assert "SELECT" in forecast_overview_query

    def test_query_uses_forecasts_table(self, forecast_overview_query: str):
        """Test that query uses forecasts table."""
        assert "forecasts" in forecast_overview_query

    def test_query_includes_sku(self, forecast_overview_query: str):
        """Test that query includes SKU column."""
        assert "p.sku" in forecast_overview_query

    def test_query_includes_forecast_date(self, forecast_overview_query: str):
        """Test that query includes forecast_date."""
        assert "forecast_date" in forecast_overview_query

    def test_query_includes_yhat(self, forecast_overview_query: str):
        """Test that query includes yhat (point forecast)."""
        assert "yhat" in forecast_overview_query.lower()

    def test_query_includes_lower_bound(self, forecast_overview_query: str):
        """Test that query includes yhat_lower (lower bound)."""
        assert "yhat_lower" in forecast_overview_query or "lower_bound" in forecast_overview_query

    def test_query_includes_upper_bound(self, forecast_overview_query: str):
        """Test that query includes yhat_upper (upper bound)."""
        assert "yhat_upper" in forecast_overview_query or "upper_bound" in forecast_overview_query

    def test_query_filters_future_dates(self, forecast_overview_query: str):
        """Test that query filters for future forecast dates."""
        assert "NOW()" in forecast_overview_query

    def test_query_uses_latest_model(self, forecast_overview_query: str):
        """Test that query uses the most recent model training."""
        assert "MAX(model_trained_at)" in forecast_overview_query

    def test_query_joins_products(self, forecast_overview_query: str):
        """Test that query joins products table."""
        assert "JOIN products" in forecast_overview_query or "products p" in forecast_overview_query

    def test_query_has_order_by(self, forecast_overview_query: str):
        """Test that query has ORDER BY clause."""
        assert "ORDER BY" in forecast_overview_query


class TestForecastBySkuQuery:
    """Tests for Forecast by SKU query."""

    def test_query_file_exists(self, forecast_by_sku_query: str):
        """Test that forecast by SKU SQL file exists and has content."""
        assert len(forecast_by_sku_query) > 100

    def test_query_has_select(self, forecast_by_sku_query: str):
        """Test that query has SELECT statement."""
        assert "SELECT" in forecast_by_sku_query

    def test_query_uses_forecasts_table(self, forecast_by_sku_query: str):
        """Test that query uses forecasts table."""
        assert "forecasts" in forecast_by_sku_query

    def test_query_has_sku_parameter(self, forecast_by_sku_query: str):
        """Test that query has SKU parameter placeholder."""
        assert "{{ sku }}" in forecast_by_sku_query

    def test_query_includes_forecast_date(self, forecast_by_sku_query: str):
        """Test that query includes forecast_date."""
        assert "forecast_date" in forecast_by_sku_query

    def test_query_includes_forecast_value(self, forecast_by_sku_query: str):
        """Test that query includes forecast value."""
        assert "forecast" in forecast_by_sku_query.lower()

    def test_query_includes_confidence_bounds(self, forecast_by_sku_query: str):
        """Test that query includes confidence bounds."""
        assert "lower_bound" in forecast_by_sku_query or "yhat_lower" in forecast_by_sku_query
        assert "upper_bound" in forecast_by_sku_query or "yhat_upper" in forecast_by_sku_query

    def test_query_filters_future_dates(self, forecast_by_sku_query: str):
        """Test that query filters for future forecast dates."""
        assert "NOW()" in forecast_by_sku_query

    def test_query_uses_latest_model(self, forecast_by_sku_query: str):
        """Test that query uses the most recent model training."""
        assert "MAX(model_trained_at)" in forecast_by_sku_query

    def test_query_has_order_by(self, forecast_by_sku_query: str):
        """Test that query has ORDER BY clause."""
        assert "ORDER BY" in forecast_by_sku_query


class TestForecastVsActualsQuery:
    """Tests for Forecast vs Actuals comparison query."""

    def test_query_file_exists(self, forecast_vs_actuals_query: str):
        """Test that forecast vs actuals SQL file exists and has content."""
        assert len(forecast_vs_actuals_query) > 100

    def test_query_has_select(self, forecast_vs_actuals_query: str):
        """Test that query has SELECT statement."""
        assert "SELECT" in forecast_vs_actuals_query

    def test_query_uses_forecasts_table(self, forecast_vs_actuals_query: str):
        """Test that query uses forecasts table."""
        assert "forecasts" in forecast_vs_actuals_query

    def test_query_uses_inventory_events(self, forecast_vs_actuals_query: str):
        """Test that query uses inventory_events for actuals."""
        assert "inventory_events" in forecast_vs_actuals_query

    def test_query_has_cte_for_actuals(self, forecast_vs_actuals_query: str):
        """Test that query has CTE for actuals calculation."""
        assert "WITH" in forecast_vs_actuals_query
        assert "actuals" in forecast_vs_actuals_query

    def test_query_aggregates_by_week(self, forecast_vs_actuals_query: str):
        """Test that query aggregates by week."""
        assert "DATE_TRUNC" in forecast_vs_actuals_query
        assert "'week'" in forecast_vs_actuals_query

    def test_query_includes_actual_column(self, forecast_vs_actuals_query: str):
        """Test that query includes actual column."""
        assert "actual" in forecast_vs_actuals_query.lower()

    def test_query_includes_forecast_column(self, forecast_vs_actuals_query: str):
        """Test that query includes forecast column."""
        assert "forecast" in forecast_vs_actuals_query.lower()

    def test_query_calculates_error(self, forecast_vs_actuals_query: str):
        """Test that query calculates error percentage."""
        assert "error" in forecast_vs_actuals_query.lower()

    def test_query_filters_depletions(self, forecast_vs_actuals_query: str):
        """Test that query filters for depletion events."""
        assert "depletion" in forecast_vs_actuals_query

    def test_query_has_order_by(self, forecast_vs_actuals_query: str):
        """Test that query has ORDER BY clause."""
        assert "ORDER BY" in forecast_vs_actuals_query


class TestForecastSQLSyntax:
    """Tests for SQL syntax validation for forecast queries."""

    def test_forecast_overview_no_unclosed_strings(self, forecast_overview_query: str):
        """Test that forecast overview query has no unclosed strings."""
        clean = self._remove_comments(forecast_overview_query)
        quote_count = clean.count("'")
        assert quote_count % 2 == 0, "Unclosed string literal detected"

    def test_forecast_by_sku_no_unclosed_strings(self, forecast_by_sku_query: str):
        """Test that forecast by SKU query has no unclosed strings."""
        clean = self._remove_comments(forecast_by_sku_query)
        # Account for {{ sku }} Jinja template syntax
        clean = clean.replace("{{ sku }}", "''")
        quote_count = clean.count("'")
        assert quote_count % 2 == 0, "Unclosed string literal detected"

    def test_forecast_vs_actuals_no_unclosed_strings(self, forecast_vs_actuals_query: str):
        """Test that forecast vs actuals query has no unclosed strings."""
        clean = self._remove_comments(forecast_vs_actuals_query)
        quote_count = clean.count("'")
        assert quote_count % 2 == 0, "Unclosed string literal detected"

    def _remove_comments(self, sql: str) -> str:
        """Remove SQL comments from query."""
        import re
        return re.sub(r"--.*$", "", sql, flags=re.MULTILINE)

    def test_forecast_overview_balanced_parentheses(self, forecast_overview_query: str):
        """Test that forecast overview query has balanced parentheses."""
        clean = self._remove_strings_and_comments(forecast_overview_query)
        assert clean.count("(") == clean.count(")"), "Unbalanced parentheses detected"

    def test_forecast_by_sku_balanced_parentheses(self, forecast_by_sku_query: str):
        """Test that forecast by SKU query has balanced parentheses."""
        clean = self._remove_strings_and_comments(forecast_by_sku_query)
        assert clean.count("(") == clean.count(")"), "Unbalanced parentheses detected"

    def test_forecast_vs_actuals_balanced_parentheses(self, forecast_vs_actuals_query: str):
        """Test that forecast vs actuals query has balanced parentheses."""
        clean = self._remove_strings_and_comments(forecast_vs_actuals_query)
        assert clean.count("(") == clean.count(")"), "Unbalanced parentheses detected"

    def _remove_strings_and_comments(self, sql: str) -> str:
        """Remove string literals and comments from SQL for syntax checking."""
        import re

        # Remove single-line comments
        sql = re.sub(r"--.*$", "", sql, flags=re.MULTILINE)
        # Remove string literals (simplified - doesn't handle escaped quotes)
        sql = re.sub(r"'[^']*'", "''", sql)
        # Remove Jinja template syntax
        sql = re.sub(r"\{\{[^}]*\}\}", "''", sql)
        return sql


class TestRedashSetupScriptForecasts:
    """Tests for Redash setup script forecast functionality."""

    def test_script_has_forecast_overview_query(self):
        """Test that script contains forecast overview query."""
        import importlib.util

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert hasattr(module, "FORECAST_OVERVIEW_QUERY")
        query = module.FORECAST_OVERVIEW_QUERY
        assert "SELECT" in query
        assert "forecasts" in query

    def test_script_has_forecast_by_sku_query(self):
        """Test that script contains forecast by SKU query."""
        import importlib.util

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert hasattr(module, "FORECAST_BY_SKU_QUERY")
        query = module.FORECAST_BY_SKU_QUERY
        assert "SELECT" in query
        assert "{{ sku }}" in query

    def test_script_has_forecast_vs_actuals_query(self):
        """Test that script contains forecast vs actuals query."""
        import importlib.util

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert hasattr(module, "FORECAST_VS_ACTUALS_QUERY")
        query = module.FORECAST_VS_ACTUALS_QUERY
        assert "SELECT" in query
        assert "actuals" in query

    def test_script_has_setup_forecast_queries_function(self):
        """Test that script has setup_forecast_queries function."""
        import importlib.util

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert hasattr(module, "setup_forecast_queries")

    def test_script_has_setup_forecast_visualizations_function(self):
        """Test that script has setup_forecast_visualizations function."""
        import importlib.util

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert hasattr(module, "setup_forecast_visualizations")

    def test_main_calls_setup_forecast_queries(self):
        """Test that main() calls setup_forecast_queries."""
        import importlib.util
        import inspect

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        source = inspect.getsource(module.main)
        assert "setup_forecast_queries" in source

    def test_main_calls_setup_forecast_visualizations(self):
        """Test that main() calls setup_forecast_visualizations."""
        import importlib.util
        import inspect

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        source = inspect.getsource(module.main)
        assert "setup_forecast_visualizations" in source


class TestForecastVisualizationConfig:
    """Tests for forecast visualization configuration."""

    def test_setup_forecast_visualizations_creates_line_chart(self):
        """Test that setup_forecast_visualizations creates line chart type."""
        import importlib.util
        import inspect

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        source = inspect.getsource(module.setup_forecast_visualizations)
        assert "line" in source.lower()

    def test_setup_forecast_visualizations_uses_datetime_xaxis(self):
        """Test that setup_forecast_visualizations uses datetime x-axis."""
        import importlib.util
        import inspect

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        source = inspect.getsource(module.setup_forecast_visualizations)
        assert "datetime" in source.lower()

    def test_setup_forecast_visualizations_maps_forecast_columns(self):
        """Test that setup_forecast_visualizations maps forecast columns."""
        import importlib.util
        import inspect

        script_path = Path(__file__).parent.parent / "scripts" / "setup_redash_dashboard.py"
        spec = importlib.util.spec_from_file_location("setup_redash_dashboard", script_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        source = inspect.getsource(module.setup_forecast_visualizations)
        assert "forecast_date" in source or "forecast" in source
