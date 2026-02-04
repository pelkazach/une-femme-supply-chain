"""Tests for inventory metrics calculation service."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.metrics import (
    DOHMetrics,
    ShipDepRatioMetrics,
    calculate_daily_depletion_rate,
    calculate_doh_t30,
    calculate_doh_t30_all_skus,
    calculate_doh_t30_for_sku,
    calculate_doh_t90,
    calculate_doh_t90_all_skus,
    calculate_doh_t90_for_sku,
    calculate_ship_dep_ratio,
    calculate_ship_dep_ratio_all_skus,
    calculate_ship_dep_ratio_for_sku,
    get_current_inventory,
    get_depletion_total,
    get_shipment_total,
)


class TestCalculateDohT30:
    """Tests for the calculate_doh_t30 function."""

    def test_basic_calculation(self) -> None:
        """Test basic DOH_T30 calculation."""
        # 1000 units on hand, 100 depleted in 30 days
        # Daily rate = 100/30 = 3.33
        # DOH = 1000 / 3.33 = 300 days
        result = calculate_doh_t30(1000, 100)
        assert result is not None
        assert abs(result - 300.0) < 0.01

    def test_spec_example_10_days(self) -> None:
        """Test spec example: 1000 units, 100/day depletion = 10 days."""
        # From spec: 1000 units on hand, 100/day depletion (30d) = DOH_T30 = 10 days
        # This means 30 * 100 = 3000 depletions in 30 days
        result = calculate_doh_t30(1000, 3000)
        assert result is not None
        assert abs(result - 10.0) < 0.01

    def test_high_inventory_low_depletion(self) -> None:
        """Test high inventory with low depletion rate."""
        # 10000 units, only 30 depleted in 30 days (1/day)
        # DOH = 10000 / 1 = 10000 days
        result = calculate_doh_t30(10000, 30)
        assert result is not None
        assert abs(result - 10000.0) < 0.01

    def test_low_inventory_high_depletion(self) -> None:
        """Test low inventory with high depletion rate."""
        # 100 units, 900 depleted in 30 days (30/day)
        # DOH = 100 / 30 = 3.33 days
        result = calculate_doh_t30(100, 900)
        assert result is not None
        assert abs(result - 3.33) < 0.01

    def test_zero_depletion_returns_none(self) -> None:
        """Test that zero depletion returns None (cannot calculate)."""
        # From spec: Zero depletion should be handled gracefully
        result = calculate_doh_t30(1000, 0)
        assert result is None

    def test_negative_depletion_returns_none(self) -> None:
        """Test that negative depletion returns None."""
        result = calculate_doh_t30(1000, -100)
        assert result is None

    def test_zero_inventory_returns_zero(self) -> None:
        """Test that zero inventory returns zero days on hand."""
        result = calculate_doh_t30(0, 100)
        assert result is not None
        assert result == 0.0

    def test_fractional_result(self) -> None:
        """Test fractional days on hand calculation."""
        # 50 units, 300 depleted in 30 days (10/day)
        # DOH = 50 / 10 = 5 days
        result = calculate_doh_t30(50, 300)
        assert result is not None
        assert abs(result - 5.0) < 0.01

    def test_large_inventory(self) -> None:
        """Test with large inventory values."""
        # 1,000,000 units, 30,000 depleted (1000/day)
        # DOH = 1,000,000 / 1000 = 1000 days
        result = calculate_doh_t30(1_000_000, 30_000)
        assert result is not None
        assert abs(result - 1000.0) < 0.01

    def test_variance_within_one_percent(self) -> None:
        """Test that calculation matches Excel formula within 1% variance."""
        # Excel formula: =current_inventory / (SUMIF(depletions_30d) / 30)
        # Our formula: current_inventory / (depletion_30d / 30)

        test_cases = [
            (1000, 100, 300.0),      # Basic case
            (500, 150, 100.0),       # 500 / (150/30) = 500 / 5 = 100
            (2500, 750, 100.0),      # 2500 / (750/30) = 2500 / 25 = 100
            (1234, 567, 65.29),      # 1234 / (567/30) = 1234 / 18.9 = 65.29
        ]

        for inventory, depletion, expected in test_cases:
            result = calculate_doh_t30(inventory, depletion)
            assert result is not None
            # Check within 1% variance
            variance = abs(result - expected) / expected
            assert variance < 0.01, f"Expected {expected}, got {result} (variance: {variance*100:.2f}%)"


class TestCalculateDohT90:
    """Tests for the calculate_doh_t90 function."""

    def test_basic_calculation(self) -> None:
        """Test basic DOH_T90 calculation."""
        # 1000 units on hand, 900 depleted in 90 days
        # Daily rate = 900/90 = 10
        # DOH = 1000 / 10 = 100 days
        result = calculate_doh_t90(1000, 900)
        assert result is not None
        assert abs(result - 100.0) < 0.01

    def test_spec_example_20_days(self) -> None:
        """Test spec example: 1000 units, 50/day depletion = 20 days."""
        # From spec: 1000 units on hand, 50/day depletion (90d) = DOH_T90 = 20 days
        # This means 90 * 50 = 4500 depletions in 90 days
        result = calculate_doh_t90(1000, 4500)
        assert result is not None
        assert abs(result - 20.0) < 0.01

    def test_high_inventory_low_depletion(self) -> None:
        """Test high inventory with low depletion rate."""
        # 10000 units, only 90 depleted in 90 days (1/day)
        # DOH = 10000 / 1 = 10000 days
        result = calculate_doh_t90(10000, 90)
        assert result is not None
        assert abs(result - 10000.0) < 0.01

    def test_low_inventory_high_depletion(self) -> None:
        """Test low inventory with high depletion rate."""
        # 100 units, 2700 depleted in 90 days (30/day)
        # DOH = 100 / 30 = 3.33 days
        result = calculate_doh_t90(100, 2700)
        assert result is not None
        assert abs(result - 3.33) < 0.01

    def test_zero_depletion_returns_none(self) -> None:
        """Test that zero depletion returns None (cannot calculate)."""
        # From spec: Zero depletion should be handled gracefully
        result = calculate_doh_t90(1000, 0)
        assert result is None

    def test_negative_depletion_returns_none(self) -> None:
        """Test that negative depletion returns None."""
        result = calculate_doh_t90(1000, -100)
        assert result is None

    def test_zero_inventory_returns_zero(self) -> None:
        """Test that zero inventory returns zero days on hand."""
        result = calculate_doh_t90(0, 900)
        assert result is not None
        assert result == 0.0

    def test_fractional_result(self) -> None:
        """Test fractional days on hand calculation."""
        # 50 units, 900 depleted in 90 days (10/day)
        # DOH = 50 / 10 = 5 days
        result = calculate_doh_t90(50, 900)
        assert result is not None
        assert abs(result - 5.0) < 0.01

    def test_large_inventory(self) -> None:
        """Test with large inventory values."""
        # 1,000,000 units, 90,000 depleted (1000/day)
        # DOH = 1,000,000 / 1000 = 1000 days
        result = calculate_doh_t90(1_000_000, 90_000)
        assert result is not None
        assert abs(result - 1000.0) < 0.01

    def test_variance_within_one_percent(self) -> None:
        """Test that calculation matches Excel formula within 1% variance."""
        # Excel formula: =current_inventory / (SUMIF(depletions_90d) / 90)
        # Our formula: current_inventory / (depletion_90d / 90)

        test_cases = [
            (1000, 900, 100.0),       # Basic case: 1000 / (900/90) = 1000 / 10 = 100
            (500, 450, 100.0),        # 500 / (450/90) = 500 / 5 = 100
            (2500, 2250, 100.0),      # 2500 / (2250/90) = 2500 / 25 = 100
            (1234, 1701, 65.29),      # 1234 / (1701/90) = 1234 / 18.9 = 65.29
        ]

        for inventory, depletion, expected in test_cases:
            result = calculate_doh_t90(inventory, depletion)
            assert result is not None
            # Check within 1% variance
            variance = abs(result - expected) / expected
            assert variance < 0.01, f"Expected {expected}, got {result} (variance: {variance*100:.2f}%)"

    def test_t90_smoother_than_t30(self) -> None:
        """Test that T90 provides more stable estimates for seasonal data."""
        # Scenario: recent spike in sales (T30 shows high rate, T90 smooths it out)
        # Same inventory, but T30 sees recent spike, T90 averages longer period
        current_inventory = 1000

        # T30: 600 units depleted (20/day) -> DOH = 1000/20 = 50 days
        depletion_30d = 600
        doh_t30 = calculate_doh_t30(current_inventory, depletion_30d)

        # T90: 900 units total (includes the spike period) -> 10/day avg -> DOH = 100 days
        depletion_90d = 900
        doh_t90 = calculate_doh_t90(current_inventory, depletion_90d)

        assert doh_t30 is not None
        assert doh_t90 is not None
        # T90 should show more conservative (higher) DOH due to smoothing
        assert doh_t90 > doh_t30


class TestCalculateDailyDepletionRate:
    """Tests for the calculate_daily_depletion_rate function."""

    def test_basic_calculation(self) -> None:
        """Test basic daily rate calculation."""
        result = calculate_daily_depletion_rate(300, 30)
        assert result is not None
        assert result == 10.0

    def test_zero_days_returns_none(self) -> None:
        """Test that zero days returns None."""
        result = calculate_daily_depletion_rate(100, 0)
        assert result is None

    def test_negative_days_returns_none(self) -> None:
        """Test that negative days returns None."""
        result = calculate_daily_depletion_rate(100, -5)
        assert result is None

    def test_fractional_rate(self) -> None:
        """Test fractional daily rate."""
        result = calculate_daily_depletion_rate(100, 30)
        assert result is not None
        assert abs(result - 3.33) < 0.01

    def test_zero_depletion(self) -> None:
        """Test zero depletion returns zero rate."""
        result = calculate_daily_depletion_rate(0, 30)
        assert result is not None
        assert result == 0.0


class TestDOHMetricsDataclass:
    """Tests for the DOHMetrics dataclass."""

    def test_create_metrics(self) -> None:
        """Test creating a DOHMetrics instance."""
        sku_id = uuid.uuid4()
        now = datetime.now(UTC)
        metrics = DOHMetrics(
            sku="UFBub250",
            sku_id=sku_id,
            current_inventory=1000,
            doh_t30=300.0,
            depletion_30d=100,
            daily_rate_30d=3.33,
            doh_t90=100.0,
            depletion_90d=900,
            daily_rate_90d=10.0,
            calculated_at=now,
        )

        assert metrics.sku == "UFBub250"
        assert metrics.sku_id == sku_id
        assert metrics.current_inventory == 1000
        assert metrics.doh_t30 == 300.0
        assert metrics.depletion_30d == 100
        assert metrics.daily_rate_30d == 3.33
        assert metrics.doh_t90 == 100.0
        assert metrics.depletion_90d == 900
        assert metrics.daily_rate_90d == 10.0
        assert metrics.calculated_at == now

    def test_metrics_with_none_doh(self) -> None:
        """Test creating metrics with None DOH (zero depletion case)."""
        sku_id = uuid.uuid4()
        now = datetime.now(UTC)
        metrics = DOHMetrics(
            sku="UFRos250",
            sku_id=sku_id,
            current_inventory=500,
            doh_t30=None,
            depletion_30d=0,
            daily_rate_30d=None,
            doh_t90=None,
            depletion_90d=0,
            daily_rate_90d=None,
            calculated_at=now,
        )

        assert metrics.doh_t30 is None
        assert metrics.daily_rate_30d is None
        assert metrics.doh_t90 is None
        assert metrics.daily_rate_90d is None

    def test_metrics_immutable(self) -> None:
        """Test that DOHMetrics is immutable (frozen dataclass)."""
        sku_id = uuid.uuid4()
        now = datetime.now(UTC)
        metrics = DOHMetrics(
            sku="UFRed250",
            sku_id=sku_id,
            current_inventory=750,
            doh_t30=150.0,
            depletion_30d=150,
            daily_rate_30d=5.0,
            doh_t90=75.0,
            depletion_90d=900,
            daily_rate_90d=10.0,
            calculated_at=now,
        )

        with pytest.raises(AttributeError):
            metrics.sku = "NewSKU"  # type: ignore


class TestGetDepletionTotal:
    """Tests for the get_depletion_total function."""

    @pytest.mark.asyncio
    async def test_get_depletion_total_basic(self) -> None:
        """Test basic depletion total retrieval."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 500
        mock_session.execute.return_value = mock_result

        sku_id = uuid.uuid4()
        result = await get_depletion_total(mock_session, sku_id, days=30)

        assert result == 500
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_depletion_total_returns_zero_when_none(self) -> None:
        """Test that None result returns 0."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_session.execute.return_value = mock_result

        sku_id = uuid.uuid4()
        result = await get_depletion_total(mock_session, sku_id, days=30)

        assert result == 0

    @pytest.mark.asyncio
    async def test_get_depletion_total_with_warehouse_filter(self) -> None:
        """Test depletion total with warehouse filter."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 200
        mock_session.execute.return_value = mock_result

        sku_id = uuid.uuid4()
        warehouse_id = uuid.uuid4()
        result = await get_depletion_total(
            mock_session, sku_id, days=30, warehouse_id=warehouse_id
        )

        assert result == 200

    @pytest.mark.asyncio
    async def test_get_depletion_total_with_distributor_filter(self) -> None:
        """Test depletion total with distributor filter."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 150
        mock_session.execute.return_value = mock_result

        sku_id = uuid.uuid4()
        distributor_id = uuid.uuid4()
        result = await get_depletion_total(
            mock_session, sku_id, days=30, distributor_id=distributor_id
        )

        assert result == 150

    @pytest.mark.asyncio
    async def test_get_depletion_total_with_as_of_date(self) -> None:
        """Test depletion total with custom as_of date."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 300
        mock_session.execute.return_value = mock_result

        sku_id = uuid.uuid4()
        as_of = datetime(2026, 1, 15, tzinfo=UTC)
        result = await get_depletion_total(
            mock_session, sku_id, days=30, as_of=as_of
        )

        assert result == 300


