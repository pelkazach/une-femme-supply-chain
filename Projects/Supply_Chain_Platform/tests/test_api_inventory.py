"""Tests for inventory API endpoints."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.inventory import parse_velocity_report, SkuVelocity
from src.database import get_db
from src.main import app
from src.services.winedirect import WineDirectAPIError, WineDirectAuthError


@pytest.fixture
def sync_client() -> TestClient:
    """Create a sync test client for simple tests."""
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_check(self, sync_client: TestClient) -> None:
        """Test health check returns healthy status."""
        response = sync_client.get("/health")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "healthy"}


class TestGetSellableInventory:
    """Tests for GET /inventory/sellable endpoint."""

    def test_get_sellable_inventory_success(self) -> None:
        """Test successful retrieval of sellable inventory."""
        mock_winedirect_inventory = [
            {"sku": "UFBub250", "quantity": 100, "pool": "pool1", "warehouse": "WH1"},
            {"sku": "UFRos250", "quantity": 50, "pool": "pool1", "warehouse": "WH1"},
            {"sku": "UFRed250", "quantity": 75, "pool": "pool2", "warehouse": "WH2"},
            {"sku": "UFCha250", "quantity": 25, "pool": "pool1", "warehouse": "WH1"},
            {"sku": "OTHER_SKU", "quantity": 200, "pool": "pool1", "warehouse": "WH1"},
        ]

        # Create mock database session
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("UFBub250",),
            ("UFRos250",),
            ("UFRed250",),
            ("UFCha250",),
        ]

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.inventory.WineDirectClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get_sellable_inventory.return_value = (
                    mock_winedirect_inventory
                )
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                client = TestClient(app)
                response = client.get("/inventory/sellable")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert "items" in data
                assert "total_items" in data
                # Should only include tracked SKUs (4 items, not OTHER_SKU)
                assert data["total_items"] == 4
                skus = [item["sku"] for item in data["items"]]
                assert "UFBub250" in skus
                assert "UFRos250" in skus
                assert "UFRed250" in skus
                assert "UFCha250" in skus
                assert "OTHER_SKU" not in skus
        finally:
            app.dependency_overrides.clear()

    def test_get_sellable_inventory_auth_error(self) -> None:
        """Test handling of WineDirect authentication error."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("UFBub250",)]

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.inventory.WineDirectClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get_sellable_inventory.side_effect = WineDirectAuthError(
                    "Invalid credentials"
                )
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                client = TestClient(app)
                response = client.get("/inventory/sellable")

                assert response.status_code == status.HTTP_401_UNAUTHORIZED
                assert "authentication failed" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()

    def test_get_sellable_inventory_api_error(self) -> None:
        """Test handling of WineDirect API error."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("UFBub250",)]

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.inventory.WineDirectClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get_sellable_inventory.side_effect = WineDirectAPIError(
                    "Server error"
                )
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                client = TestClient(app)
                response = client.get("/inventory/sellable")

                assert response.status_code == status.HTTP_502_BAD_GATEWAY
                assert "API error" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_get_sellable_inventory_empty(self) -> None:
        """Test handling when no tracked SKUs are in WineDirect."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("UFBub250",)]

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.inventory.WineDirectClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                # WineDirect returns inventory but none match our tracked SKUs
                mock_client.get_sellable_inventory.return_value = [
                    {"sku": "OTHER_SKU", "quantity": 100},
                ]
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                client = TestClient(app)
                response = client.get("/inventory/sellable")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["total_items"] == 0
                assert data["items"] == []
        finally:
            app.dependency_overrides.clear()


