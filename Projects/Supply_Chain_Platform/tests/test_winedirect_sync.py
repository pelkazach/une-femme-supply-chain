"""Tests for WineDirect sync Celery task."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tasks.winedirect_sync import (
    DEFAULT_WAREHOUSE_CODE,
    TRACKED_SKUS,
    _async_sync_winedirect,
    get_or_create_warehouse,
    get_sku_id_map,
    sync_depletion_events,
    sync_inventory_positions,
    sync_winedirect_inventory,
)


class MockProduct:
    """Mock Product for testing."""

    def __init__(self, sku: str, id: uuid.UUID):
        self.sku = sku
        self.id = id


class MockWarehouse:
    """Mock Warehouse for testing."""

    def __init__(self, code: str, id: uuid.UUID):
        self.code = code
        self.id = id


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock async database session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def sku_map() -> dict[str, uuid.UUID]:
    """Create a SKU to UUID mapping for testing."""
    return {
        "UFBub250": uuid.uuid4(),
        "UFRos250": uuid.uuid4(),
        "UFRed250": uuid.uuid4(),
        "UFCha250": uuid.uuid4(),
    }


@pytest.fixture
def warehouse_id() -> uuid.UUID:
    """Create a warehouse UUID for testing."""
    return uuid.uuid4()


class TestGetOrCreateWarehouse:
    """Tests for get_or_create_warehouse function."""

    async def test_returns_existing_warehouse(self, mock_session: AsyncMock) -> None:
        """Test that existing warehouse is returned."""
        existing_id = uuid.uuid4()
        mock_warehouse = MockWarehouse(code="WH01", id=existing_id)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_warehouse
        mock_session.execute.return_value = mock_result

        result = await get_or_create_warehouse(mock_session, "WH01", "Warehouse 1")

        assert result == existing_id
        mock_session.add.assert_not_called()

    async def test_creates_new_warehouse(self, mock_session: AsyncMock) -> None:
        """Test that new warehouse is created when not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        # The function creates a new warehouse and flushes
        await get_or_create_warehouse(mock_session, "WH02", "Warehouse 2")

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()


class TestGetSkuIdMap:
    """Tests for get_sku_id_map function."""

    async def test_returns_sku_mapping(self, mock_session: AsyncMock) -> None:
        """Test that SKU to ID mapping is returned."""
        sku_rows = [
            MagicMock(sku="UFBub250", id=uuid.uuid4()),
            MagicMock(sku="UFRos250", id=uuid.uuid4()),
        ]

        mock_result = MagicMock()
        mock_result.__iter__ = lambda self: iter(sku_rows)
        mock_session.execute.return_value = mock_result

        result = await get_sku_id_map(mock_session)

        assert len(result) == 2
        assert "UFBub250" in result
        assert "UFRos250" in result


class TestSyncInventoryPositions:
    """Tests for sync_inventory_positions function."""

    async def test_creates_inventory_events(
        self,
        mock_session: AsyncMock,
        sku_map: dict[str, uuid.UUID],
        warehouse_id: uuid.UUID,
    ) -> None:
        """Test that inventory events are created from API data."""
        mock_client = AsyncMock()
        mock_client.get_sellable_inventory.return_value = [
            {"sku": "UFBub250", "quantity": 100},
            {"sku": "UFRos250", "quantity": 50},
        ]

        sync_time = datetime.now(UTC)
        count = await sync_inventory_positions(
            mock_session, mock_client, sku_map, warehouse_id, sync_time
        )

        assert count == 2
        assert mock_session.add.call_count == 2

    async def test_filters_untracked_skus(
        self,
        mock_session: AsyncMock,
        sku_map: dict[str, uuid.UUID],
        warehouse_id: uuid.UUID,
    ) -> None:
        """Test that untracked SKUs are filtered out."""
        mock_client = AsyncMock()
        mock_client.get_sellable_inventory.return_value = [
            {"sku": "UFBub250", "quantity": 100},
            {"sku": "UNKNOWN_SKU", "quantity": 50},
        ]

        sync_time = datetime.now(UTC)
        count = await sync_inventory_positions(
            mock_session, mock_client, sku_map, warehouse_id, sync_time
        )

        assert count == 1
        assert mock_session.add.call_count == 1

    async def test_handles_alternative_field_names(
        self,
        mock_session: AsyncMock,
        sku_map: dict[str, uuid.UUID],
        warehouse_id: uuid.UUID,
    ) -> None:
        """Test that alternative field names are handled."""
        mock_client = AsyncMock()
        mock_client.get_sellable_inventory.return_value = [
            {"item_code": "UFBub250", "qty": 100},
            {"product_code": "UFRos250", "available": 50},
        ]

        sync_time = datetime.now(UTC)
        count = await sync_inventory_positions(
            mock_session, mock_client, sku_map, warehouse_id, sync_time
        )

        assert count == 2

    async def test_handles_empty_inventory(
        self,
        mock_session: AsyncMock,
        sku_map: dict[str, uuid.UUID],
        warehouse_id: uuid.UUID,
    ) -> None:
        """Test that empty inventory list is handled."""
        mock_client = AsyncMock()
        mock_client.get_sellable_inventory.return_value = []

        sync_time = datetime.now(UTC)
        count = await sync_inventory_positions(
            mock_session, mock_client, sku_map, warehouse_id, sync_time
        )

        assert count == 0
        mock_session.add.assert_not_called()