class TestGetCurrentInventory:
    """Tests for the get_current_inventory function."""

    @pytest.mark.asyncio
    async def test_current_inventory_from_snapshot(self) -> None:
        """Test getting current inventory from a snapshot."""
        mock_session = AsyncMock()

        # First call returns snapshot
        snapshot_result = MagicMock()
        snapshot_time = datetime.now(UTC) - timedelta(hours=1)
        snapshot_result.first.return_value = (1000, snapshot_time)

        # Second call returns delta (events after snapshot)
        delta_result = MagicMock()
        delta_result.scalar.return_value = -50

        mock_session.execute.side_effect = [snapshot_result, delta_result]

        sku_id = uuid.uuid4()
        result = await get_current_inventory(mock_session, sku_id)

        assert result == 950  # 1000 - 50

    @pytest.mark.asyncio
    async def test_current_inventory_no_snapshot(self) -> None:
        """Test getting current inventory when no snapshot exists."""
        mock_session = AsyncMock()

        # First call returns no snapshot
        snapshot_result = MagicMock()
        snapshot_result.first.return_value = None

        # Second call returns sum of all events
        sum_result = MagicMock()
        sum_result.scalar.return_value = 750

        mock_session.execute.side_effect = [snapshot_result, sum_result]

        sku_id = uuid.uuid4()
        result = await get_current_inventory(mock_session, sku_id)

        assert result == 750

    @pytest.mark.asyncio
    async def test_current_inventory_empty_returns_zero(self) -> None:
        """Test that empty inventory returns zero."""
        mock_session = AsyncMock()

        snapshot_result = MagicMock()
        snapshot_result.first.return_value = None

        sum_result = MagicMock()
        sum_result.scalar.return_value = None

        mock_session.execute.side_effect = [snapshot_result, sum_result]

        sku_id = uuid.uuid4()
        result = await get_current_inventory(mock_session, sku_id)

        assert result == 0


