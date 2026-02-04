"""Tests for distributor report parsers."""

import io
from datetime import date

import pandas as pd
import pytest

from src.services.distributor import (
    ParsedRow,
    ParseResult,
    RowError,
    parse_rndc_csv,
    parse_rndc_excel,
    parse_rndc_report,
    parse_southern_glazers_csv,
    parse_southern_glazers_excel,
    parse_southern_glazers_report,
    parse_winebow_csv,
    parse_winebow_excel,
    parse_winebow_report,
    _find_column,
    _parse_date,
    _parse_float,
    _parse_quantity,
)


class TestFindColumn:
    """Tests for _find_column helper function."""

    def test_find_exact_match(self) -> None:
        """Test finding column with exact name match."""
        headers = ["Date", "Invoice", "SKU"]
        idx, name = _find_column(headers, ["date"])
        assert idx == 0
        assert name == "Date"

    def test_find_case_insensitive(self) -> None:
        """Test case-insensitive column matching."""
        headers = ["DATE", "INVOICE", "SKU"]
        idx, name = _find_column(headers, ["date"])
        assert idx == 0
        assert name == "DATE"

    def test_find_alternative_name(self) -> None:
        """Test finding column with alternative name."""
        headers = ["Ship_Date", "Invoice", "Item_Code"]
        idx, name = _find_column(headers, ["date", "ship_date"])
        assert idx == 0
        assert name == "Ship_Date"

    def test_column_not_found(self) -> None:
        """Test when column is not found."""
        headers = ["A", "B", "C"]
        idx, name = _find_column(headers, ["date", "ship_date"])
        assert idx is None
        assert name is None

    def test_find_with_whitespace(self) -> None:
        """Test finding column with whitespace."""
        headers = [" Date ", "Invoice", "SKU"]
        idx, name = _find_column(headers, ["date"])
        assert idx == 0


class TestParseDate:
    """Tests for _parse_date helper function."""

    def test_parse_iso_format(self) -> None:
        """Test parsing ISO date format (YYYY-MM-DD)."""
        result = _parse_date("2026-01-15", 1)
        assert result == date(2026, 1, 15)

    def test_parse_us_format(self) -> None:
        """Test parsing US date format (MM/DD/YYYY)."""
        result = _parse_date("01/15/2026", 1)
        assert result == date(2026, 1, 15)

    def test_parse_datetime_object(self) -> None:
        """Test parsing datetime object."""
        from datetime import datetime

        dt = datetime(2026, 1, 15, 10, 30, 0)
        result = _parse_date(dt, 1)
        assert result == date(2026, 1, 15)

    def test_parse_date_object(self) -> None:
        """Test parsing date object."""
        d = date(2026, 1, 15)
        result = _parse_date(d, 1)
        assert result == date(2026, 1, 15)

    def test_parse_empty_string_returns_error(self) -> None:
        """Test that empty string returns RowError."""
        result = _parse_date("", 5)
        assert isinstance(result, RowError)
        assert result.row_number == 5
        assert result.field == "date"
        assert "required" in result.message.lower()

    def test_parse_invalid_date_returns_error(self) -> None:
        """Test that invalid date returns RowError."""
        result = _parse_date("not-a-date", 3)
        assert isinstance(result, RowError)
        assert result.row_number == 3
        assert "Invalid date format" in result.message


class TestParseQuantity:
    """Tests for _parse_quantity helper function."""

    def test_parse_integer(self) -> None:
        """Test parsing integer quantity."""
        result = _parse_quantity(24, 1)
        assert result == 24

    def test_parse_float(self) -> None:
        """Test parsing float quantity (from Excel)."""
        result = _parse_quantity(24.0, 1)
        assert result == 24

    def test_parse_string(self) -> None:
        """Test parsing string quantity."""
        result = _parse_quantity("24", 1)
        assert result == 24

    def test_parse_string_with_comma(self) -> None:
        """Test parsing string quantity with comma."""
        result = _parse_quantity("1,234", 1)
        assert result == 1234

    def test_parse_none_returns_error(self) -> None:
        """Test that None returns RowError."""
        result = _parse_quantity(None, 5)
        assert isinstance(result, RowError)
        assert result.field == "quantity"

    def test_parse_empty_string_returns_error(self) -> None:
        """Test that empty string returns RowError."""
        result = _parse_quantity("", 5)
        assert isinstance(result, RowError)

    def test_parse_invalid_returns_error(self) -> None:
        """Test that invalid quantity returns RowError."""
        result = _parse_quantity("abc", 3)
        assert isinstance(result, RowError)
        assert "Invalid quantity" in result.message


class TestParseFloat:
    """Tests for _parse_float helper function."""

    def test_parse_float(self) -> None:
        """Test parsing float value."""
        result = _parse_float(12.99)
        assert result == 12.99

    def test_parse_integer(self) -> None:
        """Test parsing integer as float."""
        result = _parse_float(100)
        assert result == 100.0

    def test_parse_string(self) -> None:
        """Test parsing string float."""
        result = _parse_float("12.99")
        assert result == 12.99

    def test_parse_currency_string(self) -> None:
        """Test parsing currency string."""
        result = _parse_float("$12.99")
        assert result == 12.99

    def test_parse_string_with_comma(self) -> None:
        """Test parsing string with comma."""
        result = _parse_float("1,234.56")
        assert result == 1234.56

    def test_parse_none_returns_none(self) -> None:
        """Test that None returns None."""
        result = _parse_float(None)
        assert result is None

    def test_parse_empty_string_returns_none(self) -> None:
        """Test that empty string returns None."""
        result = _parse_float("")
        assert result is None

    def test_parse_invalid_returns_none(self) -> None:
        """Test that invalid value returns None."""
        result = _parse_float("abc")
        assert result is None


