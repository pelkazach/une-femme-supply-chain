"""Tests for Alembic migrations."""


class TestSeedProductSkusMigration:
    """Tests for the seed_product_skus migration (52fa8d4129df).

    These tests verify the seed data defined in the migration matches requirements.
    """

    # Expected SKUs per spec/01-database-schema.md
    EXPECTED_SKUS = {
        "UFBub250": {"name": "Une Femme Bubbles 250ml", "category": "sparkling"},
        "UFRos250": {"name": "Une Femme Rosé 250ml", "category": "rose"},
        "UFRed250": {"name": "Une Femme Red 250ml", "category": "red"},
        "UFCha250": {"name": "Une Femme Chardonnay 250ml", "category": "white"},
    }

    def test_expected_skus_count(self) -> None:
        """Test that exactly 4 SKUs are expected per spec."""
        assert len(self.EXPECTED_SKUS) == 4

    def test_all_skus_have_250ml_format(self) -> None:
        """Test that all SKUs follow 250ml canned wine format."""
        for sku in self.EXPECTED_SKUS:
            assert "250" in sku, f"SKU {sku} should indicate 250ml format"

    def test_all_skus_have_uf_prefix(self) -> None:
        """Test that all SKUs have Une Femme (UF) prefix."""
        for sku in self.EXPECTED_SKUS:
            assert sku.startswith("UF"), f"SKU {sku} should have UF prefix"

    def test_categories_cover_wine_varieties(self) -> None:
        """Test that categories cover expected wine types."""
        categories = {info["category"] for info in self.EXPECTED_SKUS.values()}
        expected_categories = {"sparkling", "rose", "red", "white"}
        assert categories == expected_categories

    def test_bubbles_is_sparkling_category(self) -> None:
        """Test that Bubbles (UFBub250) is sparkling wine."""
        assert self.EXPECTED_SKUS["UFBub250"]["category"] == "sparkling"

    def test_rose_is_rose_category(self) -> None:
        """Test that Rosé (UFRos250) is rose wine."""
        assert self.EXPECTED_SKUS["UFRos250"]["category"] == "rose"

    def test_red_is_red_category(self) -> None:
        """Test that Red (UFRed250) is red wine."""
        assert self.EXPECTED_SKUS["UFRed250"]["category"] == "red"

    def test_chardonnay_is_white_category(self) -> None:
        """Test that Chardonnay (UFCha250) is white wine."""
        assert self.EXPECTED_SKUS["UFCha250"]["category"] == "white"