class TestCalculateDohT30ForSku:
    """Tests for the calculate_doh_t30_for_sku function."""

    @pytest.mark.asyncio
    async def test_calculate_for_sku_basic(self) -> None:
        """Test basic SKU metrics calculation."""
        mock_session = AsyncMock()
        sku_id = uuid.uuid4()

        # Mock product query
        mock_product = MagicMock()
        mock_product.sku = "UFBub250"
        mock_product.id = sku_id

        with patch(
            "src.services.metrics.get_current_inventory",
            new_callable=AsyncMock,
        ) as mock_get_inv:
            mock_get_inv.return_value = 1000

            with patch(
                "src.services.metrics.get_depletion_total",
                new_callable=AsyncMock,
            ) as mock_get_dep:
                # Return different values for 30-day and 90-day calls
                mock_get_dep.side_effect = [100, 300]  # 30d, 90d

                # Mock the product query result
                product_result = MagicMock()
                product_result.scalar_one.return_value = mock_product
                mock_session.execute.return_value = product_result

                result = await calculate_doh_t30_for_sku(mock_session, sku_id)

                assert result.sku == "UFBub250"
                assert result.sku_id == sku_id
                assert result.current_inventory == 1000
                assert result.depletion_30d == 100
                assert result.doh_t30 is not None
                assert abs(result.doh_t30 - 300.0) < 0.01
                # T90 metrics should also be calculated
                assert result.depletion_90d == 300
                assert result.doh_t90 is not None
                assert abs(result.doh_t90 - 300.0) < 0.01  # 1000 / (300/90) = 300

    @pytest.mark.asyncio
    async def test_calculate_for_sku_zero_depletion(self) -> None:
        """Test SKU metrics calculation with zero depletion."""
        mock_session = AsyncMock()
        sku_id = uuid.uuid4()

        mock_product = MagicMock()
        mock_product.sku = "UFRos250"
        mock_product.id = sku_id

        with patch(
            "src.services.metrics.get_current_inventory",
            new_callable=AsyncMock,
        ) as mock_get_inv:
            mock_get_inv.return_value = 500

            with patch(
                "src.services.metrics.get_depletion_total",
                new_callable=AsyncMock,
            ) as mock_get_dep:
                mock_get_dep.return_value = 0  # Zero for both 30d and 90d

                product_result = MagicMock()
                product_result.scalar_one.return_value = mock_product
                mock_session.execute.return_value = product_result

                result = await calculate_doh_t30_for_sku(mock_session, sku_id)

                assert result.sku == "UFRos250"
                assert result.doh_t30 is None  # Cannot calculate DOH with zero depletion
                assert result.daily_rate_30d == 0.0  # Daily rate is 0 when no depletions
                assert result.doh_t90 is None  # T90 also None with zero depletion
                assert result.daily_rate_90d == 0.0

    @pytest.mark.asyncio
    async def test_calculate_for_sku_different_t30_t90(self) -> None:
        """Test SKU metrics with different T30 and T90 rates."""
        mock_session = AsyncMock()
        sku_id = uuid.uuid4()

        mock_product = MagicMock()
        mock_product.sku = "UFRed250"
        mock_product.id = sku_id

        with patch(
            "src.services.metrics.get_current_inventory",
            new_callable=AsyncMock,
        ) as mock_get_inv:
            mock_get_inv.return_value = 1000

            with patch(
                "src.services.metrics.get_depletion_total",
                new_callable=AsyncMock,
            ) as mock_get_dep:
                # Simulate higher recent sales (spike in 30d)
                mock_get_dep.side_effect = [600, 900]  # 30d=600, 90d=900

                product_result = MagicMock()
                product_result.scalar_one.return_value = mock_product
                mock_session.execute.return_value = product_result

                result = await calculate_doh_t30_for_sku(mock_session, sku_id)

                # T30: 1000 / (600/30) = 1000 / 20 = 50 days
                assert result.doh_t30 is not None
                assert abs(result.doh_t30 - 50.0) < 0.01
                assert result.daily_rate_30d is not None
                assert abs(result.daily_rate_30d - 20.0) < 0.01

                # T90: 1000 / (900/90) = 1000 / 10 = 100 days
                assert result.doh_t90 is not None
                assert abs(result.doh_t90 - 100.0) < 0.01
                assert result.daily_rate_90d is not None
                assert abs(result.daily_rate_90d - 10.0) < 0.01