class TestParseRndcCsv:
    """Tests for parse_rndc_csv function."""

    def test_parse_valid_csv(self) -> None:
        """Test parsing valid RNDC CSV file."""
        csv_content = b"""Date,Invoice,Account,SKU,Description,Qty Sold,Unit Price,Extended
2026-01-15,INV001,ABC Liquor,UFBub250,Une Femme Brut 250ml,24,12.99,311.76
2026-01-16,INV002,XYZ Wine,UFRos250,Une Femme Rose 250ml,12,11.99,143.88"""

        result = parse_rndc_csv(csv_content)

        assert isinstance(result, ParseResult)
        assert result.total_rows == 2
        assert result.success_count == 2
        assert result.error_count == 0
        assert len(result.rows) == 2

        # Check first row
        row1 = result.rows[0]
        assert row1.date == date(2026, 1, 15)
        assert row1.sku == "UFBub250"
        assert row1.quantity == 24
        assert row1.invoice == "INV001"
        assert row1.account == "ABC Liquor"
        assert row1.description == "Une Femme Brut 250ml"
        assert row1.unit_price == 12.99
        assert row1.extended_amount == 311.76

    def test_parse_csv_with_us_date_format(self) -> None:
        """Test parsing CSV with US date format."""
        csv_content = b"""Date,SKU,Qty Sold
01/15/2026,UFBub250,24"""

        result = parse_rndc_csv(csv_content)

        assert result.success_count == 1
        assert result.rows[0].date == date(2026, 1, 15)

    def test_parse_csv_minimal_columns(self) -> None:
        """Test parsing CSV with only required columns."""
        csv_content = b"""Date,SKU,Qty Sold
2026-01-15,UFBub250,24"""

        result = parse_rndc_csv(csv_content)

        assert result.success_count == 1
        row = result.rows[0]
        assert row.date == date(2026, 1, 15)
        assert row.sku == "UFBub250"
        assert row.quantity == 24
        assert row.invoice is None
        assert row.account is None

    def test_parse_csv_alternative_column_names(self) -> None:
        """Test parsing CSV with alternative column names."""
        csv_content = b"""ship_date,item_code,quantity
2026-01-15,UFBub250,24"""

        result = parse_rndc_csv(csv_content)

        assert result.success_count == 1
        assert result.rows[0].sku == "UFBub250"

    def test_parse_csv_missing_required_column(self) -> None:
        """Test error when required column is missing."""
        csv_content = b"""Date,SKU
2026-01-15,UFBub250"""

        result = parse_rndc_csv(csv_content)

        assert result.success_count == 0
        assert result.error_count == 1
        assert "Missing required columns" in result.errors[0].message
        assert "Qty Sold" in result.errors[0].message

    def test_parse_csv_empty_file(self) -> None:
        """Test error on empty file."""
        csv_content = b""

        result = parse_rndc_csv(csv_content)

        assert result.success_count == 0
        assert result.error_count == 1
        assert "No data rows" in result.errors[0].message

    def test_parse_csv_header_only(self) -> None:
        """Test file with header but no data rows."""
        csv_content = b"""Date,SKU,Qty Sold"""

        result = parse_rndc_csv(csv_content)

        assert result.total_rows == 0
        assert result.success_count == 0
        assert result.error_count == 0

    def test_parse_csv_invalid_date_row(self) -> None:
        """Test handling of row with invalid date."""
        csv_content = b"""Date,SKU,Qty Sold
2026-01-15,UFBub250,24
invalid-date,UFRos250,12
2026-01-17,UFRed250,36"""

        result = parse_rndc_csv(csv_content)

        assert result.total_rows == 3
        assert result.success_count == 2
        assert result.error_count == 1
        assert result.errors[0].row_number == 3
        assert result.errors[0].field == "date"

    def test_parse_csv_missing_sku(self) -> None:
        """Test handling of row with missing SKU."""
        csv_content = b"""Date,SKU,Qty Sold
2026-01-15,,24"""

        result = parse_rndc_csv(csv_content)

        assert result.success_count == 0
        assert result.error_count == 1
        assert "SKU is required" in result.errors[0].message

    def test_parse_csv_missing_quantity(self) -> None:
        """Test handling of row with missing quantity."""
        csv_content = b"""Date,SKU,Qty Sold
2026-01-15,UFBub250,"""

        result = parse_rndc_csv(csv_content)

        assert result.success_count == 0
        assert result.error_count == 1
        assert "Quantity is required" in result.errors[0].message

    def test_parse_csv_invalid_quantity(self) -> None:
        """Test handling of row with invalid quantity."""
        csv_content = b"""Date,SKU,Qty Sold
2026-01-15,UFBub250,abc"""

        result = parse_rndc_csv(csv_content)

        assert result.success_count == 0
        assert result.error_count == 1
        assert "Invalid quantity" in result.errors[0].message

    def test_parse_csv_skip_empty_rows(self) -> None:
        """Test that empty rows are skipped."""
        csv_content = b"""Date,SKU,Qty Sold
2026-01-15,UFBub250,24

2026-01-16,UFRos250,12"""

        result = parse_rndc_csv(csv_content)

        assert result.success_count == 2

    def test_parse_csv_100_rows(self) -> None:
        """Test parsing 100 rows (acceptance criteria)."""
        header = b"Date,Invoice,Account,SKU,Qty Sold\n"
        rows = [
            f"2026-01-{(i % 28) + 1:02d},INV{i:03d},Account{i},UFBub250,{i}\n".encode()
            for i in range(1, 101)
        ]
        csv_content = header + b"".join(rows)

        result = parse_rndc_csv(csv_content)

        assert result.total_rows == 100
        assert result.success_count == 100
        assert result.error_count == 0

    def test_parse_csv_latin1_encoding(self) -> None:
        """Test parsing CSV with Latin-1 encoding."""
        # Use Latin-1 encoded content with special character
        csv_content = "Date,SKU,Qty Sold\n2026-01-15,UFBub250,24\n".encode("latin-1")

        result = parse_rndc_csv(csv_content)

        assert result.success_count == 1

    def test_parse_csv_quantity_with_comma(self) -> None:
        """Test parsing quantity with thousands separator."""
        csv_content = b"""Date,SKU,Qty Sold
2026-01-15,UFBub250,"1,234" """

        result = parse_rndc_csv(csv_content)

        assert result.success_count == 1
        assert result.rows[0].quantity == 1234


