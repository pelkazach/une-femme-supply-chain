"""Tests for inventory API endpoints."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

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