class TestCalculateDohT90ForSku:
    """Tests for the calculate_doh_t90_for_sku function."""

    @pytest.mark.asyncio
    async def test_is_alias_for_t30(self) -> None:
        """Test that calculate_doh_t90_for_sku delegates to calculate_doh_t30_for_sku."""
        mock_session = AsyncMock()
        sku_id = uuid.uuid4()

        mock_product = MagicMock()
        mock_product.sku = "UFCha250"
        mock_product.id = sku_id

        with patch(
            "src.services.metrics.get_current_inventory",
            new_callable=AsyncMock,
        ) as mock_get_inv:
            mock_get_inv.return_value = 1000

            with patch(
                "src.services.metrics.get_depletion_total",
                new_callable=AsyncMock,
            ) as mock_get_dep:
                mock_get_dep.side_effect = [300, 900]

                product_result = MagicMock()
                product_result.scalar_one.return_value = mock_product
                mock_session.execute.return_value = product_result

                result = await calculate_doh_t90_for_sku(mock_session, sku_id)

                # Should return complete metrics including both T30 and T90
                assert result.sku == "UFCha250"
                assert result.doh_t30 is not None
                assert result.doh_t90 is not None


class TestCalculateDohT30AllSkus:
    """Tests for the calculate_doh_t30_all_skus function."""

    @pytest.mark.asyncio
    async def test_calculate_all_skus(self) -> None:
        """Test calculating metrics for all SKUs."""
        mock_session = AsyncMock()

        # Create mock products
        products = []
        for sku in ["UFBub250", "UFRos250", "UFRed250", "UFCha250"]:
            mock_product = MagicMock()
            mock_product.sku = sku
            mock_product.id = uuid.uuid4()
            products.append(mock_product)

        # Mock the products query
        products_result = MagicMock()
        products_result.scalars.return_value.all.return_value = products
        mock_session.execute.return_value = products_result

        # Mock calculate_doh_t30_for_sku
        with patch(
            "src.services.metrics.calculate_doh_t30_for_sku",
            new_callable=AsyncMock,
        ) as mock_calc:
            mock_calc.side_effect = [
                DOHMetrics(
                    sku=p.sku,
                    sku_id=p.id,
                    current_inventory=1000,
                    doh_t30=100.0,
                    depletion_30d=300,
                    daily_rate_30d=10.0,
                    doh_t90=100.0,
                    depletion_90d=900,
                    daily_rate_90d=10.0,
                    calculated_at=datetime.now(UTC),
                )
                for p in products
            ]

            result = await calculate_doh_t30_all_skus(mock_session)

            assert len(result) == 4
            assert all(isinstance(m, DOHMetrics) for m in result)
            skus = [m.sku for m in result]
            assert "UFBub250" in skus
            assert "UFRos250" in skus
            assert "UFRed250" in skus
            assert "UFCha250" in skus
            # Verify T90 metrics are also included
            assert all(m.doh_t90 is not None for m in result)

    @pytest.mark.asyncio
    async def test_calculate_all_skus_empty(self) -> None:
        """Test calculating metrics when no products exist."""
        mock_session = AsyncMock()

        products_result = MagicMock()
        products_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = products_result

        result = await calculate_doh_t30_all_skus(mock_session)

        assert result == []