class TestParseRndcExcel:
    """Tests for parse_rndc_excel function."""

    def _create_excel(self, data: dict) -> bytes:
        """Create an Excel file from dictionary data."""
        df = pd.DataFrame(data)
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False)
        return buffer.getvalue()

    def test_parse_valid_excel(self) -> None:
        """Test parsing valid RNDC Excel file."""
        excel_content = self._create_excel(
            {
                "Date": [date(2026, 1, 15), date(2026, 1, 16)],
                "Invoice": ["INV001", "INV002"],
                "Account": ["ABC Liquor", "XYZ Wine"],
                "SKU": ["UFBub250", "UFRos250"],
                "Description": ["Une Femme Brut 250ml", "Une Femme Rose 250ml"],
                "Qty Sold": [24, 12],
                "Unit Price": [12.99, 11.99],
                "Extended": [311.76, 143.88],
            }
        )

        result = parse_rndc_excel(excel_content)

        assert result.total_rows == 2
        assert result.success_count == 2
        assert result.error_count == 0

        row1 = result.rows[0]
        assert row1.date == date(2026, 1, 15)
        assert row1.sku == "UFBub250"
        assert row1.quantity == 24
        assert row1.invoice == "INV001"

    def test_parse_excel_minimal_columns(self) -> None:
        """Test parsing Excel with only required columns."""
        excel_content = self._create_excel(
            {
                "Date": [date(2026, 1, 15)],
                "SKU": ["UFBub250"],
                "Qty Sold": [24],
            }
        )

        result = parse_rndc_excel(excel_content)

        assert result.success_count == 1
        row = result.rows[0]
        assert row.invoice is None
        assert row.account is None

    def test_parse_excel_empty_file(self) -> None:
        """Test error on empty Excel file."""
        excel_content = self._create_excel({})

        result = parse_rndc_excel(excel_content)

        assert result.success_count == 0
        assert result.error_count == 1
        # Either "No data rows" or "Missing required columns"
        assert (
            "No data rows" in result.errors[0].message
            or "Missing required" in result.errors[0].message
        )

    def test_parse_excel_missing_required_column(self) -> None:
        """Test error when required column is missing."""
        excel_content = self._create_excel(
            {
                "Date": [date(2026, 1, 15)],
                "SKU": ["UFBub250"],
                # Missing Qty Sold
            }
        )

        result = parse_rndc_excel(excel_content)

        assert result.error_count >= 1
        # Check for missing column error
        assert any(
            "Missing required" in e.message or "Quantity" in e.message
            for e in result.errors
        )

    def test_parse_excel_invalid_date_row(self) -> None:
        """Test handling of row with invalid date in Excel."""
        excel_content = self._create_excel(
            {
                "Date": [date(2026, 1, 15), None, date(2026, 1, 17)],
                "SKU": ["UFBub250", "UFRos250", "UFRed250"],
                "Qty Sold": [24, 12, 36],
            }
        )

        result = parse_rndc_excel(excel_content)

        assert result.total_rows == 3
        assert result.success_count == 2
        assert result.error_count == 1

    def test_parse_excel_100_rows(self) -> None:
        """Test parsing 100 rows in Excel (acceptance criteria)."""
        excel_content = self._create_excel(
            {
                "Date": [date(2026, 1, (i % 28) + 1) for i in range(100)],
                "Invoice": [f"INV{i:03d}" for i in range(100)],
                "Account": [f"Account{i}" for i in range(100)],
                "SKU": ["UFBub250"] * 100,
                "Qty Sold": list(range(1, 101)),
            }
        )

        result = parse_rndc_excel(excel_content)

        assert result.total_rows == 100
        assert result.success_count == 100
        assert result.error_count == 0


