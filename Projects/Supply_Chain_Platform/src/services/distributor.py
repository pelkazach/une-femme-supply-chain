"""Distributor report parsers for processing CSV/Excel files.

This module contains parsers for different distributor report formats:
- RNDC: Date, Invoice, Account, SKU, Description, Qty Sold, Unit Price, Extended
- Southern Glazers: Ship Date, Customer, Item Code, Item Description, Cases, Bottles, Amount
- Winebow: transaction_date, customer_name, product_code, product_name, quantity, total
"""

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any

import pandas as pd


class Distributor(str, Enum):
    """Supported distributor types."""

    RNDC = "RNDC"
    SOUTHERN_GLAZERS = "Southern Glazers"
    WINEBOW = "Winebow"


@dataclass
class ParsedRow:
    """A successfully parsed row from a distributor report."""

    date: date
    sku: str
    quantity: int
    invoice: str | None = None
    account: str | None = None
    customer: str | None = None
    description: str | None = None
    unit_price: float | None = None
    extended_amount: float | None = None
    cases: int | None = None
    bottles: int | None = None


@dataclass
class RowError:
    """An error encountered while parsing a row."""

    row_number: int
    field: str | None
    message: str


@dataclass
class ParseResult:
    """Result of parsing a distributor report."""

    rows: list[ParsedRow]
    errors: list[RowError]
    total_rows: int

    @property
    def success_count(self) -> int:
        """Number of successfully parsed rows."""
        return len(self.rows)

    @property
    def error_count(self) -> int:
        """Number of rows with errors."""
        return len(self.errors)


# RNDC column mappings (case-insensitive)
RNDC_REQUIRED_COLUMNS = {
    "date": ["date", "ship_date", "shipdate", "trans_date"],
    "sku": ["sku", "item_code", "itemcode", "product_code"],
    "quantity": ["qty sold", "qty_sold", "qtysold", "quantity", "qty"],
}

RNDC_OPTIONAL_COLUMNS = {
    "invoice": ["invoice", "invoice_number", "invoicenumber", "inv"],
    "account": ["account", "customer", "account_name"],
    "description": ["description", "item_description", "product_name", "desc"],
    "unit_price": ["unit price", "unit_price", "unitprice", "price"],
    "extended": ["extended", "amount", "total", "ext_amount"],
}

# Southern Glazers column mappings (case-insensitive)
SOUTHERN_GLAZERS_REQUIRED_COLUMNS = {
    "date": ["ship date", "ship_date", "shipdate", "date"],
    "sku": ["item code", "item_code", "itemcode", "sku", "product_code"],
    "bottles": ["bottles", "units", "qty", "quantity"],
}

SOUTHERN_GLAZERS_OPTIONAL_COLUMNS = {
    "customer": ["customer", "account", "customer_name", "account_name"],
    "description": ["item description", "item_description", "description", "product_name"],
    "cases": ["cases", "case_qty", "case_count"],
    "amount": ["amount", "total", "extended", "ext_amount"],
}


def _find_column(
    headers: list[str], possible_names: list[str]
) -> tuple[int | None, str | None]:
    """Find a column index by checking possible names.

    Args:
        headers: List of header names from the file.
        possible_names: List of possible column names to match.

    Returns:
        Tuple of (index, matched_name) or (None, None) if not found.
    """
    headers_lower = [h.lower().strip() for h in headers]
    for name in possible_names:
        if name.lower() in headers_lower:
            idx = headers_lower.index(name.lower())
            return idx, headers[idx]
    return None, None


def _parse_date(value: str | datetime | date, row_num: int) -> date | RowError:
    """Parse a date value from various formats.

    Supports formats:
    - YYYY-MM-DD
    - MM/DD/YYYY
    - MM-DD-YYYY
    - datetime/date objects

    Args:
        value: The date value to parse.
        row_num: Row number for error reporting.

    Returns:
        Parsed date or RowError.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    if not isinstance(value, str) or not value.strip():
        return RowError(
            row_number=row_num,
            field="date",
            message="Date is required",
        )

    value = value.strip()

    # Try common date formats
    formats = [
        "%Y-%m-%d",  # 2026-01-15
        "%m/%d/%Y",  # 01/15/2026
        "%m-%d-%Y",  # 01-15-2026
        "%Y/%m/%d",  # 2026/01/15
        "%d/%m/%Y",  # 15/01/2026 (European)
        "%d-%m-%Y",  # 15-01-2026 (European)
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    return RowError(
        row_number=row_num,
        field="date",
        message=f"Invalid date format: {value!r}",
    )


def _parse_quantity(value: Any, row_num: int) -> int | RowError:
    """Parse a quantity value.

    Args:
        value: The quantity value to parse.
        row_num: Row number for error reporting.

    Returns:
        Parsed integer quantity or RowError.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return RowError(
            row_number=row_num,
            field="quantity",
            message="Quantity is required",
        )

    try:
        if isinstance(value, float):
            # Handle Excel numeric values
            return int(value)
        if isinstance(value, int):
            return value
        # Parse string, handling commas
        return int(str(value).strip().replace(",", ""))
    except (ValueError, TypeError):
        return RowError(
            row_number=row_num,
            field="quantity",
            message=f"Invalid quantity: {value!r}",
        )