class TestCalculateDohT90AllSkus:
    """Tests for the calculate_doh_t90_all_skus function."""

    @pytest.mark.asyncio
    async def test_is_alias_for_t30_all_skus(self) -> None:
        """Test that calculate_doh_t90_all_skus delegates to calculate_doh_t30_all_skus."""
        mock_session = AsyncMock()

        # Create mock products
        products = []
        for sku in ["UFBub250", "UFRos250"]:
            mock_product = MagicMock()
            mock_product.sku = sku
            mock_product.id = uuid.uuid4()
            products.append(mock_product)

        # Mock the products query
        products_result = MagicMock()
        products_result.scalars.return_value.all.return_value = products
        mock_session.execute.return_value = products_result

        # Mock calculate_doh_t30_for_sku
        with patch(
            "src.services.metrics.calculate_doh_t30_for_sku",
            new_callable=AsyncMock,
        ) as mock_calc:
            mock_calc.side_effect = [
                DOHMetrics(
                    sku=p.sku,
                    sku_id=p.id,
                    current_inventory=1000,
                    doh_t30=100.0,
                    depletion_30d=300,
                    daily_rate_30d=10.0,
                    doh_t90=100.0,
                    depletion_90d=900,
                    daily_rate_90d=10.0,
                    calculated_at=datetime.now(UTC),
                )
                for p in products
            ]

            result = await calculate_doh_t90_all_skus(mock_session)

            assert len(result) == 2
            # Should return complete metrics including both T30 and T90
            assert all(m.doh_t30 is not None for m in result)
            assert all(m.doh_t90 is not None for m in result)