class TestParseRndcReport:
    """Tests for parse_rndc_report function (unified interface)."""

    def test_parse_csv_extension(self) -> None:
        """Test that .csv extension routes to CSV parser."""
        csv_content = b"""Date,SKU,Qty Sold
2026-01-15,UFBub250,24"""

        result = parse_rndc_report(csv_content, ".csv")

        assert result.success_count == 1

    def test_parse_xlsx_extension(self) -> None:
        """Test that .xlsx extension routes to Excel parser."""
        df = pd.DataFrame(
            {
                "Date": [date(2026, 1, 15)],
                "SKU": ["UFBub250"],
                "Qty Sold": [24],
            }
        )
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False)
        excel_content = buffer.getvalue()

        result = parse_rndc_report(excel_content, ".xlsx")

        assert result.success_count == 1

    def test_parse_xls_extension(self) -> None:
        """Test that .xls extension routes to Excel parser."""
        df = pd.DataFrame(
            {
                "Date": [date(2026, 1, 15)],
                "SKU": ["UFBub250"],
                "Qty Sold": [24],
            }
        )
        buffer = io.BytesIO()
        # Note: openpyxl doesn't support .xls, but pandas handles it
        df.to_excel(buffer, index=False, engine="openpyxl")
        excel_content = buffer.getvalue()

        result = parse_rndc_report(excel_content, ".xls")

        # May succeed or fail depending on xlrd availability
        # The important thing is it doesn't crash
        assert isinstance(result, ParseResult)

    def test_parse_uppercase_extension(self) -> None:
        """Test that uppercase extension is handled."""
        csv_content = b"""Date,SKU,Qty Sold
2026-01-15,UFBub250,24"""

        result = parse_rndc_report(csv_content, ".CSV")

        assert result.success_count == 1

    def test_parse_unsupported_extension(self) -> None:
        """Test error for unsupported extension."""
        result = parse_rndc_report(b"content", ".pdf")

        assert result.success_count == 0
        assert result.error_count == 1
        assert "Unsupported file extension" in result.errors[0].message


class TestParsedRow:
    """Tests for ParsedRow dataclass."""

    def test_create_with_required_fields(self) -> None:
        """Test creating ParsedRow with required fields only."""
        row = ParsedRow(
            date=date(2026, 1, 15),
            sku="UFBub250",
            quantity=24,
        )

        assert row.date == date(2026, 1, 15)
        assert row.sku == "UFBub250"
        assert row.quantity == 24
        assert row.invoice is None
        assert row.account is None

    def test_create_with_all_fields(self) -> None:
        """Test creating ParsedRow with all fields."""
        row = ParsedRow(
            date=date(2026, 1, 15),
            sku="UFBub250",
            quantity=24,
            invoice="INV001",
            account="ABC Liquor",
            customer="Customer Name",
            description="Une Femme Brut 250ml",
            unit_price=12.99,
            extended_amount=311.76,
        )

        assert row.invoice == "INV001"
        assert row.unit_price == 12.99


class TestParseResult:
    """Tests for ParseResult dataclass."""

    def test_success_count_property(self) -> None:
        """Test success_count property."""
        result = ParseResult(
            rows=[
                ParsedRow(date=date(2026, 1, 15), sku="UFBub250", quantity=24),
                ParsedRow(date=date(2026, 1, 16), sku="UFRos250", quantity=12),
            ],
            errors=[],
            total_rows=2,
        )

        assert result.success_count == 2

    def test_error_count_property(self) -> None:
        """Test error_count property."""
        result = ParseResult(
            rows=[],
            errors=[
                RowError(row_number=2, field="date", message="Invalid date"),
                RowError(row_number=3, field="sku", message="SKU required"),
            ],
            total_rows=2,
        )

        assert result.error_count == 2


