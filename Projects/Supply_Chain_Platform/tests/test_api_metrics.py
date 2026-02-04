"""Tests for inventory metrics API endpoints."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.main import app
from src.services.metrics import (
    DOHMetrics,
    ShipDepRatioMetrics,
    VelocityTrendMetrics,
)


@pytest.fixture
def mock_products() -> list[MagicMock]:
    """Create mock products for testing."""
    products = []
    for sku in ["UFBub250", "UFRos250", "UFRed250", "UFCha250"]:
        mock_product = MagicMock()
        mock_product.sku = sku
        mock_product.id = uuid.uuid4()
        products.append(mock_product)
    return products


@pytest.fixture
def mock_doh_metrics(mock_products: list[MagicMock]) -> list[DOHMetrics]:
    """Create mock DOH metrics for testing."""
    now = datetime.now(UTC)
    return [
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
            calculated_at=now,
        )
        for p in mock_products
    ]


@pytest.fixture
def mock_ship_dep_metrics(mock_products: list[MagicMock]) -> list[ShipDepRatioMetrics]:
    """Create mock shipment:depletion ratio metrics for testing."""
    now = datetime.now(UTC)
    return [
        ShipDepRatioMetrics(
            sku=p.sku,
            sku_id=p.id,
            shipment_30d=300,
            depletion_30d=200,
            ratio_30d=1.5,
            shipment_90d=900,
            depletion_90d=600,
            ratio_90d=1.5,
            calculated_at=now,
        )
        for p in mock_products
    ]


@pytest.fixture
def mock_velocity_metrics(mock_products: list[MagicMock]) -> list[VelocityTrendMetrics]:
    """Create mock velocity trend metrics for testing."""
    now = datetime.now(UTC)
    return [
        VelocityTrendMetrics(
            sku=p.sku,
            sku_id=p.id,
            depletion_30d=3000,
            depletion_90d=7200,
            daily_rate_30d_dep=100.0,
            daily_rate_90d_dep=80.0,
            velocity_trend_dep=1.25,
            shipment_30d=2700,
            shipment_90d=6300,
            daily_rate_30d_ship=90.0,
            daily_rate_90d_ship=70.0,
            velocity_trend_ship=1.286,
            calculated_at=now,
        )
        for p in mock_products
    ]


class TestGetMetrics:
    """Tests for GET /metrics endpoint."""

    def test_get_metrics_success(
        self,
        mock_products: list[MagicMock],
        mock_doh_metrics: list[DOHMetrics],
        mock_ship_dep_metrics: list[ShipDepRatioMetrics],
        mock_velocity_metrics: list[VelocityTrendMetrics],
    ) -> None:
        """Test successful retrieval of all metrics for all SKUs."""
        mock_session = AsyncMock(spec=AsyncSession)

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.metrics.calculate_doh_t30_all_skus",
                new_callable=AsyncMock,
            ) as mock_doh:
                mock_doh.return_value = mock_doh_metrics

                with patch(
                    "src.api.metrics.calculate_ship_dep_ratio_all_skus",
                    new_callable=AsyncMock,
                ) as mock_ship_dep:
                    mock_ship_dep.return_value = mock_ship_dep_metrics

                    with patch(
                        "src.api.metrics.calculate_velocity_trend_all_skus",
                        new_callable=AsyncMock,
                    ) as mock_velocity:
                        mock_velocity.return_value = mock_velocity_metrics

                        client = TestClient(app)
                        response = client.get("/metrics")

                        assert response.status_code == status.HTTP_200_OK
                        data = response.json()

                        assert "skus" in data
                        assert "total_skus" in data
                        assert "calculated_at" in data
                        assert data["total_skus"] == 4

                        # Verify all 4 SKUs are present
                        skus = [sku["sku"] for sku in data["skus"]]
                        assert "UFBub250" in skus
                        assert "UFRos250" in skus
                        assert "UFRed250" in skus
                        assert "UFCha250" in skus

                        # Verify metrics structure
                        first_sku = data["skus"][0]
                        assert "doh" in first_sku
                        assert "ship_dep_ratio" in first_sku
                        assert "velocity_trend" in first_sku

                        # Verify DOH metrics
                        assert "doh_t30" in first_sku["doh"]
                        assert "doh_t90" in first_sku["doh"]
                        assert "current_inventory" in first_sku["doh"]

                        # Verify shipment:depletion ratio metrics
                        assert "ratio_30d" in first_sku["ship_dep_ratio"]
                        assert "ratio_90d" in first_sku["ship_dep_ratio"]

                        # Verify velocity trend metrics
                        assert "velocity_trend_dep" in first_sku["velocity_trend"]
                        assert "velocity_trend_ship" in first_sku["velocity_trend"]
        finally:
            app.dependency_overrides.clear()

    def test_get_metrics_with_warehouse_filter(
        self,
        mock_products: list[MagicMock],
        mock_doh_metrics: list[DOHMetrics],
        mock_ship_dep_metrics: list[ShipDepRatioMetrics],
        mock_velocity_metrics: list[VelocityTrendMetrics],
    ) -> None:
        """Test metrics retrieval with warehouse filter."""
        mock_session = AsyncMock(spec=AsyncSession)
        warehouse_id = uuid.uuid4()

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.metrics.calculate_doh_t30_all_skus",
                new_callable=AsyncMock,
            ) as mock_doh:
                mock_doh.return_value = mock_doh_metrics

                with patch(
                    "src.api.metrics.calculate_ship_dep_ratio_all_skus",
                    new_callable=AsyncMock,
                ) as mock_ship_dep:
                    mock_ship_dep.return_value = mock_ship_dep_metrics

                    with patch(
                        "src.api.metrics.calculate_velocity_trend_all_skus",
                        new_callable=AsyncMock,
                    ) as mock_velocity:
                        mock_velocity.return_value = mock_velocity_metrics

                        client = TestClient(app)
                        response = client.get(
                            "/metrics",
                            params={"warehouse_id": str(warehouse_id)},
                        )

                        assert response.status_code == status.HTTP_200_OK
                        data = response.json()
                        assert data["warehouse_id"] == str(warehouse_id)

                        # Verify filters were passed
                        mock_doh.assert_called_once()
                        assert mock_doh.call_args.kwargs["warehouse_id"] == warehouse_id
        finally:
            app.dependency_overrides.clear()

    def test_get_metrics_with_warehouse_code_filter(
        self,
        mock_products: list[MagicMock],
        mock_doh_metrics: list[DOHMetrics],
        mock_ship_dep_metrics: list[ShipDepRatioMetrics],
        mock_velocity_metrics: list[VelocityTrendMetrics],
    ) -> None:
        """Test metrics retrieval with warehouse code filter."""
        mock_session = AsyncMock(spec=AsyncSession)
        warehouse_id = uuid.uuid4()

        # Mock warehouse lookup
        mock_warehouse = MagicMock()
        mock_warehouse.id = warehouse_id
        mock_warehouse.code = "WH001"

        warehouse_result = MagicMock()
        warehouse_result.scalar_one_or_none.return_value = mock_warehouse
        mock_session.execute.return_value = warehouse_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.metrics.calculate_doh_t30_all_skus",
                new_callable=AsyncMock,
            ) as mock_doh:
                mock_doh.return_value = mock_doh_metrics

                with patch(
                    "src.api.metrics.calculate_ship_dep_ratio_all_skus",
                    new_callable=AsyncMock,
                ) as mock_ship_dep:
                    mock_ship_dep.return_value = mock_ship_dep_metrics

                    with patch(
                        "src.api.metrics.calculate_velocity_trend_all_skus",
                        new_callable=AsyncMock,
                    ) as mock_velocity:
                        mock_velocity.return_value = mock_velocity_metrics

                        client = TestClient(app)
                        response = client.get(
                            "/metrics",
                            params={"warehouse_code": "WH001"},
                        )

                        assert response.status_code == status.HTTP_200_OK
                        data = response.json()
                        assert data["warehouse_id"] == str(warehouse_id)
        finally:
            app.dependency_overrides.clear()

    def test_get_metrics_warehouse_code_not_found(self) -> None:
        """Test 404 when warehouse code not found."""
        mock_session = AsyncMock(spec=AsyncSession)

        # Mock warehouse lookup returns None
        warehouse_result = MagicMock()
        warehouse_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = warehouse_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            client = TestClient(app)
            response = client.get(
                "/metrics",
                params={"warehouse_code": "UNKNOWN"},
            )

            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()

    def test_get_metrics_with_distributor_filter(
        self,
        mock_products: list[MagicMock],
        mock_doh_metrics: list[DOHMetrics],
        mock_ship_dep_metrics: list[ShipDepRatioMetrics],
        mock_velocity_metrics: list[VelocityTrendMetrics],
    ) -> None:
        """Test metrics retrieval with distributor filter."""
        mock_session = AsyncMock(spec=AsyncSession)
        distributor_id = uuid.uuid4()

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.metrics.calculate_doh_t30_all_skus",
                new_callable=AsyncMock,
            ) as mock_doh:
                mock_doh.return_value = mock_doh_metrics

                with patch(
                    "src.api.metrics.calculate_ship_dep_ratio_all_skus",
                    new_callable=AsyncMock,
                ) as mock_ship_dep:
                    mock_ship_dep.return_value = mock_ship_dep_metrics

                    with patch(
                        "src.api.metrics.calculate_velocity_trend_all_skus",
                        new_callable=AsyncMock,
                    ) as mock_velocity:
                        mock_velocity.return_value = mock_velocity_metrics

                        client = TestClient(app)
                        response = client.get(
                            "/metrics",
                            params={"distributor_id": str(distributor_id)},
                        )

                        assert response.status_code == status.HTTP_200_OK
                        data = response.json()
                        assert data["distributor_id"] == str(distributor_id)

                        # Verify filters were passed
                        mock_ship_dep.assert_called_once()
                        assert mock_ship_dep.call_args.kwargs["distributor_id"] == distributor_id
                        mock_velocity.assert_called_once()
                        assert mock_velocity.call_args.kwargs["distributor_id"] == distributor_id
        finally:
            app.dependency_overrides.clear()

    def test_get_metrics_distributor_name_not_found(self) -> None:
        """Test 404 when distributor name not found."""
        mock_session = AsyncMock(spec=AsyncSession)

        # Mock distributor lookup returns None
        distributor_result = MagicMock()
        distributor_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = distributor_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            client = TestClient(app)
            response = client.get(
                "/metrics",
                params={"distributor_name": "UNKNOWN"},
            )

            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()

    def test_get_metrics_empty_skus(self) -> None:
        """Test metrics endpoint when no SKUs exist."""
        mock_session = AsyncMock(spec=AsyncSession)

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.metrics.calculate_doh_t30_all_skus",
                new_callable=AsyncMock,
            ) as mock_doh:
                mock_doh.return_value = []

                with patch(
                    "src.api.metrics.calculate_ship_dep_ratio_all_skus",
                    new_callable=AsyncMock,
                ) as mock_ship_dep:
                    mock_ship_dep.return_value = []

                    with patch(
                        "src.api.metrics.calculate_velocity_trend_all_skus",
                        new_callable=AsyncMock,
                    ) as mock_velocity:
                        mock_velocity.return_value = []

                        client = TestClient(app)
                        response = client.get("/metrics")

                        assert response.status_code == status.HTTP_200_OK
                        data = response.json()
                        assert data["total_skus"] == 0
                        assert data["skus"] == []
        finally:
            app.dependency_overrides.clear()


class TestGetMetricsBySku:
    """Tests for GET /metrics/{sku} endpoint."""

    def test_get_metrics_by_sku_success(self, mock_products: list[MagicMock]) -> None:
        """Test successful retrieval of metrics for a specific SKU."""
        mock_session = AsyncMock(spec=AsyncSession)
        product = mock_products[0]  # UFBub250
        now = datetime.now(UTC)

        # Mock product lookup
        product_result = MagicMock()
        product_result.scalar_one_or_none.return_value = product
        mock_session.execute.return_value = product_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.metrics.calculate_doh_t30_for_sku",
                new_callable=AsyncMock,
            ) as mock_doh:
                mock_doh.return_value = DOHMetrics(
                    sku=product.sku,
                    sku_id=product.id,
                    current_inventory=1000,
                    doh_t30=100.0,
                    depletion_30d=300,
                    daily_rate_30d=10.0,
                    doh_t90=100.0,
                    depletion_90d=900,
                    daily_rate_90d=10.0,
                    calculated_at=now,
                )

                with patch(
                    "src.api.metrics.calculate_ship_dep_ratio_for_sku",
                    new_callable=AsyncMock,
                ) as mock_ship_dep:
                    mock_ship_dep.return_value = ShipDepRatioMetrics(
                        sku=product.sku,
                        sku_id=product.id,
                        shipment_30d=300,
                        depletion_30d=200,
                        ratio_30d=1.5,
                        shipment_90d=900,
                        depletion_90d=600,
                        ratio_90d=1.5,
                        calculated_at=now,
                    )

                    with patch(
                        "src.api.metrics.calculate_velocity_trend_for_sku",
                        new_callable=AsyncMock,
                    ) as mock_velocity:
                        mock_velocity.return_value = VelocityTrendMetrics(
                            sku=product.sku,
                            sku_id=product.id,
                            depletion_30d=3000,
                            depletion_90d=7200,
                            daily_rate_30d_dep=100.0,
                            daily_rate_90d_dep=80.0,
                            velocity_trend_dep=1.25,
                            shipment_30d=2700,
                            shipment_90d=6300,
                            daily_rate_30d_ship=90.0,
                            daily_rate_90d_ship=70.0,
                            velocity_trend_ship=1.286,
                            calculated_at=now,
                        )

                        client = TestClient(app)
                        response = client.get("/metrics/UFBub250")

                        assert response.status_code == status.HTTP_200_OK
                        data = response.json()

                        assert data["sku"] == "UFBub250"
                        assert "doh" in data
                        assert "ship_dep_ratio" in data
                        assert "velocity_trend" in data

                        # Verify DOH metrics
                        assert data["doh"]["doh_t30"] == 100.0
                        assert data["doh"]["doh_t90"] == 100.0
                        assert data["doh"]["current_inventory"] == 1000

                        # Verify shipment:depletion ratio metrics
                        assert data["ship_dep_ratio"]["ratio_30d"] == 1.5
                        assert data["ship_dep_ratio"]["ratio_90d"] == 1.5

                        # Verify velocity trend metrics
                        assert data["velocity_trend"]["velocity_trend_dep"] == 1.25
        finally:
            app.dependency_overrides.clear()

    def test_get_metrics_by_sku_not_found(self) -> None:
        """Test 404 when SKU is not tracked in the system."""
        mock_session = AsyncMock(spec=AsyncSession)

        # Mock product lookup returns None
        product_result = MagicMock()
        product_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = product_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            client = TestClient(app)
            response = client.get("/metrics/UNKNOWN_SKU")

            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "not tracked" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_get_metrics_by_sku_with_filters(
        self, mock_products: list[MagicMock]
    ) -> None:
        """Test metrics by SKU with warehouse and distributor filters."""
        mock_session = AsyncMock(spec=AsyncSession)
        product = mock_products[0]
        warehouse_id = uuid.uuid4()
        distributor_id = uuid.uuid4()
        now = datetime.now(UTC)

        # Mock product lookup
        product_result = MagicMock()
        product_result.scalar_one_or_none.return_value = product
        mock_session.execute.return_value = product_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.metrics.calculate_doh_t30_for_sku",
                new_callable=AsyncMock,
            ) as mock_doh:
                mock_doh.return_value = DOHMetrics(
                    sku=product.sku,
                    sku_id=product.id,
                    current_inventory=500,
                    doh_t30=50.0,
                    depletion_30d=300,
                    daily_rate_30d=10.0,
                    doh_t90=50.0,
                    depletion_90d=900,
                    daily_rate_90d=10.0,
                    calculated_at=now,
                )

                with patch(
                    "src.api.metrics.calculate_ship_dep_ratio_for_sku",
                    new_callable=AsyncMock,
                ) as mock_ship_dep:
                    mock_ship_dep.return_value = ShipDepRatioMetrics(
                        sku=product.sku,
                        sku_id=product.id,
                        shipment_30d=150,
                        depletion_30d=100,
                        ratio_30d=1.5,
                        shipment_90d=450,
                        depletion_90d=300,
                        ratio_90d=1.5,
                        calculated_at=now,
                    )

                    with patch(
                        "src.api.metrics.calculate_velocity_trend_for_sku",
                        new_callable=AsyncMock,
                    ) as mock_velocity:
                        mock_velocity.return_value = VelocityTrendMetrics(
                            sku=product.sku,
                            sku_id=product.id,
                            depletion_30d=1500,
                            depletion_90d=3600,
                            daily_rate_30d_dep=50.0,
                            daily_rate_90d_dep=40.0,
                            velocity_trend_dep=1.25,
                            shipment_30d=1350,
                            shipment_90d=3150,
                            daily_rate_30d_ship=45.0,
                            daily_rate_90d_ship=35.0,
                            velocity_trend_ship=1.286,
                            calculated_at=now,
                        )

                        client = TestClient(app)
                        response = client.get(
                            "/metrics/UFBub250",
                            params={
                                "warehouse_id": str(warehouse_id),
                                "distributor_id": str(distributor_id),
                            },
                        )

                        assert response.status_code == status.HTTP_200_OK

                        # Verify filters were passed
                        mock_doh.assert_called_once()
                        assert mock_doh.call_args.kwargs["warehouse_id"] == warehouse_id

                        mock_ship_dep.assert_called_once()
                        assert mock_ship_dep.call_args.kwargs["warehouse_id"] == warehouse_id
                        assert mock_ship_dep.call_args.kwargs["distributor_id"] == distributor_id

                        mock_velocity.assert_called_once()
                        assert mock_velocity.call_args.kwargs["warehouse_id"] == warehouse_id
                        assert mock_velocity.call_args.kwargs["distributor_id"] == distributor_id
        finally:
            app.dependency_overrides.clear()

    def test_get_metrics_by_sku_with_none_values(
        self, mock_products: list[MagicMock]
    ) -> None:
        """Test metrics by SKU when some metrics are None (e.g., zero depletions)."""
        mock_session = AsyncMock(spec=AsyncSession)
        product = mock_products[0]
        now = datetime.now(UTC)

        # Mock product lookup
        product_result = MagicMock()
        product_result.scalar_one_or_none.return_value = product
        mock_session.execute.return_value = product_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "src.api.metrics.calculate_doh_t30_for_sku",
                new_callable=AsyncMock,
            ) as mock_doh:
                # DOH is None because there are no depletions
                mock_doh.return_value = DOHMetrics(
                    sku=product.sku,
                    sku_id=product.id,
                    current_inventory=1000,
                    doh_t30=None,
                    depletion_30d=0,
                    daily_rate_30d=None,
                    doh_t90=None,
                    depletion_90d=0,
                    daily_rate_90d=None,
                    calculated_at=now,
                )

                with patch(
                    "src.api.metrics.calculate_ship_dep_ratio_for_sku",
                    new_callable=AsyncMock,
                ) as mock_ship_dep:
                    # Ratio is None because there are no depletions
                    mock_ship_dep.return_value = ShipDepRatioMetrics(
                        sku=product.sku,
                        sku_id=product.id,
                        shipment_30d=100,
                        depletion_30d=0,
                        ratio_30d=None,
                        shipment_90d=300,
                        depletion_90d=0,
                        ratio_90d=None,
                        calculated_at=now,
                    )

                    with patch(
                        "src.api.metrics.calculate_velocity_trend_for_sku",
                        new_callable=AsyncMock,
                    ) as mock_velocity:
                        # Velocity trend is None because there's no historical data
                        mock_velocity.return_value = VelocityTrendMetrics(
                            sku=product.sku,
                            sku_id=product.id,
                            depletion_30d=100,
                            depletion_90d=0,
                            daily_rate_30d_dep=3.33,
                            daily_rate_90d_dep=0.0,
                            velocity_trend_dep=None,
                            shipment_30d=200,
                            shipment_90d=0,
                            daily_rate_30d_ship=6.67,
                            daily_rate_90d_ship=0.0,
                            velocity_trend_ship=None,
                            calculated_at=now,
                        )

                        client = TestClient(app)
                        response = client.get("/metrics/UFBub250")

                        assert response.status_code == status.HTTP_200_OK
                        data = response.json()

                        # Verify None values are returned correctly
                        assert data["doh"]["doh_t30"] is None
                        assert data["doh"]["doh_t90"] is None
                        assert data["ship_dep_ratio"]["ratio_30d"] is None
                        assert data["ship_dep_ratio"]["ratio_90d"] is None
                        assert data["velocity_trend"]["velocity_trend_dep"] is None
                        assert data["velocity_trend"]["velocity_trend_ship"] is None
        finally:
            app.dependency_overrides.clear()


class TestMetricsQueryPerformance:
    """Tests for metrics query performance requirements."""

    def test_metrics_endpoint_accepts_all_tracked_skus(
        self, mock_products: list[MagicMock]
    ) -> None:
        """Test that metrics endpoint works for all 4 tracked SKUs."""
        mock_session = AsyncMock(spec=AsyncSession)
        now = datetime.now(UTC)

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            for sku_code in ["UFBub250", "UFRos250", "UFRed250", "UFCha250"]:
                # Find the matching product
                product = next(p for p in mock_products if p.sku == sku_code)

                # Mock product lookup
                product_result = MagicMock()
                product_result.scalar_one_or_none.return_value = product
                mock_session.execute.return_value = product_result

                with patch(
                    "src.api.metrics.calculate_doh_t30_for_sku",
                    new_callable=AsyncMock,
                ) as mock_doh:
                    mock_doh.return_value = DOHMetrics(
                        sku=product.sku,
                        sku_id=product.id,
                        current_inventory=1000,
                        doh_t30=100.0,
                        depletion_30d=300,
                        daily_rate_30d=10.0,
                        doh_t90=100.0,
                        depletion_90d=900,
                        daily_rate_90d=10.0,
                        calculated_at=now,
                    )

                    with patch(
                        "src.api.metrics.calculate_ship_dep_ratio_for_sku",
                        new_callable=AsyncMock,
                    ) as mock_ship_dep:
                        mock_ship_dep.return_value = ShipDepRatioMetrics(
                            sku=product.sku,
                            sku_id=product.id,
                            shipment_30d=300,
                            depletion_30d=200,
                            ratio_30d=1.5,
                            shipment_90d=900,
                            depletion_90d=600,
                            ratio_90d=1.5,
                            calculated_at=now,
                        )

                        with patch(
                            "src.api.metrics.calculate_velocity_trend_for_sku",
                            new_callable=AsyncMock,
                        ) as mock_velocity:
                            mock_velocity.return_value = VelocityTrendMetrics(
                                sku=product.sku,
                                sku_id=product.id,
                                depletion_30d=3000,
                                depletion_90d=7200,
                                daily_rate_30d_dep=100.0,
                                daily_rate_90d_dep=80.0,
                                velocity_trend_dep=1.25,
                                shipment_30d=2700,
                                shipment_90d=6300,
                                daily_rate_30d_ship=90.0,
                                daily_rate_90d_ship=70.0,
                                velocity_trend_ship=1.286,
                                calculated_at=now,
                            )

                            client = TestClient(app)
                            response = client.get(f"/metrics/{sku_code}")

                            assert response.status_code == status.HTTP_200_OK
                            data = response.json()
                            assert data["sku"] == sku_code
        finally:
            app.dependency_overrides.clear()
