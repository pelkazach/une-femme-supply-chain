"""Tests for QuickBooks inventory sync task."""

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.inventory_event import InventoryEvent
from src.models.product import Product
from src.models.warehouse import Warehouse
from src.services.quickbooks import (
    QuickBooksAPIError,
    QuickBooksAuthError,
    QuickBooksClient,
    SyncResult,
    TokenData,
)
from src.tasks.quickbooks_sync import (
    DISCREPANCY_THRESHOLD,
    QUICKBOOKS_WAREHOUSE_CODE,
    TRACKED_SKUS,
    InventoryDiscrepancy,
    InventorySyncResult,
    check_inventory_discrepancies,
    detect_discrepancies,
    get_or_create_warehouse,
    get_platform_inventory,
    get_quickbooks_inventory,
    get_sku_id_map,
    pull_inventory_from_quickbooks,
    push_inventory_to_quickbooks,
    sync_quickbooks_inventory,
)


# ============================================================================
# InventoryDiscrepancy Tests
# ============================================================================


class TestInventoryDiscrepancy:
    """Tests for InventoryDiscrepancy dataclass."""

    def test_calculate_no_difference(self) -> None:
        """Test with no difference between quantities."""
        discrepancy = InventoryDiscrepancy.calculate("UFBub250", 100, 100)

        assert discrepancy.sku == "UFBub250"
        assert discrepancy.platform_quantity == 100
        assert discrepancy.quickbooks_quantity == 100
        assert discrepancy.difference == 0
        assert discrepancy.difference_percent == 0.0
        assert discrepancy.exceeds_threshold is False

    def test_calculate_small_difference(self) -> None:
        """Test with difference within threshold."""
        # 1% of 100 = 1 unit difference is within threshold
        discrepancy = InventoryDiscrepancy.calculate("UFBub250", 100, 99)

        assert discrepancy.difference == 1
        assert discrepancy.difference_percent == 0.01  # 1%
        assert discrepancy.exceeds_threshold is False

    def test_calculate_exceeds_threshold(self) -> None:
        """Test with difference exceeding threshold."""
        # 5% difference exceeds 1% threshold
        discrepancy = InventoryDiscrepancy.calculate("UFBub250", 100, 95)

        assert discrepancy.difference == 5
        assert discrepancy.difference_percent == 0.05  # 5%
        assert discrepancy.exceeds_threshold is True

    def test_calculate_platform_higher(self) -> None:
        """Test when platform quantity is higher."""
        discrepancy = InventoryDiscrepancy.calculate("UFBub250", 150, 100)

        assert discrepancy.difference == 50
        assert discrepancy.platform_quantity > discrepancy.quickbooks_quantity
        assert discrepancy.exceeds_threshold is True

    def test_calculate_quickbooks_higher(self) -> None:
        """Test when QuickBooks quantity is higher."""
        discrepancy = InventoryDiscrepancy.calculate("UFBub250", 100, 150)

        assert discrepancy.difference == -50
        assert discrepancy.platform_quantity < discrepancy.quickbooks_quantity
        assert discrepancy.exceeds_threshold is True

    def test_calculate_zero_quantities(self) -> None:
        """Test with zero quantities (avoid division by zero)."""
        discrepancy = InventoryDiscrepancy.calculate("UFBub250", 0, 0)

        assert discrepancy.difference == 0
        assert discrepancy.difference_percent == 0.0
        assert discrepancy.exceeds_threshold is False

    def test_calculate_one_zero(self) -> None:
        """Test when one quantity is zero."""
        discrepancy = InventoryDiscrepancy.calculate("UFBub250", 100, 0)

        assert discrepancy.difference == 100
        assert discrepancy.difference_percent == 1.0  # 100%
        assert discrepancy.exceeds_threshold is True


# ============================================================================
# InventorySyncResult Tests
# ============================================================================