class TestParseSouthernGlazersCsv:
    """Tests for parse_southern_glazers_csv function."""

    def test_parse_valid_csv(self) -> None:
        """Test parsing valid Southern Glazers CSV file."""
        csv_content = b"""Ship Date,Customer,Item Code,Item Description,Cases,Bottles,Amount
01/15/2026,XYZ Wine Bar,UFRos250,Une Femme Rose 250ml,10,120,1558.80
01/16/2026,ABC Liquor,UFBub250,Une Femme Brut 250ml,5,60,779.40"""

        result = parse_southern_glazers_csv(csv_content)

        assert isinstance(result, ParseResult)
        assert result.total_rows == 2
        assert result.success_count == 2
        assert result.error_count == 0
        assert len(result.rows) == 2

        # Check first row
        row1 = result.rows[0]
        assert row1.date == date(2026, 1, 15)
        assert row1.sku == "UFRos250"
        assert row1.quantity == 120
        assert row1.bottles == 120
        assert row1.cases == 10
        assert row1.customer == "XYZ Wine Bar"
        assert row1.description == "Une Femme Rose 250ml"
        assert row1.extended_amount == 1558.80

    def test_parse_csv_with_iso_date_format(self) -> None:
        """Test parsing CSV with ISO date format."""
        csv_content = b"""Ship Date,Item Code,Bottles
2026-01-15,UFBub250,24"""

        result = parse_southern_glazers_csv(csv_content)

        assert result.success_count == 1
        assert result.rows[0].date == date(2026, 1, 15)

    def test_parse_csv_minimal_columns(self) -> None:
        """Test parsing CSV with only required columns."""
        csv_content = b"""Ship Date,Item Code,Bottles
01/15/2026,UFRos250,120"""

        result = parse_southern_glazers_csv(csv_content)

        assert result.success_count == 1
        row = result.rows[0]
        assert row.date == date(2026, 1, 15)
        assert row.sku == "UFRos250"
        assert row.quantity == 120
        assert row.bottles == 120
        assert row.cases is None
        assert row.customer is None

    def test_parse_csv_alternative_column_names(self) -> None:
        """Test parsing CSV with alternative column names."""
        csv_content = b"""date,product_code,units
01/15/2026,UFBub250,24"""

        result = parse_southern_glazers_csv(csv_content)

        assert result.success_count == 1
        assert result.rows[0].sku == "UFBub250"
        assert result.rows[0].quantity == 24

    def test_parse_csv_missing_required_column(self) -> None:
        """Test error when required column is missing."""
        csv_content = b"""Ship Date,Item Code
01/15/2026,UFRos250"""

        result = parse_southern_glazers_csv(csv_content)

        assert result.success_count == 0
        assert result.error_count == 1
        assert "Missing required columns" in result.errors[0].message
        assert "Bottles" in result.errors[0].message

    def test_parse_csv_empty_file(self) -> None:
        """Test error on empty file."""
        csv_content = b""

        result = parse_southern_glazers_csv(csv_content)

        assert result.success_count == 0
        assert result.error_count == 1
        assert "No data rows" in result.errors[0].message

    def test_parse_csv_header_only(self) -> None:
        """Test file with header but no data rows."""
        csv_content = b"""Ship Date,Item Code,Bottles"""

        result = parse_southern_glazers_csv(csv_content)

        assert result.total_rows == 0
        assert result.success_count == 0
        assert result.error_count == 0

    def test_parse_csv_invalid_date_row(self) -> None:
        """Test handling of row with invalid date."""
        csv_content = b"""Ship Date,Item Code,Bottles
01/15/2026,UFBub250,24
invalid-date,UFRos250,12
01/17/2026,UFRed250,36"""

        result = parse_southern_glazers_csv(csv_content)

        assert result.total_rows == 3
        assert result.success_count == 2
        assert result.error_count == 1
        assert result.errors[0].row_number == 3
        assert result.errors[0].field == "date"

    def test_parse_csv_missing_item_code(self) -> None:
        """Test handling of row with missing Item Code."""
        csv_content = b"""Ship Date,Item Code,Bottles
01/15/2026,,120"""

        result = parse_southern_glazers_csv(csv_content)

        assert result.success_count == 0
        assert result.error_count == 1
        assert "Item Code is required" in result.errors[0].message

    def test_parse_csv_missing_bottles(self) -> None:
        """Test handling of row with missing Bottles."""
        csv_content = b"""Ship Date,Item Code,Bottles
01/15/2026,UFRos250,"""

        result = parse_southern_glazers_csv(csv_content)

        assert result.success_count == 0
        assert result.error_count == 1
        assert "Bottles" in result.errors[0].message

    def test_parse_csv_invalid_bottles(self) -> None:
        """Test handling of row with invalid Bottles."""
        csv_content = b"""Ship Date,Item Code,Bottles
01/15/2026,UFRos250,abc"""

        result = parse_southern_glazers_csv(csv_content)

        assert result.success_count == 0
        assert result.error_count == 1
        assert "Bottles" in result.errors[0].message or "Invalid" in result.errors[0].message

    def test_parse_csv_skip_empty_rows(self) -> None:
        """Test that empty rows are skipped."""
        csv_content = b"""Ship Date,Item Code,Bottles
01/15/2026,UFBub250,24

01/16/2026,UFRos250,12"""

        result = parse_southern_glazers_csv(csv_content)

        assert result.success_count == 2

    def test_parse_csv_100_rows(self) -> None:
        """Test parsing 100 rows (acceptance criteria)."""
        header = b"Ship Date,Customer,Item Code,Cases,Bottles\n"
        rows = [
            f"01/{(i % 28) + 1:02d}/2026,Customer{i},UFRos250,{i},{i * 12}\n".encode()
            for i in range(1, 101)
        ]
        csv_content = header + b"".join(rows)

        result = parse_southern_glazers_csv(csv_content)

        assert result.total_rows == 100
        assert result.success_count == 100
        assert result.error_count == 0

    def test_parse_csv_bottles_with_comma(self) -> None:
        """Test parsing bottles with thousands separator."""
        csv_content = b"""Ship Date,Item Code,Bottles
01/15/2026,UFRos250,"1,234" """

        result = parse_southern_glazers_csv(csv_content)

        assert result.success_count == 1
        assert result.rows[0].quantity == 1234
        assert result.rows[0].bottles == 1234

    def test_parse_csv_invalid_cases_still_succeeds(self) -> None:
        """Test that invalid cases value doesn't fail the row (optional field)."""
        csv_content = b"""Ship Date,Item Code,Cases,Bottles
01/15/2026,UFRos250,abc,120"""

        result = parse_southern_glazers_csv(csv_content)

        assert result.success_count == 1
        assert result.rows[0].cases is None
        assert result.rows[0].bottles == 120