class TestGetSellableInventoryBySku:
    """Tests for GET /inventory/sellable/{sku} endpoint."""

    def test_get_inventory_by_sku_success(self) -> None:
        """Test successful retrieval of inventory for specific SKU."""
        winedirect_inventory = [
            {"sku": "UFBub250", "quantity": 100, "pool": "pool1", "warehouse": "WH1"},
            {"sku": "UFRos250", "quantity": 50, "pool": "pool1", "warehouse": "WH1"},
        ]

        mock_product = MagicMock()
        mock_product.sku = "UFBub250"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_product

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.inventory.WineDirectClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get_sellable_inventory.return_value = winedirect_inventory
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                client = TestClient(app)
                response = client.get("/inventory/sellable/UFBub250")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["sku"] == "UFBub250"
                assert data["quantity"] == 100
                assert data["pool"] == "pool1"
                assert data["warehouse"] == "WH1"
        finally:
            app.dependency_overrides.clear()

    def test_get_inventory_by_sku_not_tracked(self) -> None:
        """Test 404 when SKU is not tracked in the system."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            client = TestClient(app)
            response = client.get("/inventory/sellable/UNKNOWN_SKU")

            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "not tracked" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_get_inventory_by_sku_not_in_winedirect(self) -> None:
        """Test 404 when SKU exists in DB but not in WineDirect."""
        # WineDirect returns inventory without the requested SKU
        winedirect_inventory = [
            {"sku": "UFRos250", "quantity": 50, "pool": "pool1", "warehouse": "WH1"},
        ]

        mock_product = MagicMock()
        mock_product.sku = "UFBub250"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_product

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.inventory.WineDirectClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get_sellable_inventory.return_value = winedirect_inventory
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                client = TestClient(app)
                response = client.get("/inventory/sellable/UFBub250")

                assert response.status_code == status.HTTP_404_NOT_FOUND
                assert "not found in WineDirect" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_get_inventory_by_sku_auth_error(self) -> None:
        """Test handling of WineDirect authentication error for specific SKU."""
        mock_product = MagicMock()
        mock_product.sku = "UFBub250"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_product

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.inventory.WineDirectClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get_sellable_inventory.side_effect = WineDirectAuthError(
                    "Invalid credentials"
                )
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                client = TestClient(app)
                response = client.get("/inventory/sellable/UFBub250")

                assert response.status_code == status.HTTP_401_UNAUTHORIZED
        finally:
            app.dependency_overrides.clear()


class TestInventoryItemAltFields:
    """Tests for handling alternative field names in WineDirect responses."""

    def test_item_code_field(self) -> None:
        """Test handling of 'item_code' field instead of 'sku'."""
        winedirect_inventory = [
            {"item_code": "UFBub250", "quantity": 100, "location": "WH1"},
        ]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("UFBub250",)]

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.inventory.WineDirectClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get_sellable_inventory.return_value = winedirect_inventory
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                client = TestClient(app)
                response = client.get("/inventory/sellable")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["total_items"] == 1
                assert data["items"][0]["sku"] == "UFBub250"
                assert data["items"][0]["warehouse"] == "WH1"
        finally:
            app.dependency_overrides.clear()

    def test_product_code_field(self) -> None:
        """Test handling of 'product_code' field instead of 'sku'."""
        winedirect_inventory = [
            {"product_code": "UFBub250", "quantity": 100},
        ]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("UFBub250",)]

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.inventory.WineDirectClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get_sellable_inventory.return_value = winedirect_inventory
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                client = TestClient(app)
                response = client.get("/inventory/sellable")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["total_items"] == 1
                assert data["items"][0]["sku"] == "UFBub250"
        finally:
            app.dependency_overrides.clear()


class TestGetInventoryOut:
    """Tests for GET /inventory/out endpoint."""

    def test_get_inventory_out_success(self) -> None:
        """Test successful retrieval of depletion events."""
        now = datetime.now(UTC)
        mock_winedirect_events = [
            {
                "sku": "UFBub250",
                "quantity": 10,
                "timestamp": now.isoformat(),
                "order_id": "ORD-001",
                "customer": "Test Customer",
                "warehouse": "WH1",
            },
            {
                "sku": "UFRos250",
                "quantity": 5,
                "timestamp": (now - timedelta(hours=1)).isoformat(),
                "order_id": "ORD-002",
                "customer": "Another Customer",
                "warehouse": "WH1",
            },
            {
                "sku": "OTHER_SKU",
                "quantity": 100,
                "timestamp": now.isoformat(),
                "order_id": "ORD-003",
            },
        ]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("UFBub250",),
            ("UFRos250",),
            ("UFRed250",),
            ("UFCha250",),
        ]

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.inventory.WineDirectClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get_inventory_out.return_value = mock_winedirect_events
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                client = TestClient(app)
                response = client.get("/inventory/out")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert "events" in data
                assert "total_events" in data
                assert "start_date" in data
                assert "end_date" in data
                # Should only include tracked SKUs (2 events, not OTHER_SKU)
                assert data["total_events"] == 2
                skus = [event["sku"] for event in data["events"]]
                assert "UFBub250" in skus
                assert "UFRos250" in skus
                assert "OTHER_SKU" not in skus
                # Verify event structure
                event = data["events"][0]
                assert "quantity" in event
                assert "timestamp" in event
                assert "order_id" in event
        finally:
            app.dependency_overrides.clear()

    def test_get_inventory_out_with_date_range(self) -> None:
        """Test retrieval of depletion events with custom date range."""
        now = datetime.now(UTC)
        start = now - timedelta(days=7)
        end = now

        mock_winedirect_events = [
            {
                "sku": "UFBub250",
                "quantity": 10,
                "timestamp": (now - timedelta(days=3)).isoformat(),
            },
        ]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("UFBub250",)]

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.inventory.WineDirectClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get_inventory_out.return_value = mock_winedirect_events
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                client = TestClient(app)
                response = client.get(
                    "/inventory/out",
                    params={
                        "start_date": start.isoformat(),
                        "end_date": end.isoformat(),
                    },
                )

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["total_events"] == 1

                # Verify the client was called with the provided dates
                call_args = mock_client.get_inventory_out.call_args
                assert call_args is not None
        finally:
            app.dependency_overrides.clear()

    def test_get_inventory_out_auth_error(self) -> None:
        """Test handling of WineDirect authentication error."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("UFBub250",)]

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.inventory.WineDirectClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get_inventory_out.side_effect = WineDirectAuthError(
                    "Invalid credentials"
                )
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                client = TestClient(app)
                response = client.get("/inventory/out")

                assert response.status_code == status.HTTP_401_UNAUTHORIZED
                assert "authentication failed" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()

    def test_get_inventory_out_api_error(self) -> None:
        """Test handling of WineDirect API error."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("UFBub250",)]

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.inventory.WineDirectClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get_inventory_out.side_effect = WineDirectAPIError(
                    "Server error"
                )
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                client = TestClient(app)
                response = client.get("/inventory/out")

                assert response.status_code == status.HTTP_502_BAD_GATEWAY
                assert "API error" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_get_inventory_out_empty(self) -> None:
        """Test handling when no tracked SKUs are in depletion events."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("UFBub250",)]

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.inventory.WineDirectClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                # WineDirect returns events but none match our tracked SKUs
                mock_client.get_inventory_out.return_value = [
                    {"sku": "OTHER_SKU", "quantity": 100, "timestamp": datetime.now(UTC).isoformat()},
                ]
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                client = TestClient(app)
                response = client.get("/inventory/out")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["total_events"] == 0
                assert data["events"] == []
        finally:
            app.dependency_overrides.clear()

    def test_get_inventory_out_alternative_field_names(self) -> None:
        """Test handling of alternative field names in depletion events."""
        now = datetime.now(UTC)
        mock_winedirect_events = [
            {
                "item_code": "UFBub250",
                "quantity": 10,
                "date": now.isoformat(),
                "order_number": "ORD-001",
                "customer_name": "Test Customer",
                "location": "WH1",
            },
        ]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("UFBub250",)]

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.inventory.WineDirectClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get_inventory_out.return_value = mock_winedirect_events
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                client = TestClient(app)
                response = client.get("/inventory/out")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["total_events"] == 1
                event = data["events"][0]
                assert event["sku"] == "UFBub250"
                assert event["order_id"] == "ORD-001"
                assert event["customer"] == "Test Customer"
                assert event["warehouse"] == "WH1"
        finally:
            app.dependency_overrides.clear()

    def test_get_inventory_out_datetime_object_in_response(self) -> None:
        """Test handling when WineDirect returns datetime objects instead of strings."""
        now = datetime.now(UTC)
        mock_winedirect_events = [
            {
                "sku": "UFBub250",
                "quantity": 10,
                "timestamp": now,  # datetime object, not string
            },
        ]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("UFBub250",)]

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.inventory.WineDirectClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get_inventory_out.return_value = mock_winedirect_events
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                client = TestClient(app)
                response = client.get("/inventory/out")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["total_events"] == 1
                assert "timestamp" in data["events"][0]
        finally:
            app.dependency_overrides.clear()

    def test_get_inventory_out_z_suffix_timestamp(self) -> None:
        """Test handling of timestamps with Z suffix."""
        mock_winedirect_events = [
            {
                "sku": "UFBub250",
                "quantity": 10,
                "timestamp": "2026-02-03T12:00:00Z",  # Z suffix for UTC
            },
        ]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("UFBub250",)]

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.inventory.WineDirectClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get_inventory_out.return_value = mock_winedirect_events
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                client = TestClient(app)
                response = client.get("/inventory/out")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["total_events"] == 1
        finally:
            app.dependency_overrides.clear()