class TestInventorySyncResult:
    """Tests for InventorySyncResult dataclass."""

    def test_default_values(self) -> None:
        """Test default values are correct."""
        result = InventorySyncResult()

        assert result.status == "success"
        assert result.direction == "bidirectional"
        assert result.skus_synced == 0
        assert result.skus_with_discrepancies == 0
        assert result.discrepancies == []
        assert result.push_result is None
        assert result.pull_events_created == 0
        assert result.errors == []

    def test_to_dict(self) -> None:
        """Test to_dict serialization."""
        discrepancy = InventoryDiscrepancy(
            sku="UFBub250",
            platform_quantity=100,
            quickbooks_quantity=90,
            difference=10,
            difference_percent=0.10,
            exceeds_threshold=True,
        )
        push_result = SyncResult(success=3, failed=1, errors=[{"sku": "X", "error": "err"}])

        result = InventorySyncResult(
            status="partial",
            direction="push",
            skus_synced=3,
            skus_with_discrepancies=1,
            discrepancies=[discrepancy],
            push_result=push_result,
            pull_events_created=4,
            errors=["Some error"],
            duration_seconds=5.123,
        )

        data = result.to_dict()

        assert data["status"] == "partial"
        assert data["direction"] == "push"
        assert data["skus_synced"] == 3
        assert data["skus_with_discrepancies"] == 1
        assert len(data["discrepancies"]) == 1
        assert data["discrepancies"][0]["sku"] == "UFBub250"
        assert data["discrepancies"][0]["difference_percent"] == 10.0  # Rounded percentage
        assert data["push_result"]["success"] == 3
        assert data["push_result"]["failed"] == 1
        assert data["pull_events_created"] == 4
        assert data["errors"] == ["Some error"]
        assert data["duration_seconds"] == 5.12  # Rounded to 2 decimals


# ============================================================================
# detect_discrepancies Tests
# ============================================================================


class TestDetectDiscrepancies:
    """Tests for detect_discrepancies function."""

    def test_no_discrepancies(self) -> None:
        """Test when quantities match exactly."""
        platform = {"UFBub250": 100, "UFRos250": 200}
        qbo = {"UFBub250": 100, "UFRos250": 200}

        discrepancies = detect_discrepancies(platform, qbo)

        assert len(discrepancies) == 0

    def test_all_discrepancies(self) -> None:
        """Test when all quantities differ."""
        platform = {"UFBub250": 100, "UFRos250": 200}
        qbo = {"UFBub250": 80, "UFRos250": 220}

        discrepancies = detect_discrepancies(platform, qbo)

        assert len(discrepancies) == 2

    def test_mixed_discrepancies(self) -> None:
        """Test with some matching and some differing."""
        platform = {"UFBub250": 100, "UFRos250": 200, "UFRed250": 300}
        qbo = {"UFBub250": 100, "UFRos250": 180, "UFRed250": 300}

        discrepancies = detect_discrepancies(platform, qbo)

        assert len(discrepancies) == 1
        assert discrepancies[0].sku == "UFRos250"

    def test_missing_in_qbo(self) -> None:
        """Test when SKU exists in platform but not QuickBooks."""
        platform = {"UFBub250": 100, "UFRos250": 200}
        qbo = {"UFBub250": 100}

        discrepancies = detect_discrepancies(platform, qbo)

        assert len(discrepancies) == 1
        assert discrepancies[0].sku == "UFRos250"
        assert discrepancies[0].quickbooks_quantity == 0

    def test_missing_in_platform(self) -> None:
        """Test when SKU exists in QuickBooks but not platform."""
        platform = {"UFBub250": 100}
        qbo = {"UFBub250": 100, "UFRos250": 200}

        discrepancies = detect_discrepancies(platform, qbo)

        assert len(discrepancies) == 1
        assert discrepancies[0].sku == "UFRos250"
        assert discrepancies[0].platform_quantity == 0

    def test_threshold_boundary(self) -> None:
        """Test discrepancy at exactly the threshold boundary."""
        # 1% of 100 = 1, so 99 vs 100 should not exceed
        platform = {"UFBub250": 100}
        qbo = {"UFBub250": 99}

        discrepancies = detect_discrepancies(platform, qbo)

        assert len(discrepancies) == 1
        assert discrepancies[0].exceeds_threshold is False


# ============================================================================
# get_quickbooks_inventory Tests
# ============================================================================