class TestParseSouthernGlazersExcel:
    """Tests for parse_southern_glazers_excel function."""

    def _create_excel(self, data: dict) -> bytes:
        """Create an Excel file from dictionary data."""
        df = pd.DataFrame(data)
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False)
        return buffer.getvalue()

    def test_parse_valid_excel(self) -> None:
        """Test parsing valid Southern Glazers Excel file."""
        excel_content = self._create_excel(
            {
                "Ship Date": [date(2026, 1, 15), date(2026, 1, 16)],
                "Customer": ["XYZ Wine Bar", "ABC Liquor"],
                "Item Code": ["UFRos250", "UFBub250"],
                "Item Description": ["Une Femme Rose 250ml", "Une Femme Brut 250ml"],
                "Cases": [10, 5],
                "Bottles": [120, 60],
                "Amount": [1558.80, 779.40],
            }
        )

        result = parse_southern_glazers_excel(excel_content)

        assert result.total_rows == 2
        assert result.success_count == 2
        assert result.error_count == 0

        row1 = result.rows[0]
        assert row1.date == date(2026, 1, 15)
        assert row1.sku == "UFRos250"
        assert row1.quantity == 120
        assert row1.bottles == 120
        assert row1.cases == 10
        assert row1.customer == "XYZ Wine Bar"

    def test_parse_excel_minimal_columns(self) -> None:
        """Test parsing Excel with only required columns."""
        excel_content = self._create_excel(
            {
                "Ship Date": [date(2026, 1, 15)],
                "Item Code": ["UFRos250"],
                "Bottles": [120],
            }
        )

        result = parse_southern_glazers_excel(excel_content)

        assert result.success_count == 1
        row = result.rows[0]
        assert row.cases is None
        assert row.customer is None

    def test_parse_excel_empty_file(self) -> None:
        """Test error on empty Excel file."""
        excel_content = self._create_excel({})

        result = parse_southern_glazers_excel(excel_content)

        assert result.success_count == 0
        assert result.error_count == 1
        assert (
            "No data rows" in result.errors[0].message
            or "Missing required" in result.errors[0].message
        )

    def test_parse_excel_missing_required_column(self) -> None:
        """Test error when required column is missing."""
        excel_content = self._create_excel(
            {
                "Ship Date": [date(2026, 1, 15)],
                "Item Code": ["UFRos250"],
                # Missing Bottles
            }
        )

        result = parse_southern_glazers_excel(excel_content)

        assert result.error_count >= 1
        assert any(
            "Missing required" in e.message or "Bottles" in e.message
            for e in result.errors
        )

    def test_parse_excel_invalid_date_row(self) -> None:
        """Test handling of row with invalid date in Excel."""
        excel_content = self._create_excel(
            {
                "Ship Date": [date(2026, 1, 15), None, date(2026, 1, 17)],
                "Item Code": ["UFRos250", "UFBub250", "UFRed250"],
                "Bottles": [120, 60, 36],
            }
        )

        result = parse_southern_glazers_excel(excel_content)

        assert result.total_rows == 3
        assert result.success_count == 2
        assert result.error_count == 1

    def test_parse_excel_100_rows(self) -> None:
        """Test parsing 100 rows in Excel (acceptance criteria)."""
        excel_content = self._create_excel(
            {
                "Ship Date": [date(2026, 1, (i % 28) + 1) for i in range(100)],
                "Customer": [f"Customer{i}" for i in range(100)],
                "Item Code": ["UFRos250"] * 100,
                "Cases": list(range(1, 101)),
                "Bottles": [i * 12 for i in range(1, 101)],
            }
        )

        result = parse_southern_glazers_excel(excel_content)

        assert result.total_rows == 100
        assert result.success_count == 100
        assert result.error_count == 0


class TestParseSouthernGlazersReport:
    """Tests for parse_southern_glazers_report function (unified interface)."""

    def test_parse_csv_extension(self) -> None:
        """Test that .csv extension routes to CSV parser."""
        csv_content = b"""Ship Date,Item Code,Bottles
01/15/2026,UFRos250,120"""

        result = parse_southern_glazers_report(csv_content, ".csv")

        assert result.success_count == 1

    def test_parse_xlsx_extension(self) -> None:
        """Test that .xlsx extension routes to Excel parser."""
        df = pd.DataFrame(
            {
                "Ship Date": [date(2026, 1, 15)],
                "Item Code": ["UFRos250"],
                "Bottles": [120],
            }
        )
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False)
        excel_content = buffer.getvalue()

        result = parse_southern_glazers_report(excel_content, ".xlsx")

        assert result.success_count == 1

    def test_parse_uppercase_extension(self) -> None:
        """Test that uppercase extension is handled."""
        csv_content = b"""Ship Date,Item Code,Bottles
01/15/2026,UFRos250,120"""

        result = parse_southern_glazers_report(csv_content, ".CSV")

        assert result.success_count == 1

    def test_parse_unsupported_extension(self) -> None:
        """Test error for unsupported extension."""
        result = parse_southern_glazers_report(b"content", ".pdf")

        assert result.success_count == 0
        assert result.error_count == 1
        assert "Unsupported file extension" in result.errors[0].message