class TestParseVelocityReport:
    """Tests for parse_velocity_report function."""

    def test_parse_velocity_report_with_skus_key(self) -> None:
        """Test parsing velocity report with 'skus' key."""
        raw_report = {
            "period_days": 30,
            "skus": [
                {"sku": "UFBub250", "units_per_day": 5.2, "total_units": 156},
                {"sku": "UFRos250", "units_per_day": 3.1, "total_units": 93},
                {"sku": "OTHER_SKU", "units_per_day": 10.0, "total_units": 300},
            ],
        }
        tracked_skus = {"UFBub250", "UFRos250", "UFRed250", "UFCha250"}

        result = parse_velocity_report(raw_report, tracked_skus, period_days=30)

        assert len(result) == 2
        skus = {v.sku for v in result}
        assert "UFBub250" in skus
        assert "UFRos250" in skus
        assert "OTHER_SKU" not in skus

        # Find UFBub250 and verify values
        bub = next(v for v in result if v.sku == "UFBub250")
        assert bub.units_per_day == 5.2
        assert bub.total_units == 156
        assert bub.period_days == 30

    def test_parse_velocity_report_with_data_key(self) -> None:
        """Test parsing velocity report with 'data' key."""
        raw_report = {
            "data": [
                {"sku": "UFBub250", "velocity": 4.5, "quantity": 135},
            ],
        }
        tracked_skus = {"UFBub250"}

        result = parse_velocity_report(raw_report, tracked_skus, period_days=30)

        assert len(result) == 1
        assert result[0].sku == "UFBub250"
        assert result[0].units_per_day == 4.5
        assert result[0].total_units == 135

    def test_parse_velocity_report_as_list(self) -> None:
        """Test parsing velocity report when response is a direct list."""
        raw_report = [
            {"sku": "UFBub250", "rate": 6.0, "total_quantity": 180},
        ]
        tracked_skus = {"UFBub250"}

        result = parse_velocity_report(raw_report, tracked_skus, period_days=30)

        assert len(result) == 1
        assert result[0].units_per_day == 6.0
        assert result[0].total_units == 180

    def test_parse_velocity_report_alternative_sku_field(self) -> None:
        """Test parsing with alternative SKU field names."""
        raw_report = {
            "skus": [
                {"item_code": "UFBub250", "depletion_rate": 5.0, "units": 150},
            ],
        }
        tracked_skus = {"UFBub250"}

        result = parse_velocity_report(raw_report, tracked_skus, period_days=30)

        assert len(result) == 1
        assert result[0].sku == "UFBub250"
        assert result[0].units_per_day == 5.0

    def test_parse_velocity_report_calculates_rate_from_total(self) -> None:
        """Test that units_per_day is calculated if only total_units provided."""
        raw_report = {
            "skus": [
                {"sku": "UFBub250", "total_units": 150},  # No rate provided
            ],
        }
        tracked_skus = {"UFBub250"}

        result = parse_velocity_report(raw_report, tracked_skus, period_days=30)

        assert len(result) == 1
        assert result[0].units_per_day == 5.0  # 150 / 30 = 5.0

    def test_parse_velocity_report_calculates_total_from_rate(self) -> None:
        """Test that total_units is calculated if only units_per_day provided."""
        raw_report = {
            "skus": [
                {"sku": "UFBub250", "units_per_day": 5.0},  # No total provided
            ],
        }
        tracked_skus = {"UFBub250"}

        result = parse_velocity_report(raw_report, tracked_skus, period_days=30)

        assert len(result) == 1
        assert result[0].total_units == 150  # 5.0 * 30 = 150

    def test_parse_velocity_report_skips_sku_without_data(self) -> None:
        """Test that SKUs without velocity data are skipped."""
        raw_report = {
            "skus": [
                {"sku": "UFBub250"},  # No rate or total
                {"sku": "UFRos250", "units_per_day": 3.0, "total_units": 90},
            ],
        }
        tracked_skus = {"UFBub250", "UFRos250"}

        result = parse_velocity_report(raw_report, tracked_skus, period_days=30)

        assert len(result) == 1
        assert result[0].sku == "UFRos250"

    def test_parse_velocity_report_empty_response(self) -> None:
        """Test parsing empty velocity report."""
        raw_report: dict[str, list[dict[str, str]]] = {"skus": []}
        tracked_skus = {"UFBub250"}

        result = parse_velocity_report(raw_report, tracked_skus, period_days=30)

        assert len(result) == 0

    def test_parse_velocity_report_rounds_rate(self) -> None:
        """Test that units_per_day is rounded to 2 decimal places."""
        raw_report = {
            "skus": [
                {"sku": "UFBub250", "units_per_day": 5.12345},
            ],
        }
        tracked_skus = {"UFBub250"}

        result = parse_velocity_report(raw_report, tracked_skus, period_days=30)

        assert result[0].units_per_day == 5.12