class TestCalculateShipDepRatio:
    """Tests for the calculate_ship_dep_ratio function."""

    def test_spec_example_ratio_1_5(self) -> None:
        """Test spec example: 300 shipped, 200 depleted = 1.5."""
        # From spec: 300 shipped, 200 depleted (30d) = A30_Ship:A30_Dep = 1.5
        result = calculate_ship_dep_ratio(300, 200)
        assert result is not None
        assert abs(result - 1.5) < 0.001

    def test_building_inventory(self) -> None:
        """Test ratio > 1 indicates building inventory."""
        result = calculate_ship_dep_ratio(500, 200)
        assert result is not None
        assert result > 1.0
        assert abs(result - 2.5) < 0.001

    def test_balanced_flow(self) -> None:
        """Test ratio = 1 indicates balanced flow."""
        result = calculate_ship_dep_ratio(200, 200)
        assert result is not None
        assert result == 1.0

    def test_depleting_inventory(self) -> None:
        """Test ratio < 1 indicates depleting inventory."""
        result = calculate_ship_dep_ratio(100, 200)
        assert result is not None
        assert result < 1.0
        assert abs(result - 0.5) < 0.001

    def test_zero_depletions_returns_none(self) -> None:
        """Test that zero depletions returns None (cannot calculate)."""
        result = calculate_ship_dep_ratio(100, 0)
        assert result is None

    def test_negative_depletions_returns_none(self) -> None:
        """Test that negative depletions returns None."""
        result = calculate_ship_dep_ratio(100, -50)
        assert result is None

    def test_zero_shipments_returns_zero(self) -> None:
        """Test that zero shipments with positive depletions returns 0."""
        result = calculate_ship_dep_ratio(0, 200)
        assert result is not None
        assert result == 0.0

    def test_large_values(self) -> None:
        """Test with large values."""
        # 1,000,000 shipped, 500,000 depleted = 2.0
        result = calculate_ship_dep_ratio(1_000_000, 500_000)
        assert result is not None
        assert abs(result - 2.0) < 0.001

    def test_fractional_result(self) -> None:
        """Test fractional ratio calculation."""
        # 150 shipped, 200 depleted = 0.75
        result = calculate_ship_dep_ratio(150, 200)
        assert result is not None
        assert abs(result - 0.75) < 0.001


class TestShipDepRatioMetricsDataclass:
    """Tests for the ShipDepRatioMetrics dataclass."""

    def test_create_metrics(self) -> None:
        """Test creating a ShipDepRatioMetrics instance."""
        sku_id = uuid.uuid4()
        now = datetime.now(UTC)
        metrics = ShipDepRatioMetrics(
            sku="UFBub250",
            sku_id=sku_id,
            shipment_30d=300,
            depletion_30d=200,
            ratio_30d=1.5,
            shipment_90d=900,
            depletion_90d=600,
            ratio_90d=1.5,
            calculated_at=now,
        )

        assert metrics.sku == "UFBub250"
        assert metrics.sku_id == sku_id
        assert metrics.shipment_30d == 300
        assert metrics.depletion_30d == 200
        assert metrics.ratio_30d == 1.5
        assert metrics.shipment_90d == 900
        assert metrics.depletion_90d == 600
        assert metrics.ratio_90d == 1.5
        assert metrics.calculated_at == now

    def test_metrics_with_none_ratio(self) -> None:
        """Test creating metrics with None ratio (zero depletion case)."""
        sku_id = uuid.uuid4()
        now = datetime.now(UTC)
        metrics = ShipDepRatioMetrics(
            sku="UFRos250",
            sku_id=sku_id,
            shipment_30d=100,
            depletion_30d=0,
            ratio_30d=None,
            shipment_90d=300,
            depletion_90d=0,
            ratio_90d=None,
            calculated_at=now,
        )

        assert metrics.ratio_30d is None
        assert metrics.ratio_90d is None

    def test_metrics_immutable(self) -> None:
        """Test that ShipDepRatioMetrics is immutable (frozen dataclass)."""
        sku_id = uuid.uuid4()
        now = datetime.now(UTC)
        metrics = ShipDepRatioMetrics(
            sku="UFRed250",
            sku_id=sku_id,
            shipment_30d=300,
            depletion_30d=200,
            ratio_30d=1.5,
            shipment_90d=900,
            depletion_90d=600,
            ratio_90d=1.5,
            calculated_at=now,
        )

        with pytest.raises(AttributeError):
            metrics.sku = "NewSKU"  # type: ignore