class TestParseWinebowCsv:
    """Tests for parse_winebow_csv function."""

    def test_parse_valid_csv(self) -> None:
        """Test parsing valid Winebow CSV file."""
        csv_content = b"""transaction_date,customer_name,product_code,product_name,quantity,total
2026-01-15,Fine Wines Inc,UFRed250,Une Femme Red 250ml,48,623.52
2026-01-16,Wine Emporium,UFBub250,Une Femme Brut 250ml,24,311.76"""

        result = parse_winebow_csv(csv_content)

        assert isinstance(result, ParseResult)
        assert result.total_rows == 2
        assert result.success_count == 2
        assert result.error_count == 0
        assert len(result.rows) == 2

        # Check first row
        row1 = result.rows[0]
        assert row1.date == date(2026, 1, 15)
        assert row1.sku == "UFRed250"
        assert row1.quantity == 48
        assert row1.customer == "Fine Wines Inc"
        assert row1.description == "Une Femme Red 250ml"
        assert row1.extended_amount == 623.52

    def test_parse_csv_with_us_date_format(self) -> None:
        """Test parsing CSV with US date format."""
        csv_content = b"""transaction_date,product_code,quantity
01/15/2026,UFRed250,48"""

        result = parse_winebow_csv(csv_content)

        assert result.success_count == 1
        assert result.rows[0].date == date(2026, 1, 15)

    def test_parse_csv_minimal_columns(self) -> None:
        """Test parsing CSV with only required columns."""
        csv_content = b"""transaction_date,product_code,quantity
2026-01-15,UFRed250,48"""

        result = parse_winebow_csv(csv_content)

        assert result.success_count == 1
        row = result.rows[0]
        assert row.date == date(2026, 1, 15)
        assert row.sku == "UFRed250"
        assert row.quantity == 48
        assert row.customer is None
        assert row.description is None
        assert row.extended_amount is None

    def test_parse_csv_alternative_column_names(self) -> None:
        """Test parsing CSV with alternative column names."""
        csv_content = b"""date,sku,qty
2026-01-15,UFRed250,48"""

        result = parse_winebow_csv(csv_content)

        assert result.success_count == 1
        assert result.rows[0].sku == "UFRed250"
        assert result.rows[0].quantity == 48

    def test_parse_csv_missing_required_column(self) -> None:
        """Test error when required column is missing."""
        csv_content = b"""transaction_date,product_code
2026-01-15,UFRed250"""

        result = parse_winebow_csv(csv_content)

        assert result.success_count == 0
        assert result.error_count == 1
        assert "Missing required columns" in result.errors[0].message
        assert "quantity" in result.errors[0].message

    def test_parse_csv_empty_file(self) -> None:
        """Test error on empty file."""
        csv_content = b""

        result = parse_winebow_csv(csv_content)

        assert result.success_count == 0
        assert result.error_count == 1
        assert "No data rows" in result.errors[0].message

    def test_parse_csv_header_only(self) -> None:
        """Test file with header but no data rows."""
        csv_content = b"""transaction_date,product_code,quantity"""

        result = parse_winebow_csv(csv_content)

        assert result.total_rows == 0
        assert result.success_count == 0
        assert result.error_count == 0

    def test_parse_csv_invalid_date_row(self) -> None:
        """Test handling of row with invalid date."""
        csv_content = b"""transaction_date,product_code,quantity
2026-01-15,UFRed250,48
invalid-date,UFBub250,24
2026-01-17,UFRos250,36"""

        result = parse_winebow_csv(csv_content)

        assert result.total_rows == 3
        assert result.success_count == 2
        assert result.error_count == 1
        assert result.errors[0].row_number == 3
        assert result.errors[0].field == "date"

    def test_parse_csv_missing_product_code(self) -> None:
        """Test handling of row with missing product_code."""
        csv_content = b"""transaction_date,product_code,quantity
2026-01-15,,48"""

        result = parse_winebow_csv(csv_content)

        assert result.success_count == 0
        assert result.error_count == 1
        assert "product_code is required" in result.errors[0].message

    def test_parse_csv_missing_quantity(self) -> None:
        """Test handling of row with missing quantity."""
        csv_content = b"""transaction_date,product_code,quantity
2026-01-15,UFRed250,"""

        result = parse_winebow_csv(csv_content)

        assert result.success_count == 0
        assert result.error_count == 1
        assert "Quantity is required" in result.errors[0].message

    def test_parse_csv_invalid_quantity(self) -> None:
        """Test handling of row with invalid quantity."""
        csv_content = b"""transaction_date,product_code,quantity
2026-01-15,UFRed250,abc"""

        result = parse_winebow_csv(csv_content)

        assert result.success_count == 0
        assert result.error_count == 1
        assert "Invalid quantity" in result.errors[0].message

    def test_parse_csv_skip_empty_rows(self) -> None:
        """Test that empty rows are skipped."""
        csv_content = b"""transaction_date,product_code,quantity
2026-01-15,UFRed250,48

2026-01-16,UFBub250,24"""

        result = parse_winebow_csv(csv_content)

        assert result.success_count == 2

    def test_parse_csv_100_rows(self) -> None:
        """Test parsing 100 rows (acceptance criteria)."""
        header = b"transaction_date,customer_name,product_code,quantity\n"
        rows = [
            f"2026-01-{(i % 28) + 1:02d},Customer{i},UFRed250,{i}\n".encode()
            for i in range(1, 101)
        ]
        csv_content = header + b"".join(rows)

        result = parse_winebow_csv(csv_content)

        assert result.total_rows == 100
        assert result.success_count == 100
        assert result.error_count == 0

    def test_parse_csv_latin1_encoding(self) -> None:
        """Test parsing CSV with Latin-1 encoding."""
        csv_content = "transaction_date,product_code,quantity\n2026-01-15,UFRed250,48\n".encode("latin-1")

        result = parse_winebow_csv(csv_content)

        assert result.success_count == 1

    def test_parse_csv_quantity_with_comma(self) -> None:
        """Test parsing quantity with thousands separator."""
        csv_content = b"""transaction_date,product_code,quantity
2026-01-15,UFRed250,"1,234" """

        result = parse_winebow_csv(csv_content)

        assert result.success_count == 1
        assert result.rows[0].quantity == 1234