class TestGetVelocityReport:
    """Tests for GET /inventory/velocity endpoint."""

    def test_get_velocity_report_success(self) -> None:
        """Test successful retrieval of velocity report."""
        mock_winedirect_report = {
            "period_days": 30,
            "skus": [
                {"sku": "UFBub250", "units_per_day": 5.2, "total_units": 156},
                {"sku": "UFRos250", "units_per_day": 3.1, "total_units": 93},
                {"sku": "OTHER_SKU", "units_per_day": 10.0, "total_units": 300},
            ],
        }

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("UFBub250",),
            ("UFRos250",),
            ("UFRed250",),
            ("UFCha250",),
        ]

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.inventory.WineDirectClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get_velocity_report.return_value = mock_winedirect_report
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                client = TestClient(app)
                response = client.get("/inventory/velocity")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["period_days"] == 30
                assert data["total_skus"] == 2
                assert "velocities" in data

                skus = [v["sku"] for v in data["velocities"]]
                assert "UFBub250" in skus
                assert "UFRos250" in skus
                assert "OTHER_SKU" not in skus
        finally:
            app.dependency_overrides.clear()

    def test_get_velocity_report_with_period(self) -> None:
        """Test velocity report with custom period parameter."""
        mock_winedirect_report = {
            "period_days": 90,
            "skus": [
                {"sku": "UFBub250", "units_per_day": 4.8, "total_units": 432},
            ],
        }

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("UFBub250",)]

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.inventory.WineDirectClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get_velocity_report.return_value = mock_winedirect_report
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                client = TestClient(app)
                response = client.get("/inventory/velocity", params={"period": 90})

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["period_days"] == 90

                # Verify the client was called with period=90
                mock_client.get_velocity_report.assert_called_once_with(days=90)
        finally:
            app.dependency_overrides.clear()

    def test_get_velocity_report_invalid_period(self) -> None:
        """Test velocity report with invalid period parameter."""
        client = TestClient(app)
        response = client.get("/inventory/velocity", params={"period": 45})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_velocity_report_auth_error(self) -> None:
        """Test handling of WineDirect authentication error."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("UFBub250",)]

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.inventory.WineDirectClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get_velocity_report.side_effect = WineDirectAuthError(
                    "Invalid credentials"
                )
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                client = TestClient(app)
                response = client.get("/inventory/velocity")

                assert response.status_code == status.HTTP_401_UNAUTHORIZED
                assert "authentication failed" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()

    def test_get_velocity_report_api_error(self) -> None:
        """Test handling of WineDirect API error."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("UFBub250",)]

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.inventory.WineDirectClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get_velocity_report.side_effect = WineDirectAPIError(
                    "Server error"
                )
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                client = TestClient(app)
                response = client.get("/inventory/velocity")

                assert response.status_code == status.HTTP_502_BAD_GATEWAY
                assert "API error" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_get_velocity_report_empty(self) -> None:
        """Test handling when no tracked SKUs are in velocity report."""
        mock_winedirect_report = {
            "period_days": 30,
            "skus": [
                {"sku": "OTHER_SKU", "units_per_day": 10.0, "total_units": 300},
            ],
        }

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("UFBub250",)]

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.inventory.WineDirectClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get_velocity_report.return_value = mock_winedirect_report
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                client = TestClient(app)
                response = client.get("/inventory/velocity")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["total_skus"] == 0
                assert data["velocities"] == []
        finally:
            app.dependency_overrides.clear()


