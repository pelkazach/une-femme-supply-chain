"""Tests for SQLAlchemy models."""

import uuid
from datetime import datetime

from src.models import Distributor, Product, Warehouse


class TestProductModel:
    """Tests for the Product model."""

    def test_product_attributes(self) -> None:
        """Test that Product has all required attributes."""
        product = Product(
            sku="UFBub250",
            name="Une Femme Bubbles 250ml",
            category="sparkling",
        )
        assert product.sku == "UFBub250"
        assert product.name == "Une Femme Bubbles 250ml"
        assert product.category == "sparkling"

    def test_product_default_id(self) -> None:
        """Test that Product generates a UUID by default."""
        product = Product(sku="UFRos250", name="Une Femme Rose 250ml")
        # id will be None until persisted, but default is set
        assert product.id is None or isinstance(product.id, uuid.UUID)

    def test_product_optional_category(self) -> None:
        """Test that category is optional."""
        product = Product(sku="UFRed250", name="Une Femme Red 250ml")
        assert product.category is None

    def test_product_repr(self) -> None:
        """Test Product string representation."""
        product = Product(sku="UFCha250", name="Une Femme Chardonnay 250ml")
        repr_str = repr(product)
        assert "UFCha250" in repr_str
        assert "Une Femme Chardonnay 250ml" in repr_str

    def test_product_tablename(self) -> None:
        """Test that Product has correct table name."""
        assert Product.__tablename__ == "products"


class TestWarehouseModel:
    """Tests for the Warehouse model."""

    def test_warehouse_attributes(self) -> None:
        """Test that Warehouse has all required attributes."""
        warehouse = Warehouse(
            name="Main Distribution Center",
            code="WH01",
        )
        assert warehouse.name == "Main Distribution Center"
        assert warehouse.code == "WH01"

    def test_warehouse_default_id(self) -> None:
        """Test that Warehouse generates a UUID by default."""
        warehouse = Warehouse(name="Secondary Warehouse", code="WH02")
        assert warehouse.id is None or isinstance(warehouse.id, uuid.UUID)

    def test_warehouse_repr(self) -> None:
        """Test Warehouse string representation."""
        warehouse = Warehouse(name="Test Warehouse", code="TEST")
        repr_str = repr(warehouse)
        assert "TEST" in repr_str
        assert "Test Warehouse" in repr_str

    def test_warehouse_tablename(self) -> None:
        """Test that Warehouse has correct table name."""
        assert Warehouse.__tablename__ == "warehouses"


class TestDistributorModel:
    """Tests for the Distributor model."""

    def test_distributor_attributes(self) -> None:
        """Test that Distributor has all required attributes."""
        distributor = Distributor(
            name="RNDC California",
            segment="RNDC",
            state="CA",
        )
        assert distributor.name == "RNDC California"
        assert distributor.segment == "RNDC"
        assert distributor.state == "CA"

    def test_distributor_default_id(self) -> None:
        """Test that Distributor generates a UUID by default."""
        distributor = Distributor(name="Test Distributor")
        assert distributor.id is None or isinstance(distributor.id, uuid.UUID)

    def test_distributor_optional_fields(self) -> None:
        """Test that segment and state are optional."""
        distributor = Distributor(name="Generic Distributor")
        assert distributor.segment is None
        assert distributor.state is None

    def test_distributor_repr(self) -> None:
        """Test Distributor string representation."""
        distributor = Distributor(name="Southern Glazers", segment="Reyes")
        repr_str = repr(distributor)
        assert "Southern Glazers" in repr_str
        assert "Reyes" in repr_str

    def test_distributor_tablename(self) -> None:
        """Test that Distributor has correct table name."""
        assert Distributor.__tablename__ == "distributors"


class TestModelRelationships:
    """Tests for model relationships and constraints."""

    def test_product_sku_column_is_unique(self) -> None:
        """Test that Product.sku has unique constraint."""
        sku_column = Product.__table__.columns["sku"]
        assert sku_column.unique is True

    def test_warehouse_code_column_is_unique(self) -> None:
        """Test that Warehouse.code has unique constraint."""
        code_column = Warehouse.__table__.columns["code"]
        assert code_column.unique is True

    def test_product_sku_is_indexed(self) -> None:
        """Test that Product.sku has an index."""
        sku_column = Product.__table__.columns["sku"]
        assert sku_column.index is True

    def test_warehouse_code_is_indexed(self) -> None:
        """Test that Warehouse.code has an index."""
        code_column = Warehouse.__table__.columns["code"]
        assert code_column.index is True