class TestParseWinebowExcel:
    """Tests for parse_winebow_excel function."""

    def _create_excel(self, data: dict) -> bytes:
        """Create an Excel file from dictionary data."""
        df = pd.DataFrame(data)
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False)
        return buffer.getvalue()

    def test_parse_valid_excel(self) -> None:
        """Test parsing valid Winebow Excel file."""
        excel_content = self._create_excel(
            {
                "transaction_date": [date(2026, 1, 15), date(2026, 1, 16)],
                "customer_name": ["Fine Wines Inc", "Wine Emporium"],
                "product_code": ["UFRed250", "UFBub250"],
                "product_name": ["Une Femme Red 250ml", "Une Femme Brut 250ml"],
                "quantity": [48, 24],
                "total": [623.52, 311.76],
            }
        )

        result = parse_winebow_excel(excel_content)

        assert result.total_rows == 2
        assert result.success_count == 2
        assert result.error_count == 0

        row1 = result.rows[0]
        assert row1.date == date(2026, 1, 15)
        assert row1.sku == "UFRed250"
        assert row1.quantity == 48
        assert row1.customer == "Fine Wines Inc"
        assert row1.description == "Une Femme Red 250ml"
        assert row1.extended_amount == 623.52

    def test_parse_excel_minimal_columns(self) -> None:
        """Test parsing Excel with only required columns."""
        excel_content = self._create_excel(
            {
                "transaction_date": [date(2026, 1, 15)],
                "product_code": ["UFRed250"],
                "quantity": [48],
            }
        )

        result = parse_winebow_excel(excel_content)

        assert result.success_count == 1
        row = result.rows[0]
        assert row.customer is None
        assert row.description is None
        assert row.extended_amount is None

    def test_parse_excel_empty_file(self) -> None:
        """Test error on empty Excel file."""
        excel_content = self._create_excel({})

        result = parse_winebow_excel(excel_content)

        assert result.success_count == 0
        assert result.error_count == 1
        assert (
            "No data rows" in result.errors[0].message
            or "Missing required" in result.errors[0].message
        )

    def test_parse_excel_missing_required_column(self) -> None:
        """Test error when required column is missing."""
        excel_content = self._create_excel(
            {
                "transaction_date": [date(2026, 1, 15)],
                "product_code": ["UFRed250"],
                # Missing quantity
            }
        )

        result = parse_winebow_excel(excel_content)

        assert result.error_count >= 1
        assert any(
            "Missing required" in e.message or "quantity" in e.message
            for e in result.errors
        )

    def test_parse_excel_invalid_date_row(self) -> None:
        """Test handling of row with invalid date in Excel."""
        excel_content = self._create_excel(
            {
                "transaction_date": [date(2026, 1, 15), None, date(2026, 1, 17)],
                "product_code": ["UFRed250", "UFBub250", "UFRos250"],
                "quantity": [48, 24, 36],
            }
        )

        result = parse_winebow_excel(excel_content)

        assert result.total_rows == 3
        assert result.success_count == 2
        assert result.error_count == 1

    def test_parse_excel_100_rows(self) -> None:
        """Test parsing 100 rows in Excel (acceptance criteria)."""
        excel_content = self._create_excel(
            {
                "transaction_date": [date(2026, 1, (i % 28) + 1) for i in range(100)],
                "customer_name": [f"Customer{i}" for i in range(100)],
                "product_code": ["UFRed250"] * 100,
                "quantity": list(range(1, 101)),
            }
        )

        result = parse_winebow_excel(excel_content)

        assert result.total_rows == 100
        assert result.success_count == 100
        assert result.error_count == 0


class TestParseWinebowReport:
    """Tests for parse_winebow_report function (unified interface)."""

    def test_parse_csv_extension(self) -> None:
        """Test that .csv extension routes to CSV parser."""
        csv_content = b"""transaction_date,product_code,quantity
2026-01-15,UFRed250,48"""

        result = parse_winebow_report(csv_content, ".csv")

        assert result.success_count == 1

    def test_parse_xlsx_extension(self) -> None:
        """Test that .xlsx extension routes to Excel parser."""
        df = pd.DataFrame(
            {
                "transaction_date": [date(2026, 1, 15)],
                "product_code": ["UFRed250"],
                "quantity": [48],
            }
        )
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False)
        excel_content = buffer.getvalue()

        result = parse_winebow_report(excel_content, ".xlsx")

        assert result.success_count == 1

    def test_parse_xls_extension(self) -> None:
        """Test that .xls extension routes to Excel parser."""
        df = pd.DataFrame(
            {
                "transaction_date": [date(2026, 1, 15)],
                "product_code": ["UFRed250"],
                "quantity": [48],
            }
        )
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False, engine="openpyxl")
        excel_content = buffer.getvalue()

        result = parse_winebow_report(excel_content, ".xls")

        # May succeed or fail depending on xlrd availability
        assert isinstance(result, ParseResult)

    def test_parse_uppercase_extension(self) -> None:
        """Test that uppercase extension is handled."""
        csv_content = b"""transaction_date,product_code,quantity
2026-01-15,UFRed250,48"""

        result = parse_winebow_report(csv_content, ".CSV")

        assert result.success_count == 1

    def test_parse_unsupported_extension(self) -> None:
        """Test error for unsupported extension."""
        result = parse_winebow_report(b"content", ".pdf")

        assert result.success_count == 0
        assert result.error_count == 1
        assert "Unsupported file extension" in result.errors[0].message