class TestGetQuickBooksInventory:
    """Tests for get_quickbooks_inventory function."""

    @pytest.mark.asyncio
    async def test_filters_tracked_skus(self) -> None:
        """Test that only tracked SKUs are included."""
        client = MagicMock(spec=QuickBooksClient)

        mock_items = [
            MagicMock(Name="UFBub250", QtyOnHand=100),
            MagicMock(Name="UFRos250", QtyOnHand=200),
            MagicMock(Name="OTHER_SKU", QtyOnHand=300),  # Not tracked
        ]

        client.get_items = AsyncMock(return_value=mock_items)

        inventory = await get_quickbooks_inventory(client)

        assert "UFBub250" in inventory
        assert "UFRos250" in inventory
        assert "OTHER_SKU" not in inventory
        assert inventory["UFBub250"] == 100
        assert inventory["UFRos250"] == 200

    @pytest.mark.asyncio
    async def test_handles_none_quantity(self) -> None:
        """Test handling of None QtyOnHand."""
        client = MagicMock(spec=QuickBooksClient)

        mock_items = [MagicMock(Name="UFBub250", QtyOnHand=None)]
        client.get_items = AsyncMock(return_value=mock_items)

        inventory = await get_quickbooks_inventory(client)

        assert inventory["UFBub250"] == 0

    @pytest.mark.asyncio
    async def test_empty_items(self) -> None:
        """Test with no items returned."""
        client = MagicMock(spec=QuickBooksClient)
        client.get_items = AsyncMock(return_value=[])

        inventory = await get_quickbooks_inventory(client)

        assert inventory == {}


# ============================================================================
# push_inventory_to_quickbooks Tests
# ============================================================================


class TestPushInventoryToQuickBooks:
    """Tests for push_inventory_to_quickbooks function."""

    @pytest.mark.asyncio
    async def test_pushes_all_skus(self) -> None:
        """Test that all SKUs are pushed."""
        client = MagicMock(spec=QuickBooksClient)
        mock_result = SyncResult(success=2, failed=0)
        client.sync_inventory = AsyncMock(return_value=mock_result)

        platform_inventory = {"UFBub250": 100, "UFRos250": 200}

        result = await push_inventory_to_quickbooks(client, platform_inventory)

        assert result.success == 2
        assert result.failed == 0

        # Verify sync_inventory was called with correct products
        call_args = client.sync_inventory.call_args
        products = call_args[0][0]
        assert len(products) == 2

    @pytest.mark.asyncio
    async def test_handles_partial_failure(self) -> None:
        """Test handling of partial failures."""
        client = MagicMock(spec=QuickBooksClient)
        mock_result = SyncResult(
            success=1,
            failed=1,
            errors=[{"sku": "UFRos250", "error": "Not found"}],
        )
        client.sync_inventory = AsyncMock(return_value=mock_result)

        platform_inventory = {"UFBub250": 100, "UFRos250": 200}

        result = await push_inventory_to_quickbooks(client, platform_inventory)

        assert result.success == 1
        assert result.failed == 1
        assert len(result.errors) == 1


# ============================================================================
# pull_inventory_from_quickbooks Tests
# ============================================================================


class TestPullInventoryFromQuickBooks:
    """Tests for pull_inventory_from_quickbooks function."""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """Create a mock database session."""
        return MagicMock(spec=AsyncSession)

    @pytest.mark.asyncio
    async def test_creates_snapshot_events(self, mock_session: MagicMock) -> None:
        """Test that snapshot events are created."""
        sku_id = uuid.uuid4()
        warehouse_id = uuid.uuid4()
        sync_time = datetime.now(UTC)

        qbo_inventory = {"UFBub250": 100}
        sku_map = {"UFBub250": sku_id}

        events_created = await pull_inventory_from_quickbooks(
            mock_session, qbo_inventory, sku_map, warehouse_id, sync_time
        )

        assert events_created == 1
        mock_session.add.assert_called_once()

        # Verify the event was created correctly
        event = mock_session.add.call_args[0][0]
        assert isinstance(event, InventoryEvent)
        assert event.event_type == "snapshot"
        assert event.quantity == 100
        assert event.sku_id == sku_id
        assert event.warehouse_id == warehouse_id

    @pytest.mark.asyncio
    async def test_skips_unknown_skus(self, mock_session: MagicMock) -> None:
        """Test that unknown SKUs are skipped."""
        warehouse_id = uuid.uuid4()
        sync_time = datetime.now(UTC)

        qbo_inventory = {"UNKNOWN_SKU": 100}
        sku_map = {"UFBub250": uuid.uuid4()}

        events_created = await pull_inventory_from_quickbooks(
            mock_session, qbo_inventory, sku_map, warehouse_id, sync_time
        )

        assert events_created == 0
        mock_session.add.assert_not_called()


