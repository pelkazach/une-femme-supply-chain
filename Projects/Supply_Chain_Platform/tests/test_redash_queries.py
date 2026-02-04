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