class TestGetShipmentTotal:
    """Tests for the get_shipment_total function."""

    @pytest.mark.asyncio
    async def test_get_shipment_total_basic(self) -> None:
        """Test basic shipment total retrieval."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 500
        mock_session.execute.return_value = mock_result

        sku_id = uuid.uuid4()
        result = await get_shipment_total(mock_session, sku_id, days=30)

        assert result == 500
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_shipment_total_returns_zero_when_none(self) -> None:
        """Test that None result returns 0."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_session.execute.return_value = mock_result

        sku_id = uuid.uuid4()
        result = await get_shipment_total(mock_session, sku_id, days=30)

        assert result == 0

    @pytest.mark.asyncio
    async def test_get_shipment_total_with_warehouse_filter(self) -> None:
        """Test shipment total with warehouse filter."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 200
        mock_session.execute.return_value = mock_result

        sku_id = uuid.uuid4()
        warehouse_id = uuid.uuid4()
        result = await get_shipment_total(
            mock_session, sku_id, days=30, warehouse_id=warehouse_id
        )

        assert result == 200

    @pytest.mark.asyncio
    async def test_get_shipment_total_with_distributor_filter(self) -> None:
        """Test shipment total with distributor filter."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 150
        mock_session.execute.return_value = mock_result

        sku_id = uuid.uuid4()
        distributor_id = uuid.uuid4()
        result = await get_shipment_total(
            mock_session, sku_id, days=30, distributor_id=distributor_id
        )

        assert result == 150

    @pytest.mark.asyncio
    async def test_get_shipment_total_with_as_of_date(self) -> None:
        """Test shipment total with custom as_of date."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 300
        mock_session.execute.return_value = mock_result

        sku_id = uuid.uuid4()
        as_of = datetime(2026, 1, 15, tzinfo=UTC)
        result = await get_shipment_total(
            mock_session, sku_id, days=30, as_of=as_of
        )

        assert result == 300


class TestCalculateShipDepRatioForSku:
    """Tests for the calculate_ship_dep_ratio_for_sku function."""

    @pytest.mark.asyncio
    async def test_calculate_ratio_for_sku_basic(self) -> None:
        """Test basic SKU ratio calculation."""
        mock_session = AsyncMock()
        sku_id = uuid.uuid4()

        # Mock product query
        mock_product = MagicMock()
        mock_product.sku = "UFBub250"
        mock_product.id = sku_id

        with patch(
            "src.services.metrics.get_shipment_total",
            new_callable=AsyncMock,
        ) as mock_get_ship:
            # Return 300 for 30d, 900 for 90d
            mock_get_ship.side_effect = [300, 900]

            with patch(
                "src.services.metrics.get_depletion_total",
                new_callable=AsyncMock,
            ) as mock_get_dep:
                # Return 200 for 30d, 600 for 90d
                mock_get_dep.side_effect = [200, 600]

                # Mock the product query result
                product_result = MagicMock()
                product_result.scalar_one.return_value = mock_product
                mock_session.execute.return_value = product_result

                result = await calculate_ship_dep_ratio_for_sku(mock_session, sku_id)

                assert result.sku == "UFBub250"
                assert result.sku_id == sku_id
                assert result.shipment_30d == 300
                assert result.depletion_30d == 200
                assert result.ratio_30d is not None
                assert abs(result.ratio_30d - 1.5) < 0.001
                assert result.shipment_90d == 900
                assert result.depletion_90d == 600
                assert result.ratio_90d is not None
                assert abs(result.ratio_90d - 1.5) < 0.001

    @pytest.mark.asyncio
    async def test_calculate_ratio_for_sku_zero_depletion(self) -> None:
        """Test SKU ratio calculation with zero depletion."""
        mock_session = AsyncMock()
        sku_id = uuid.uuid4()

        mock_product = MagicMock()
        mock_product.sku = "UFRos250"
        mock_product.id = sku_id

        with patch(
            "src.services.metrics.get_shipment_total",
            new_callable=AsyncMock,
        ) as mock_get_ship:
            mock_get_ship.return_value = 100  # Some shipments

            with patch(
                "src.services.metrics.get_depletion_total",
                new_callable=AsyncMock,
            ) as mock_get_dep:
                mock_get_dep.return_value = 0  # Zero depletions

                product_result = MagicMock()
                product_result.scalar_one.return_value = mock_product
                mock_session.execute.return_value = product_result

                result = await calculate_ship_dep_ratio_for_sku(mock_session, sku_id)

                assert result.sku == "UFRos250"
                assert result.ratio_30d is None  # Cannot calculate with zero depletion
                assert result.ratio_90d is None

    @pytest.mark.asyncio
    async def test_calculate_ratio_for_sku_with_filters(self) -> None:
        """Test SKU ratio calculation with warehouse and distributor filters."""
        mock_session = AsyncMock()
        sku_id = uuid.uuid4()
        warehouse_id = uuid.uuid4()
        distributor_id = uuid.uuid4()

        mock_product = MagicMock()
        mock_product.sku = "UFRed250"
        mock_product.id = sku_id

        with patch(
            "src.services.metrics.get_shipment_total",
            new_callable=AsyncMock,
        ) as mock_get_ship:
            mock_get_ship.side_effect = [150, 450]

            with patch(
                "src.services.metrics.get_depletion_total",
                new_callable=AsyncMock,
            ) as mock_get_dep:
                mock_get_dep.side_effect = [100, 300]

                product_result = MagicMock()
                product_result.scalar_one.return_value = mock_product
                mock_session.execute.return_value = product_result

                result = await calculate_ship_dep_ratio_for_sku(
                    mock_session,
                    sku_id,
                    warehouse_id=warehouse_id,
                    distributor_id=distributor_id,
                )

                assert result.ratio_30d is not None
                assert abs(result.ratio_30d - 1.5) < 0.001

                # Verify filters were passed
                assert mock_get_ship.call_count == 2
                call_args = mock_get_ship.call_args_list[0]
                assert call_args.kwargs["warehouse_id"] == warehouse_id
                assert call_args.kwargs["distributor_id"] == distributor_id


class TestCalculateShipDepRatioAllSkus:
    """Tests for the calculate_ship_dep_ratio_all_skus function."""

    @pytest.mark.asyncio
    async def test_calculate_ratio_all_skus(self) -> None:
        """Test calculating ratio metrics for all SKUs."""
        mock_session = AsyncMock()

        # Create mock products
        products = []
        for sku in ["UFBub250", "UFRos250", "UFRed250", "UFCha250"]:
            mock_product = MagicMock()
            mock_product.sku = sku
            mock_product.id = uuid.uuid4()
            products.append(mock_product)

        # Mock the products query
        products_result = MagicMock()
        products_result.scalars.return_value.all.return_value = products
        mock_session.execute.return_value = products_result

        # Mock calculate_ship_dep_ratio_for_sku
        with patch(
            "src.services.metrics.calculate_ship_dep_ratio_for_sku",
            new_callable=AsyncMock,
        ) as mock_calc:
            mock_calc.side_effect = [
                ShipDepRatioMetrics(
                    sku=p.sku,
                    sku_id=p.id,
                    shipment_30d=300,
                    depletion_30d=200,
                    ratio_30d=1.5,
                    shipment_90d=900,
                    depletion_90d=600,
                    ratio_90d=1.5,
                    calculated_at=datetime.now(UTC),
                )
                for p in products
            ]

            result = await calculate_ship_dep_ratio_all_skus(mock_session)

            assert len(result) == 4
            assert all(isinstance(m, ShipDepRatioMetrics) for m in result)
            skus = [m.sku for m in result]
            assert "UFBub250" in skus
            assert "UFRos250" in skus
            assert "UFRed250" in skus
            assert "UFCha250" in skus

    @pytest.mark.asyncio
    async def test_calculate_ratio_all_skus_empty(self) -> None:
        """Test calculating ratio metrics when no products exist."""
        mock_session = AsyncMock()

        products_result = MagicMock()
        products_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = products_result

        result = await calculate_ship_dep_ratio_all_skus(mock_session)

        assert result == []

    @pytest.mark.asyncio
    async def test_calculate_ratio_all_skus_with_filters(self) -> None:
        """Test calculating ratio metrics with filters."""
        mock_session = AsyncMock()
        warehouse_id = uuid.uuid4()
        distributor_id = uuid.uuid4()

        # Create mock products
        products = []
        for sku in ["UFBub250", "UFRos250"]:
            mock_product = MagicMock()
            mock_product.sku = sku
            mock_product.id = uuid.uuid4()
            products.append(mock_product)

        # Mock the products query
        products_result = MagicMock()
        products_result.scalars.return_value.all.return_value = products
        mock_session.execute.return_value = products_result

        # Mock calculate_ship_dep_ratio_for_sku
        with patch(
            "src.services.metrics.calculate_ship_dep_ratio_for_sku",
            new_callable=AsyncMock,
        ) as mock_calc:
            mock_calc.side_effect = [
                ShipDepRatioMetrics(
                    sku=p.sku,
                    sku_id=p.id,
                    shipment_30d=300,
                    depletion_30d=200,
                    ratio_30d=1.5,
                    shipment_90d=900,
                    depletion_90d=600,
                    ratio_90d=1.5,
                    calculated_at=datetime.now(UTC),
                )
                for p in products
            ]

            result = await calculate_ship_dep_ratio_all_skus(
                mock_session,
                warehouse_id=warehouse_id,
                distributor_id=distributor_id,
            )

            assert len(result) == 2

            # Verify filters were passed to each call
            assert mock_calc.call_count == 2
            for call in mock_calc.call_args_list:
                # Args are: session, product.id, warehouse_id, distributor_id, as_of
                assert call[0][2] == warehouse_id
                assert call[0][3] == distributor_id