def _parse_float(value: Any) -> float | None:
    """Parse an optional float value.

    Args:
        value: The value to parse.

    Returns:
        Parsed float or None if empty/invalid.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return None

    try:
        if isinstance(value, int | float):
            return float(value)
        # Parse string, handling currency symbols and commas
        clean_value = str(value).strip().replace(",", "").replace("$", "")
        return float(clean_value)
    except (ValueError, TypeError):
        return None


def _get_cell_value(row: dict[str, Any] | list[Any], idx: int | str) -> Any:
    """Get a cell value from a row (handles both dict and list rows).

    Args:
        row: The row data.
        idx: Column index (int) or key (str).

    Returns:
        The cell value or None.
    """
    try:
        if isinstance(row, dict):
            if isinstance(idx, str):
                return row.get(idx)
            # If idx is int, find by position
            keys = list(row.keys())
            if isinstance(idx, int) and 0 <= idx < len(keys):
                return row[keys[idx]]
            return None
        if isinstance(idx, int):
            return row[idx] if 0 <= idx < len(row) else None
        return None
    except (IndexError, KeyError, TypeError):
        return None


def parse_rndc_csv(content: bytes) -> ParseResult:
    """Parse an RNDC report from CSV content.

    RNDC format:
    Date,Invoice,Account,SKU,Description,Qty Sold,Unit Price,Extended

    Args:
        content: CSV file content as bytes.

    Returns:
        ParseResult with parsed rows and any errors.
    """
    rows: list[ParsedRow] = []
    errors: list[RowError] = []
    total_rows = 0

    try:
        # Decode content
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("latin-1")

        reader = csv.reader(io.StringIO(text))

        # Read header
        try:
            headers = next(reader)
        except StopIteration:
            errors.append(
                RowError(row_number=0, field=None, message="No data rows found")
            )
            return ParseResult(rows=rows, errors=errors, total_rows=0)

        # Find required columns
        date_idx, _ = _find_column(headers, RNDC_REQUIRED_COLUMNS["date"])
        sku_idx, _ = _find_column(headers, RNDC_REQUIRED_COLUMNS["sku"])
        qty_idx, _ = _find_column(headers, RNDC_REQUIRED_COLUMNS["quantity"])

        # Find optional columns
        invoice_idx, _ = _find_column(headers, RNDC_OPTIONAL_COLUMNS["invoice"])
        account_idx, _ = _find_column(headers, RNDC_OPTIONAL_COLUMNS["account"])
        desc_idx, _ = _find_column(headers, RNDC_OPTIONAL_COLUMNS["description"])
        price_idx, _ = _find_column(headers, RNDC_OPTIONAL_COLUMNS["unit_price"])
        extended_idx, _ = _find_column(headers, RNDC_OPTIONAL_COLUMNS["extended"])

        # Check required columns
        missing_cols = []
        if date_idx is None:
            missing_cols.append("Date")
        if sku_idx is None:
            missing_cols.append("SKU")
        if qty_idx is None:
            missing_cols.append("Qty Sold")

        if missing_cols:
            errors.append(
                RowError(
                    row_number=0,
                    field=None,
                    message=f"Missing required columns: {', '.join(missing_cols)}",
                )
            )
            return ParseResult(rows=rows, errors=errors, total_rows=0)

        # Type narrowing for mypy - at this point we know these are not None
        assert date_idx is not None
        assert sku_idx is not None
        assert qty_idx is not None

        # Parse data rows
        for row_num, row in enumerate(reader, start=2):  # 1-indexed, header is row 1
            total_rows += 1

            # Skip empty rows
            if not any(cell.strip() for cell in row):
                continue

            # Parse required fields
            date_result = _parse_date(row[date_idx], row_num)
            if isinstance(date_result, RowError):
                errors.append(date_result)
                continue

            sku_value = row[sku_idx].strip() if row[sku_idx] else ""
            if not sku_value:
                errors.append(
                    RowError(
                        row_number=row_num,
                        field="sku",
                        message="SKU is required",
                    )
                )
                continue

            qty_result = _parse_quantity(row[qty_idx], row_num)
            if isinstance(qty_result, RowError):
                errors.append(qty_result)
                continue

            # Parse optional fields
            invoice = row[invoice_idx].strip() if invoice_idx is not None else None
            account = row[account_idx].strip() if account_idx is not None else None
            description = row[desc_idx].strip() if desc_idx is not None else None
            unit_price = (
                _parse_float(row[price_idx]) if price_idx is not None else None
            )
            extended = (
                _parse_float(row[extended_idx]) if extended_idx is not None else None
            )

            rows.append(
                ParsedRow(
                    date=date_result,
                    sku=sku_value,
                    quantity=qty_result,
                    invoice=invoice,
                    account=account,
                    description=description,
                    unit_price=unit_price,
                    extended_amount=extended,
                )
            )

    except Exception as e:
        errors.append(
            RowError(
                row_number=0,
                field=None,
                message=f"Error parsing CSV: {e}",
            )
        )

    return ParseResult(rows=rows, errors=errors, total_rows=total_rows)


def parse_rndc_excel(content: bytes) -> ParseResult:
    """Parse an RNDC report from Excel content.

    RNDC format:
    Date,Invoice,Account,SKU,Description,Qty Sold,Unit Price,Extended

    Args:
        content: Excel file content as bytes.

    Returns:
        ParseResult with parsed rows and any errors.
    """
    rows: list[ParsedRow] = []
    errors: list[RowError] = []
    total_rows = 0

    try:
        # Read Excel file
        df = pd.read_excel(io.BytesIO(content), sheet_name=0)

        if df.empty:
            errors.append(
                RowError(row_number=0, field=None, message="No data rows found")
            )
            return ParseResult(rows=rows, errors=errors, total_rows=0)

        # Get headers
        headers = [str(col) for col in df.columns]

        # Find required columns
        date_col, date_name = _find_column(headers, RNDC_REQUIRED_COLUMNS["date"])
        sku_col, sku_name = _find_column(headers, RNDC_REQUIRED_COLUMNS["sku"])
        qty_col, qty_name = _find_column(headers, RNDC_REQUIRED_COLUMNS["quantity"])

        # Find optional columns
        invoice_col, invoice_name = _find_column(
            headers, RNDC_OPTIONAL_COLUMNS["invoice"]
        )
        account_col, account_name = _find_column(
            headers, RNDC_OPTIONAL_COLUMNS["account"]
        )
        desc_col, desc_name = _find_column(
            headers, RNDC_OPTIONAL_COLUMNS["description"]
        )
        price_col, price_name = _find_column(
            headers, RNDC_OPTIONAL_COLUMNS["unit_price"]
        )
        extended_col, extended_name = _find_column(
            headers, RNDC_OPTIONAL_COLUMNS["extended"]
        )

        # Check required columns
        missing_cols = []
        if date_col is None:
            missing_cols.append("Date")
        if sku_col is None:
            missing_cols.append("SKU")
        if qty_col is None:
            missing_cols.append("Qty Sold")

        if missing_cols:
            errors.append(
                RowError(
                    row_number=0,
                    field=None,
                    message=f"Missing required columns: {', '.join(missing_cols)}",
                )
            )
            return ParseResult(rows=rows, errors=errors, total_rows=0)

        # Type narrowing for mypy - at this point we know these are not None
        assert date_col is not None
        assert sku_col is not None
        assert qty_col is not None

        # Get actual column names for accessing data
        date_key = headers[date_col]
        sku_key = headers[sku_col]
        qty_key = headers[qty_col]
        invoice_key = headers[invoice_col] if invoice_col is not None else None
        account_key = headers[account_col] if account_col is not None else None
        desc_key = headers[desc_col] if desc_col is not None else None
        price_key = headers[price_col] if price_col is not None else None
        extended_key = headers[extended_col] if extended_col is not None else None

        # Parse data rows
        for idx, row in df.iterrows():
            row_num = idx + 2  # 1-indexed, header is row 1
            total_rows += 1

            # Parse required fields
            date_value = row[date_key]
            # Handle pandas NaT
            if pd.isna(date_value):
                errors.append(
                    RowError(
                        row_number=row_num,
                        field="date",
                        message="Date is required",
                    )
                )
                continue

            date_result = _parse_date(date_value, row_num)
            if isinstance(date_result, RowError):
                errors.append(date_result)
                continue

            sku_value = row[sku_key]
            if pd.isna(sku_value) or not str(sku_value).strip():
                errors.append(
                    RowError(
                        row_number=row_num,
                        field="sku",
                        message="SKU is required",
                    )
                )
                continue
            sku_value = str(sku_value).strip()

            qty_value = row[qty_key]
            if pd.isna(qty_value):
                errors.append(
                    RowError(
                        row_number=row_num,
                        field="quantity",
                        message="Quantity is required",
                    )
                )
                continue

            qty_result = _parse_quantity(qty_value, row_num)
            if isinstance(qty_result, RowError):
                errors.append(qty_result)
                continue

            # Parse optional fields
            invoice = (
                str(row[invoice_key]).strip()
                if invoice_key and not pd.isna(row.get(invoice_key))
                else None
            )
            account = (
                str(row[account_key]).strip()
                if account_key and not pd.isna(row.get(account_key))
                else None
            )
            description = (
                str(row[desc_key]).strip()
                if desc_key and not pd.isna(row.get(desc_key))
                else None
            )
            unit_price = (
                _parse_float(row[price_key])
                if price_key and not pd.isna(row.get(price_key))
                else None
            )
            extended = (
                _parse_float(row[extended_key])
                if extended_key and not pd.isna(row.get(extended_key))
                else None
            )

            rows.append(
                ParsedRow(
                    date=date_result,
                    sku=sku_value,
                    quantity=qty_result,
                    invoice=invoice,
                    account=account,
                    description=description,
                    unit_price=unit_price,
                    extended_amount=extended,
                )
            )

    except Exception as e:
        errors.append(
            RowError(
                row_number=0,
                field=None,
                message=f"Error parsing Excel file: {e}",
            )
        )

    return ParseResult(rows=rows, errors=errors, total_rows=total_rows)


def parse_rndc_report(content: bytes, extension: str) -> ParseResult:
    """Parse an RNDC report from either CSV or Excel format.

    Args:
        content: File content as bytes.
        extension: File extension ('.csv', '.xlsx', or '.xls').

    Returns:
        ParseResult with parsed rows and any errors.
    """
    extension = extension.lower()
    if extension == ".csv":
        return parse_rndc_csv(content)
    elif extension in (".xlsx", ".xls"):
        return parse_rndc_excel(content)
    else:
        return ParseResult(
            rows=[],
            errors=[
                RowError(
                    row_number=0,
                    field=None,
                    message=f"Unsupported file extension: {extension}",
                )
            ],
            total_rows=0,
        )


def parse_southern_glazers_csv(content: bytes) -> ParseResult:
    """Parse a Southern Glazers report from CSV content.

    Southern Glazers format:
    Ship Date,Customer,Item Code,Item Description,Cases,Bottles,Amount

    Args:
        content: CSV file content as bytes.

    Returns:
        ParseResult with parsed rows and any errors.
    """
    rows: list[ParsedRow] = []
    errors: list[RowError] = []
    total_rows = 0

    try:
        # Decode content
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("latin-1")

        reader = csv.reader(io.StringIO(text))

        # Read header
        try:
            headers = next(reader)
        except StopIteration:
            errors.append(
                RowError(row_number=0, field=None, message="No data rows found")
            )
            return ParseResult(rows=rows, errors=errors, total_rows=0)

        # Find required columns
        date_idx, _ = _find_column(headers, SOUTHERN_GLAZERS_REQUIRED_COLUMNS["date"])
        sku_idx, _ = _find_column(headers, SOUTHERN_GLAZERS_REQUIRED_COLUMNS["sku"])
        bottles_idx, _ = _find_column(
            headers, SOUTHERN_GLAZERS_REQUIRED_COLUMNS["bottles"]
        )

        # Find optional columns
        customer_idx, _ = _find_column(
            headers, SOUTHERN_GLAZERS_OPTIONAL_COLUMNS["customer"]
        )
        desc_idx, _ = _find_column(
            headers, SOUTHERN_GLAZERS_OPTIONAL_COLUMNS["description"]
        )
        cases_idx, _ = _find_column(headers, SOUTHERN_GLAZERS_OPTIONAL_COLUMNS["cases"])
        amount_idx, _ = _find_column(
            headers, SOUTHERN_GLAZERS_OPTIONAL_COLUMNS["amount"]
        )

        # Check required columns
        missing_cols = []
        if date_idx is None:
            missing_cols.append("Ship Date")
        if sku_idx is None:
            missing_cols.append("Item Code")
        if bottles_idx is None:
            missing_cols.append("Bottles")

        if missing_cols:
            errors.append(
                RowError(
                    row_number=0,
                    field=None,
                    message=f"Missing required columns: {', '.join(missing_cols)}",
                )
            )
            return ParseResult(rows=rows, errors=errors, total_rows=0)

        # Type narrowing for mypy - at this point we know these are not None
        assert date_idx is not None
        assert sku_idx is not None
        assert bottles_idx is not None

        # Parse data rows
        for row_num, row in enumerate(reader, start=2):  # 1-indexed, header is row 1
            total_rows += 1

            # Skip empty rows
            if not any(cell.strip() for cell in row):
                continue

            # Parse required fields
            date_result = _parse_date(row[date_idx], row_num)
            if isinstance(date_result, RowError):
                errors.append(date_result)
                continue

            sku_value = row[sku_idx].strip() if row[sku_idx] else ""
            if not sku_value:
                errors.append(
                    RowError(
                        row_number=row_num,
                        field="sku",
                        message="Item Code is required",
                    )
                )
                continue

            bottles_result = _parse_quantity(row[bottles_idx], row_num)
            if isinstance(bottles_result, RowError):
                # Override field name for clarity
                errors.append(
                    RowError(
                        row_number=row_num,
                        field="bottles",
                        message=bottles_result.message.replace(
                            "quantity", "Bottles"
                        ).replace("Quantity", "Bottles"),
                    )
                )
                continue

            # Parse optional fields
            customer = (
                row[customer_idx].strip()
                if customer_idx is not None and len(row) > customer_idx
                else None
            )
            description = (
                row[desc_idx].strip()
                if desc_idx is not None and len(row) > desc_idx
                else None
            )
            cases = (
                _parse_quantity(row[cases_idx], row_num)
                if cases_idx is not None and len(row) > cases_idx
                else None
            )
            # If cases parsing failed, just set to None (optional field)
            if isinstance(cases, RowError):
                cases = None
            amount = (
                _parse_float(row[amount_idx])
                if amount_idx is not None and len(row) > amount_idx
                else None
            )

            rows.append(
                ParsedRow(
                    date=date_result,
                    sku=sku_value,
                    quantity=bottles_result,
                    customer=customer,
                    description=description,
                    cases=cases,
                    bottles=bottles_result,
                    extended_amount=amount,
                )
            )

    except Exception as e:
        errors.append(
            RowError(
                row_number=0,
                field=None,
                message=f"Error parsing CSV: {e}",
            )
        )

    return ParseResult(rows=rows, errors=errors, total_rows=total_rows)


def parse_southern_glazers_excel(content: bytes) -> ParseResult:
    """Parse a Southern Glazers report from Excel content.

    Southern Glazers format:
    Ship Date,Customer,Item Code,Item Description,Cases,Bottles,Amount

    Args:
        content: Excel file content as bytes.

    Returns:
        ParseResult with parsed rows and any errors.
    """
    rows: list[ParsedRow] = []
    errors: list[RowError] = []
    total_rows = 0

    try:
        # Read Excel file
        df = pd.read_excel(io.BytesIO(content), sheet_name=0)

        if df.empty:
            errors.append(
                RowError(row_number=0, field=None, message="No data rows found")
            )
            return ParseResult(rows=rows, errors=errors, total_rows=0)

        # Get headers
        headers = [str(col) for col in df.columns]

        # Find required columns
        date_col, date_name = _find_column(
            headers, SOUTHERN_GLAZERS_REQUIRED_COLUMNS["date"]
        )
        sku_col, sku_name = _find_column(
            headers, SOUTHERN_GLAZERS_REQUIRED_COLUMNS["sku"]
        )
        bottles_col, bottles_name = _find_column(
            headers, SOUTHERN_GLAZERS_REQUIRED_COLUMNS["bottles"]
        )

        # Find optional columns
        customer_col, customer_name = _find_column(
            headers, SOUTHERN_GLAZERS_OPTIONAL_COLUMNS["customer"]
        )
        desc_col, desc_name = _find_column(
            headers, SOUTHERN_GLAZERS_OPTIONAL_COLUMNS["description"]
        )
        cases_col, cases_name = _find_column(
            headers, SOUTHERN_GLAZERS_OPTIONAL_COLUMNS["cases"]
        )
        amount_col, amount_name = _find_column(
            headers, SOUTHERN_GLAZERS_OPTIONAL_COLUMNS["amount"]
        )

        # Check required columns
        missing_cols = []
        if date_col is None:
            missing_cols.append("Ship Date")
        if sku_col is None:
            missing_cols.append("Item Code")
        if bottles_col is None:
            missing_cols.append("Bottles")

        if missing_cols:
            errors.append(
                RowError(
                    row_number=0,
                    field=None,
                    message=f"Missing required columns: {', '.join(missing_cols)}",
                )
            )
            return ParseResult(rows=rows, errors=errors, total_rows=0)

        # Type narrowing for mypy - at this point we know these are not None
        assert date_col is not None
        assert sku_col is not None
        assert bottles_col is not None

        # Get actual column names for accessing data
        date_key = headers[date_col]
        sku_key = headers[sku_col]
        bottles_key = headers[bottles_col]
        customer_key = headers[customer_col] if customer_col is not None else None
        desc_key = headers[desc_col] if desc_col is not None else None
        cases_key = headers[cases_col] if cases_col is not None else None
        amount_key = headers[amount_col] if amount_col is not None else None

        # Parse data rows
        for idx, row in df.iterrows():
            row_num = idx + 2  # 1-indexed, header is row 1
            total_rows += 1

            # Parse required fields
            date_value = row[date_key]
            # Handle pandas NaT
            if pd.isna(date_value):
                errors.append(
                    RowError(
                        row_number=row_num,
                        field="date",
                        message="Ship Date is required",
                    )
                )
                continue

            date_result = _parse_date(date_value, row_num)
            if isinstance(date_result, RowError):
                errors.append(date_result)
                continue

            sku_value = row[sku_key]
            if pd.isna(sku_value) or not str(sku_value).strip():
                errors.append(
                    RowError(
                        row_number=row_num,
                        field="sku",
                        message="Item Code is required",
                    )
                )
                continue
            sku_value = str(sku_value).strip()

            bottles_value = row[bottles_key]
            if pd.isna(bottles_value):
                errors.append(
                    RowError(
                        row_number=row_num,
                        field="bottles",
                        message="Bottles is required",
                    )
                )
                continue

            bottles_result = _parse_quantity(bottles_value, row_num)
            if isinstance(bottles_result, RowError):
                errors.append(
                    RowError(
                        row_number=row_num,
                        field="bottles",
                        message=bottles_result.message.replace(
                            "quantity", "Bottles"
                        ).replace("Quantity", "Bottles"),
                    )
                )
                continue

            # Parse optional fields
            customer = (
                str(row[customer_key]).strip()
                if customer_key and not pd.isna(row.get(customer_key))
                else None
            )
            description = (
                str(row[desc_key]).strip()
                if desc_key and not pd.isna(row.get(desc_key))
                else None
            )

            cases = None
            if cases_key and not pd.isna(row.get(cases_key)):
                cases_result = _parse_quantity(row[cases_key], row_num)
                if not isinstance(cases_result, RowError):
                    cases = cases_result

            amount = (
                _parse_float(row[amount_key])
                if amount_key and not pd.isna(row.get(amount_key))
                else None
            )

            rows.append(
                ParsedRow(
                    date=date_result,
                    sku=sku_value,
                    quantity=bottles_result,
                    customer=customer,
                    description=description,
                    cases=cases,
                    bottles=bottles_result,
                    extended_amount=amount,
                )
            )

    except Exception as e:
        errors.append(
            RowError(
                row_number=0,
                field=None,
                message=f"Error parsing Excel file: {e}",
            )
        )

    return ParseResult(rows=rows, errors=errors, total_rows=total_rows)


def parse_southern_glazers_report(content: bytes, extension: str) -> ParseResult:
    """Parse a Southern Glazers report from either CSV or Excel format.

    Args:
        content: File content as bytes.
        extension: File extension ('.csv', '.xlsx', or '.xls').

    Returns:
        ParseResult with parsed rows and any errors.
    """
    extension = extension.lower()
    if extension == ".csv":
        return parse_southern_glazers_csv(content)
    elif extension in (".xlsx", ".xls"):
        return parse_southern_glazers_excel(content)
    else:
        return ParseResult(
            rows=[],
            errors=[
                RowError(
                    row_number=0,
                    field=None,
                    message=f"Unsupported file extension: {extension}",
                )
            ],
            total_rows=0,
        )