class TestGetVelocityBySku:
    """Tests for GET /inventory/velocity/{sku} endpoint."""

    def test_get_velocity_by_sku_success(self) -> None:
        """Test successful retrieval of velocity for specific SKU."""
        mock_winedirect_report = {
            "period_days": 30,
            "skus": [
                {"sku": "UFBub250", "units_per_day": 5.2, "total_units": 156},
                {"sku": "UFRos250", "units_per_day": 3.1, "total_units": 93},
            ],
        }

        mock_product = MagicMock()
        mock_product.sku = "UFBub250"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_product

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.inventory.WineDirectClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get_velocity_report.return_value = mock_winedirect_report
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                client = TestClient(app)
                response = client.get("/inventory/velocity/UFBub250")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["sku"] == "UFBub250"
                assert data["units_per_day"] == 5.2
                assert data["total_units"] == 156
                assert data["period_days"] == 30
        finally:
            app.dependency_overrides.clear()

    def test_get_velocity_by_sku_not_tracked(self) -> None:
        """Test 404 when SKU is not tracked in the system."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            client = TestClient(app)
            response = client.get("/inventory/velocity/UNKNOWN_SKU")

            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "not tracked" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_get_velocity_by_sku_not_in_report(self) -> None:
        """Test 404 when SKU exists in DB but not in velocity report."""
        mock_winedirect_report = {
            "period_days": 30,
            "skus": [
                {"sku": "UFRos250", "units_per_day": 3.1, "total_units": 93},
            ],
        }

        mock_product = MagicMock()
        mock_product.sku = "UFBub250"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_product

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.inventory.WineDirectClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get_velocity_report.return_value = mock_winedirect_report
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                client = TestClient(app)
                response = client.get("/inventory/velocity/UFBub250")

                assert response.status_code == status.HTTP_404_NOT_FOUND
                assert "not found in WineDirect" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_get_velocity_by_sku_with_period(self) -> None:
        """Test velocity by SKU with custom period parameter."""
        mock_winedirect_report = {
            "period_days": 60,
            "skus": [
                {"sku": "UFBub250", "units_per_day": 5.0, "total_units": 300},
            ],
        }

        mock_product = MagicMock()
        mock_product.sku = "UFBub250"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_product

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.inventory.WineDirectClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get_velocity_report.return_value = mock_winedirect_report
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                client = TestClient(app)
                response = client.get(
                    "/inventory/velocity/UFBub250",
                    params={"period": 60},
                )

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["period_days"] == 60

                mock_client.get_velocity_report.assert_called_once_with(days=60)
        finally:
            app.dependency_overrides.clear()

    def test_get_velocity_by_sku_auth_error(self) -> None:
        """Test handling of WineDirect authentication error for specific SKU."""
        mock_product = MagicMock()
        mock_product.sku = "UFBub250"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_product

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.inventory.WineDirectClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get_velocity_report.side_effect = WineDirectAuthError(
                    "Invalid credentials"
                )
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                client = TestClient(app)
                response = client.get("/inventory/velocity/UFBub250")

                assert response.status_code == status.HTTP_401_UNAUTHORIZED
        finally:
            app.dependency_overrides.clear()