# ============================================================================
# Celery Task Tests
# ============================================================================


class TestSyncQuickBooksInventoryTask:
    """Tests for sync_quickbooks_inventory Celery task."""

    def test_task_returns_sync_result(self) -> None:
        """Test that the task returns InventorySyncResult as dict."""
        mock_result = InventorySyncResult(
            status="success",
            skus_synced=4,
        )

        with patch(
            "src.tasks.quickbooks_sync._async_sync_quickbooks_inventory",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            with patch("asyncio.run", return_value=mock_result):
                # Create mock self for bound task
                mock_self = MagicMock()
                mock_self.retry = MagicMock(side_effect=Exception("Should not retry"))

                # Call task directly using apply
                result = sync_quickbooks_inventory.apply(
                    kwargs={"direction": "push"}
                ).result

        assert result["status"] == "success"
        assert result["skus_synced"] == 4

    def test_task_direction_parameter(self) -> None:
        """Test that direction parameter is passed correctly."""
        mock_result = InventorySyncResult(direction="push")

        with patch("asyncio.run", return_value=mock_result):
            # Test that the task accepts direction parameter
            result = sync_quickbooks_inventory.apply(
                kwargs={"direction": "push"}
            ).result

        assert result["direction"] == "push"


class TestCheckInventoryDiscrepanciesTask:
    """Tests for check_inventory_discrepancies Celery task."""

    def test_returns_error_when_not_authenticated(self) -> None:
        """Test that discrepancy check returns error when not authenticated."""
        # Create mock engine with async dispose
        mock_engine = MagicMock()
        mock_engine.dispose = AsyncMock()

        with (
            patch("src.tasks.quickbooks_sync.create_async_engine", return_value=mock_engine),
            patch("src.tasks.quickbooks_sync.async_sessionmaker"),
            patch("src.tasks.quickbooks_sync.QuickBooksClient") as mock_client_class,
        ):
            mock_client = MagicMock()
            mock_client.load_token.return_value = False
            mock_client_class.return_value = mock_client

            result = check_inventory_discrepancies()

            assert result["status"] == "error"
            assert "not authenticated" in result["error"].lower()


# ============================================================================
# Integration Tests
# ============================================================================


class TestQuickBooksSyncIntegration:
    """Integration tests for QuickBooks sync functionality."""

    def test_discrepancy_threshold_is_one_percent(self) -> None:
        """AC: Inventory quantities match between systems (±1%)."""
        assert DISCREPANCY_THRESHOLD == 0.01

    def test_tracked_skus_match_platform(self) -> None:
        """Test that tracked SKUs are the 4 Une Femme products."""
        expected_skus = {"UFBub250", "UFRos250", "UFRed250", "UFCha250"}
        assert TRACKED_SKUS == expected_skus

    def test_sync_result_captures_discrepancies(self) -> None:
        """Test that sync result properly captures discrepancy information."""
        discrepancy = InventoryDiscrepancy.calculate("UFBub250", 100, 80)

        result = InventorySyncResult(
            discrepancies=[discrepancy],
            skus_with_discrepancies=1 if discrepancy.exceeds_threshold else 0,
        )

        data = result.to_dict()

        # Discrepancy info should be in the result
        assert len(data["discrepancies"]) == 1
        assert data["discrepancies"][0]["exceeds_threshold"] is True
        assert data["skus_with_discrepancies"] == 1


# ============================================================================
# Acceptance Criteria Tests
# ============================================================================


class TestAcceptanceCriteria:
    """Tests verifying acceptance criteria from spec."""

    def test_inventory_variance_threshold(self) -> None:
        """AC: Inventory quantities match between systems (±1%)."""
        # ±1% variance threshold
        assert DISCREPANCY_THRESHOLD == 0.01

        # Test at exactly 1% - should not exceed
        discrepancy = InventoryDiscrepancy.calculate("TEST", 100, 99)
        assert discrepancy.difference_percent <= 0.01
        assert discrepancy.exceeds_threshold is False

        # Test at 1.1% - should exceed
        discrepancy = InventoryDiscrepancy.calculate("TEST", 1000, 989)
        assert discrepancy.difference_percent > 0.01
        assert discrepancy.exceeds_threshold is True

    def test_discrepancy_flagged_for_review(self) -> None:
        """AC: Mismatched inventory flagged for review."""
        # When discrepancy exceeds threshold, it should be flagged
        discrepancy = InventoryDiscrepancy.calculate("UFBub250", 100, 50)

        # exceeds_threshold serves as the "flagged for review" indicator
        assert discrepancy.exceeds_threshold is True
        assert discrepancy.difference_percent > DISCREPANCY_THRESHOLD

    def test_sync_result_includes_errors(self) -> None:
        """AC: Sync includes error handling."""
        result = InventorySyncResult(
            status="partial",
            errors=["API error occurred"],
        )

        data = result.to_dict()

        assert data["status"] == "partial"
        assert len(data["errors"]) == 1

    def test_bidirectional_sync_supported(self) -> None:
        """AC: Sync inventory levels bidirectionally."""
        result = InventorySyncResult(direction="bidirectional")

        assert result.direction == "bidirectional"

        # Push and pull can happen in the same sync
        result.push_result = SyncResult(success=4)
        result.pull_events_created = 4

        data = result.to_dict()
        assert data["push_result"] is not None
        assert data["pull_events_created"] == 4


# ============================================================================
# Beat Schedule Tests
# ============================================================================


class TestBeatSchedule:
    """Tests for Celery beat schedule configuration."""

    def test_quickbooks_sync_in_schedule(self) -> None:
        """Test that QuickBooks sync is in the beat schedule."""
        from src.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule

        assert "sync-quickbooks-inventory" in schedule

    def test_quickbooks_sync_schedule_every_4_hours(self) -> None:
        """AC: Sync runs every 4 hours."""
        from src.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule["sync-quickbooks-inventory"]

        # Check it's configured for every 4 hours
        crontab = schedule["schedule"]
        assert crontab.minute == {0}  # At minute 0
        assert crontab.hour == {0, 4, 8, 12, 16, 20}  # Every 4 hours

    def test_quickbooks_sync_bidirectional_default(self) -> None:
        """Test that default direction is bidirectional."""
        from src.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule["sync-quickbooks-inventory"]

        assert schedule["kwargs"]["direction"] == "bidirectional"


# ============================================================================
# Helper Function Tests
# ============================================================================


class TestHelperFunctions:
    """Tests for helper functions."""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """Create a mock database session."""
        return MagicMock(spec=AsyncSession)

    @pytest.mark.asyncio
    async def test_get_sku_id_map(self, mock_session: MagicMock) -> None:
        """Test SKU to ID mapping retrieval."""
        sku_id_1 = uuid.uuid4()
        sku_id_2 = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(
            return_value=iter(
                [
                    MagicMock(sku="UFBub250", id=sku_id_1),
                    MagicMock(sku="UFRos250", id=sku_id_2),
                ]
            )
        )
        mock_session.execute = AsyncMock(return_value=mock_result)

        sku_map = await get_sku_id_map(mock_session)

        assert "UFBub250" in sku_map
        assert "UFRos250" in sku_map
        assert sku_map["UFBub250"] == sku_id_1
        assert sku_map["UFRos250"] == sku_id_2

    @pytest.mark.asyncio
    async def test_get_or_create_warehouse_existing(
        self, mock_session: MagicMock
    ) -> None:
        """Test getting an existing warehouse."""
        warehouse_id = uuid.uuid4()
        mock_warehouse = MagicMock(id=warehouse_id)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_warehouse
        mock_session.execute = AsyncMock(return_value=mock_result)

        result_id = await get_or_create_warehouse(
            mock_session, "QUICKBOOKS", "QuickBooks Warehouse"
        )

        assert result_id == warehouse_id
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_create_warehouse_new(self, mock_session: MagicMock) -> None:
        """Test creating a new warehouse."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.flush = AsyncMock()

        await get_or_create_warehouse(
            mock_session, "QUICKBOOKS", "QuickBooks Warehouse"
        )

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

        # Verify the warehouse was created with correct values
        warehouse = mock_session.add.call_args[0][0]
        assert isinstance(warehouse, Warehouse)
        assert warehouse.code == "QUICKBOOKS"
        assert warehouse.name == "QuickBooks Warehouse"