class TestSyncDepletionEvents:
    """Tests for sync_depletion_events function."""

    async def test_creates_depletion_events(
        self,
        mock_session: AsyncMock,
        sku_map: dict[str, uuid.UUID],
        warehouse_id: uuid.UUID,
    ) -> None:
        """Test that depletion events are created from API data."""
        mock_client = AsyncMock()
        mock_client.get_inventory_out.return_value = [
            {"sku": "UFBub250", "quantity": 10, "timestamp": "2026-02-03T10:00:00Z"},
            {"sku": "UFRos250", "quantity": 5, "timestamp": "2026-02-03T11:00:00Z"},
        ]

        since = datetime.now(UTC) - timedelta(hours=24)
        count = await sync_depletion_events(
            mock_session, mock_client, sku_map, warehouse_id, since
        )

        assert count == 2
        assert mock_session.add.call_count == 2

    async def test_filters_untracked_skus(
        self,
        mock_session: AsyncMock,
        sku_map: dict[str, uuid.UUID],
        warehouse_id: uuid.UUID,
    ) -> None:
        """Test that untracked SKUs are filtered out."""
        mock_client = AsyncMock()
        mock_client.get_inventory_out.return_value = [
            {"sku": "UFBub250", "quantity": 10, "timestamp": "2026-02-03T10:00:00Z"},
            {"sku": "OTHER_SKU", "quantity": 5, "timestamp": "2026-02-03T11:00:00Z"},
        ]

        since = datetime.now(UTC) - timedelta(hours=24)
        count = await sync_depletion_events(
            mock_session, mock_client, sku_map, warehouse_id, since
        )

        assert count == 1

    async def test_handles_alternative_field_names(
        self,
        mock_session: AsyncMock,
        sku_map: dict[str, uuid.UUID],
        warehouse_id: uuid.UUID,
    ) -> None:
        """Test that alternative field names are handled."""
        mock_client = AsyncMock()
        mock_client.get_inventory_out.return_value = [
            {"item_code": "UFBub250", "qty": 10, "event_date": "2026-02-03T10:00:00Z"},
            {"product_code": "UFRos250", "quantity": 5, "transaction_date": "2026-02-03T11:00:00+00:00"},
        ]

        since = datetime.now(UTC) - timedelta(hours=24)
        count = await sync_depletion_events(
            mock_session, mock_client, sku_map, warehouse_id, since
        )

        assert count == 2

    async def test_handles_datetime_objects(
        self,
        mock_session: AsyncMock,
        sku_map: dict[str, uuid.UUID],
        warehouse_id: uuid.UUID,
    ) -> None:
        """Test that datetime objects are handled correctly."""
        mock_client = AsyncMock()
        mock_client.get_inventory_out.return_value = [
            {"sku": "UFBub250", "quantity": 10, "timestamp": datetime(2026, 2, 3, 10, 0, 0, tzinfo=UTC)},
        ]

        since = datetime.now(UTC) - timedelta(hours=24)
        count = await sync_depletion_events(
            mock_session, mock_client, sku_map, warehouse_id, since
        )

        assert count == 1

    async def test_converts_negative_quantities(
        self,
        mock_session: AsyncMock,
        sku_map: dict[str, uuid.UUID],
        warehouse_id: uuid.UUID,
    ) -> None:
        """Test that negative quantities are converted to positive."""
        mock_client = AsyncMock()
        mock_client.get_inventory_out.return_value = [
            {"sku": "UFBub250", "quantity": -10, "timestamp": "2026-02-03T10:00:00Z"},
        ]

        since = datetime.now(UTC) - timedelta(hours=24)
        await sync_depletion_events(
            mock_session, mock_client, sku_map, warehouse_id, since
        )

        # Verify the event was added with positive quantity
        call_args = mock_session.add.call_args
        event = call_args[0][0]
        assert event.quantity == 10


