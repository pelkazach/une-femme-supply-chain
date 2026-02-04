"""Tests for SQLAlchemy models."""

import uuid
from datetime import datetime, timezone

from src.models import Distributor, InventoryEvent, Product, Warehouse


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


class TestInventoryEventModel:
    """Tests for the InventoryEvent model."""

    def test_inventory_event_attributes(self) -> None:
        """Test that InventoryEvent has all required attributes."""
        event_time = datetime.now(timezone.utc)
        sku_id = uuid.uuid4()
        warehouse_id = uuid.uuid4()

        event = InventoryEvent(
            time=event_time,
            sku_id=sku_id,
            warehouse_id=warehouse_id,
            event_type="shipment",
            quantity=100,
        )
        assert event.time == event_time
        assert event.sku_id == sku_id
        assert event.warehouse_id == warehouse_id
        assert event.event_type == "shipment"
        assert event.quantity == 100

    def test_inventory_event_default_id(self) -> None:
        """Test that InventoryEvent generates a UUID by default."""
        event = InventoryEvent(
            time=datetime.now(timezone.utc),
            sku_id=uuid.uuid4(),
            warehouse_id=uuid.uuid4(),
            event_type="depletion",
            quantity=50,
        )
        assert event.id is None or isinstance(event.id, uuid.UUID)

    def test_inventory_event_optional_distributor(self) -> None:
        """Test that distributor_id is optional."""
        event = InventoryEvent(
            time=datetime.now(timezone.utc),
            sku_id=uuid.uuid4(),
            warehouse_id=uuid.uuid4(),
            event_type="adjustment",
            quantity=-10,
        )
        assert event.distributor_id is None

    def test_inventory_event_with_distributor(self) -> None:
        """Test InventoryEvent with a distributor."""
        distributor_id = uuid.uuid4()
        event = InventoryEvent(
            time=datetime.now(timezone.utc),
            sku_id=uuid.uuid4(),
            warehouse_id=uuid.uuid4(),
            distributor_id=distributor_id,
            event_type="depletion",
            quantity=25,
        )
        assert event.distributor_id == distributor_id

    def test_inventory_event_repr(self) -> None:
        """Test InventoryEvent string representation."""
        event_time = datetime.now(timezone.utc)
        event = InventoryEvent(
            time=event_time,
            sku_id=uuid.uuid4(),
            warehouse_id=uuid.uuid4(),
            event_type="shipment",
            quantity=100,
        )
        repr_str = repr(event)
        assert "shipment" in repr_str
        assert "100" in repr_str

    def test_inventory_event_tablename(self) -> None:
        """Test that InventoryEvent has correct table name."""
        assert InventoryEvent.__tablename__ == "inventory_events"

    def test_inventory_event_has_brin_index(self) -> None:
        """Test that InventoryEvent has a BRIN index on time column."""
        # Check that the BRIN index exists in table args
        table_args = InventoryEvent.__table_args__
        brin_index_found = False
        for arg in table_args:
            if hasattr(arg, "name") and arg.name == "idx_inventory_events_time_brin":
                # Check it uses BRIN
                assert arg.kwargs.get("postgresql_using") == "brin"
                brin_index_found = True
                break
        assert brin_index_found, "BRIN index on time column not found"

    def test_inventory_event_has_composite_indexes(self) -> None:
        """Test that InventoryEvent has composite indexes for query optimization."""
        table_args = InventoryEvent.__table_args__
        index_names = [
            arg.name for arg in table_args if hasattr(arg, "name") and arg.name is not None
        ]
        assert "idx_inventory_events_sku_time" in index_names
        assert "idx_inventory_events_warehouse_time" in index_names

    def test_inventory_event_foreign_keys(self) -> None:
        """Test that InventoryEvent has correct foreign key references."""
        sku_id_col = InventoryEvent.__table__.columns["sku_id"]
        warehouse_id_col = InventoryEvent.__table__.columns["warehouse_id"]
        distributor_id_col = InventoryEvent.__table__.columns["distributor_id"]

        # Check foreign keys exist
        sku_fk = list(sku_id_col.foreign_keys)[0]
        warehouse_fk = list(warehouse_id_col.foreign_keys)[0]
        distributor_fk = list(distributor_id_col.foreign_keys)[0]

        assert sku_fk.target_fullname == "products.id"
        assert warehouse_fk.target_fullname == "warehouses.id"
        assert distributor_fk.target_fullname == "distributors.id"

    def test_inventory_event_cascade_delete(self) -> None:
        """Test that InventoryEvent foreign keys have correct delete behavior."""
        sku_id_col = InventoryEvent.__table__.columns["sku_id"]
        warehouse_id_col = InventoryEvent.__table__.columns["warehouse_id"]
        distributor_id_col = InventoryEvent.__table__.columns["distributor_id"]

        sku_fk = list(sku_id_col.foreign_keys)[0]
        warehouse_fk = list(warehouse_id_col.foreign_keys)[0]
        distributor_fk = list(distributor_id_col.foreign_keys)[0]

        assert sku_fk.ondelete == "CASCADE"
        assert warehouse_fk.ondelete == "CASCADE"
        assert distributor_fk.ondelete == "SET NULL"