class TestAsyncSyncWineDirect:
    """Tests for _async_sync_winedirect function."""

    @patch("src.tasks.winedirect_sync.create_async_engine")
    @patch("src.tasks.winedirect_sync.WineDirectClient")
    async def test_successful_sync(
        self, mock_client_cls: MagicMock, mock_engine: MagicMock
    ) -> None:
        """Test successful full sync."""
        # Setup mock engine and session
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.flush = AsyncMock()

        # Mock warehouse lookup
        mock_warehouse = MockWarehouse(code=DEFAULT_WAREHOUSE_CODE, id=uuid.uuid4())
        warehouse_result = MagicMock()
        warehouse_result.scalar_one_or_none.return_value = mock_warehouse

        # Mock SKU lookup
        sku_rows = [
            MagicMock(sku="UFBub250", id=uuid.uuid4()),
            MagicMock(sku="UFRos250", id=uuid.uuid4()),
        ]
        sku_result = MagicMock()
        sku_result.__iter__ = lambda self: iter(sku_rows)

        mock_session.execute = AsyncMock(side_effect=[warehouse_result, sku_result])

        # Setup session factory
        mock_session_factory = MagicMock()
        mock_session_factory.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.__aexit__ = AsyncMock(return_value=None)

        # Setup engine mock
        mock_engine_instance = MagicMock()
        mock_engine_instance.dispose = AsyncMock()
        mock_engine.return_value = mock_engine_instance

        # Setup client mock
        mock_client = AsyncMock()
        mock_client.get_sellable_inventory.return_value = [
            {"sku": "UFBub250", "quantity": 100},
        ]
        mock_client.get_inventory_out.return_value = [
            {"sku": "UFBub250", "quantity": 10, "timestamp": "2026-02-03T10:00:00Z"},
        ]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        with patch(
            "src.tasks.winedirect_sync.async_sessionmaker", return_value=lambda: mock_session_factory
        ):
            result = await _async_sync_winedirect()

        assert result["status"] == "success"
        assert result["inventory_events"] == 1
        assert result["depletion_events"] == 1
        assert result["errors"] == []

    @patch("src.tasks.winedirect_sync.create_async_engine")
    @patch("src.tasks.winedirect_sync.WineDirectClient")
    async def test_auth_error(
        self, mock_client_cls: MagicMock, mock_engine: MagicMock
    ) -> None:
        """Test handling of authentication error."""
        from src.services.winedirect import WineDirectAuthError

        # Setup mock engine
        mock_engine_instance = MagicMock()
        mock_engine_instance.dispose = AsyncMock()
        mock_engine.return_value = mock_engine_instance

        # Setup client to raise auth error
        mock_client_cls.return_value.__aenter__ = AsyncMock(
            side_effect=WineDirectAuthError("Invalid credentials")
        )

        # Setup mock session
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.flush = AsyncMock()

        mock_warehouse = MockWarehouse(code=DEFAULT_WAREHOUSE_CODE, id=uuid.uuid4())
        warehouse_result = MagicMock()
        warehouse_result.scalar_one_or_none.return_value = mock_warehouse

        sku_rows = [MagicMock(sku="UFBub250", id=uuid.uuid4())]
        sku_result = MagicMock()
        sku_result.__iter__ = lambda self: iter(sku_rows)

        mock_session.execute = AsyncMock(side_effect=[warehouse_result, sku_result])

        mock_session_factory = MagicMock()
        mock_session_factory.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.tasks.winedirect_sync.async_sessionmaker", return_value=lambda: mock_session_factory
        ):
            result = await _async_sync_winedirect()

        assert result["status"] == "error"
        assert len(result["errors"]) > 0
        assert "Authentication" in result["errors"][0]


class TestSyncWineDirectInventoryTask:
    """Tests for the Celery task."""

    @patch("src.tasks.winedirect_sync.asyncio.run")
    def test_task_calls_async_sync(self, mock_asyncio_run: MagicMock) -> None:
        """Test that Celery task calls the async sync function."""
        expected_result = {
            "status": "success",
            "sync_time": datetime.now(UTC).isoformat(),
            "inventory_events": 5,
            "depletion_events": 3,
            "errors": [],
        }
        mock_asyncio_run.return_value = expected_result

        # Call the task directly (Celery binds self automatically)
        result = sync_winedirect_inventory.run()

        assert result["status"] == "success"
        assert result["inventory_events"] == 5
        assert result["depletion_events"] == 3
        mock_asyncio_run.assert_called_once()


class TestTrackedSkus:
    """Tests for TRACKED_SKUS constant."""

    def test_tracked_skus_contains_four_products(self) -> None:
        """Test that TRACKED_SKUS contains all 4 Une Femme products."""
        assert len(TRACKED_SKUS) == 4
        assert "UFBub250" in TRACKED_SKUS
        assert "UFRos250" in TRACKED_SKUS
        assert "UFRed250" in TRACKED_SKUS
        assert "UFCha250" in TRACKED_SKUS


class TestDefaultWarehouseCode:
    """Tests for DEFAULT_WAREHOUSE_CODE constant."""

    def test_default_warehouse_code(self) -> None:
        """Test that DEFAULT_WAREHOUSE_CODE is set."""
        assert DEFAULT_WAREHOUSE_CODE == "WINEDIRECT"
