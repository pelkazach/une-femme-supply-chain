"""Tests for file upload API endpoints."""

from collections.abc import AsyncGenerator
from io import BytesIO
from unittest.mock import AsyncMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.upload import (
    MAX_FILE_SIZE,
    SUPPORTED_EXTENSIONS,
    validate_content_type,
    validate_file_extension,
)
from src.database import get_db
from src.main import app


@pytest.fixture
def sync_client() -> TestClient:
    """Create a sync test client for simple tests."""
    return TestClient(app)


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock database session."""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def override_db(mock_db_session: AsyncMock) -> None:
    """Override the database dependency."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield mock_db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


class TestValidateFileExtension:
    """Tests for validate_file_extension function."""

    def test_validate_csv_extension(self) -> None:
        """Test validation of .csv extension."""
        result = validate_file_extension("report.csv")
        assert result == ".csv"

    def test_validate_xlsx_extension(self) -> None:
        """Test validation of .xlsx extension."""
        result = validate_file_extension("report.xlsx")
        assert result == ".xlsx"

    def test_validate_xls_extension(self) -> None:
        """Test validation of .xls extension."""
        result = validate_file_extension("report.xls")
        assert result == ".xls"

    def test_validate_uppercase_extension(self) -> None:
        """Test validation handles uppercase extensions."""
        result = validate_file_extension("report.CSV")
        assert result == ".csv"

    def test_validate_mixed_case_extension(self) -> None:
        """Test validation handles mixed case extensions."""
        result = validate_file_extension("report.XlSx")
        assert result == ".xlsx"

    def test_invalid_extension_raises_error(self) -> None:
        """Test that invalid extensions raise HTTPException."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            validate_file_extension("report.pdf")

        assert exc_info.value.status_code == 400
        assert "Unsupported file type" in str(exc_info.value.detail)

    def test_no_extension_raises_error(self) -> None:
        """Test that files without extension raise HTTPException."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            validate_file_extension("report")

        assert exc_info.value.status_code == 400
        assert "Unsupported file type" in str(exc_info.value.detail)

    def test_empty_filename_raises_error(self) -> None:
        """Test that empty filename raises HTTPException."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            validate_file_extension("")

        assert exc_info.value.status_code == 400
        assert "Filename is required" in str(exc_info.value.detail)


class TestValidateContentType:
    """Tests for validate_content_type function."""

    def test_valid_csv_content_type(self) -> None:
        """Test validation of text/csv content type."""
        # Should not raise
        validate_content_type("text/csv", ".csv")

    def test_valid_application_csv_content_type(self) -> None:
        """Test validation of application/csv content type."""
        # Should not raise
        validate_content_type("application/csv", ".csv")

    def test_valid_xlsx_content_type(self) -> None:
        """Test validation of xlsx content type."""
        # Should not raise
        validate_content_type(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".xlsx",
        )

    def test_valid_xls_content_type(self) -> None:
        """Test validation of xls content type."""
        # Should not raise
        validate_content_type("application/vnd.ms-excel", ".xls")

    def test_octet_stream_allowed(self) -> None:
        """Test that application/octet-stream is allowed for any extension."""
        # Should not raise
        validate_content_type("application/octet-stream", ".csv")
        validate_content_type("application/octet-stream", ".xlsx")

    def test_none_content_type_allowed(self) -> None:
        """Test that None content type is allowed."""
        # Should not raise
        validate_content_type(None, ".csv")

    def test_mismatched_content_type_raises_error(self) -> None:
        """Test that mismatched content type raises HTTPException."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            validate_content_type("text/csv", ".xlsx")

        assert exc_info.value.status_code == 400
        assert "does not match" in str(exc_info.value.detail)


class TestUploadEndpoint:
    """Tests for POST /upload endpoint."""

    def test_upload_csv_success(self, override_db: None) -> None:
        """Test successful CSV file upload."""
        csv_content = b"Date,Invoice,Account,SKU,Qty Sold\n2026-01-15,INV001,ABC,UFBub250,24"

        client = TestClient(app)
        response = client.post(
            "/upload",
            files={"file": ("report.csv", BytesIO(csv_content), "text/csv")},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "message" in data
        assert "result" in data
        assert data["result"]["filename"] == "report.csv"

    def test_upload_xlsx_success(self, override_db: None) -> None:
        """Test successful Excel file upload."""
        # Minimal valid xlsx file content (just needs to pass size check)
        xlsx_content = b"PK\x03\x04" + b"\x00" * 100  # Minimal ZIP header

        client = TestClient(app)
        response = client.post(
            "/upload",
            files={
                "file": (
                    "report.xlsx",
                    BytesIO(xlsx_content),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["result"]["filename"] == "report.xlsx"

    def test_upload_with_distributor_param(self, override_db: None) -> None:
        """Test upload with distributor parameter."""
        csv_content = b"Date,SKU,Qty\n2026-01-15,UFBub250,24"

        client = TestClient(app)
        response = client.post(
            "/upload",
            files={"file": ("report.csv", BytesIO(csv_content), "text/csv")},
            data={"distributor": "RNDC"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["result"]["distributor"] == "RNDC"

    def test_upload_unsupported_file_type(self, override_db: None) -> None:
        """Test upload of unsupported file type."""
        pdf_content = b"%PDF-1.4 fake pdf content"

        client = TestClient(app)
        response = client.post(
            "/upload",
            files={"file": ("report.pdf", BytesIO(pdf_content), "application/pdf")},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Unsupported file type" in response.json()["detail"]

    def test_upload_empty_file(self, override_db: None) -> None:
        """Test upload of empty file."""
        client = TestClient(app)
        response = client.post(
            "/upload",
            files={"file": ("report.csv", BytesIO(b""), "text/csv")},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "empty" in response.json()["detail"].lower()

    def test_upload_file_too_large(self, override_db: None) -> None:
        """Test upload of file exceeding size limit."""
        # Create a file larger than MAX_FILE_SIZE
        large_content = b"x" * (MAX_FILE_SIZE + 1)

        client = TestClient(app)
        response = client.post(
            "/upload",
            files={"file": ("report.csv", BytesIO(large_content), "text/csv")},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "exceeds maximum" in response.json()["detail"].lower()

    def test_upload_no_file(self) -> None:
        """Test upload without file."""
        client = TestClient(app)
        response = client.post("/upload")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_upload_mismatched_content_type(self, override_db: None) -> None:
        """Test upload with mismatched content type."""
        csv_content = b"Date,SKU,Qty\n2026-01-15,UFBub250,24"

        client = TestClient(app)
        response = client.post(
            "/upload",
            files={
                "file": (
                    "report.csv",
                    BytesIO(csv_content),
                    "application/vnd.ms-excel",  # Excel content type for CSV file
                )
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "does not match" in response.json()["detail"]

    def test_upload_octet_stream_content_type_allowed(self, override_db: None) -> None:
        """Test that application/octet-stream content type is allowed."""
        csv_content = b"Date,SKU,Qty\n2026-01-15,UFBub250,24"

        client = TestClient(app)
        response = client.post(
            "/upload",
            files={
                "file": (
                    "report.csv",
                    BytesIO(csv_content),
                    "application/octet-stream",
                )
            },
        )

        assert response.status_code == status.HTTP_200_OK

    def test_upload_response_structure(self, override_db: None) -> None:
        """Test that upload response has correct structure."""
        csv_content = b"Date,SKU,Qty\n2026-01-15,UFBub250,24"

        client = TestClient(app)
        response = client.post(
            "/upload",
            files={"file": ("report.csv", BytesIO(csv_content), "text/csv")},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Check top-level structure
        assert "message" in data
        assert "result" in data

        # Check result structure
        result = data["result"]
        assert "filename" in result
        assert "distributor" in result
        assert "total_rows" in result
        assert "success_count" in result
        assert "error_count" in result
        assert "errors" in result

        # Check types
        assert isinstance(result["total_rows"], int)
        assert isinstance(result["success_count"], int)
        assert isinstance(result["error_count"], int)
        assert isinstance(result["errors"], list)


class TestSupportedExtensions:
    """Tests for supported file extensions constant."""

    def test_csv_supported(self) -> None:
        """Test that .csv is in supported extensions."""
        assert ".csv" in SUPPORTED_EXTENSIONS

    def test_xlsx_supported(self) -> None:
        """Test that .xlsx is in supported extensions."""
        assert ".xlsx" in SUPPORTED_EXTENSIONS

    def test_xls_supported(self) -> None:
        """Test that .xls is in supported extensions."""
        assert ".xls" in SUPPORTED_EXTENSIONS


class TestSkuValidation:
    """Tests for SKU validation in upload endpoint."""

    def test_upload_with_valid_skus(self, override_db: None) -> None:
        """Test upload where all SKUs are valid."""
        csv_content = b"Date,SKU,Qty Sold\n2026-01-15,UFBub250,24\n2026-01-16,UFRos250,12"

        client = TestClient(app)
        response = client.post(
            "/upload",
            files={"file": ("report.csv", BytesIO(csv_content), "text/csv")},
            data={"distributor": "RNDC"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        result = data["result"]
        assert result["success_count"] == 2
        assert result["error_count"] == 0

    def test_upload_with_invalid_skus_flagged(self, override_db: None) -> None:
        """Test upload where invalid SKUs are flagged with errors."""
        csv_content = b"Date,SKU,Qty Sold\n2026-01-15,UFBub250,24\n2026-01-16,INVALID_SKU,12\n2026-01-17,UFRos250,36"

        client = TestClient(app)
        response = client.post(
            "/upload",
            files={"file": ("report.csv", BytesIO(csv_content), "text/csv")},
            data={"distributor": "RNDC"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        result = data["result"]
        # 2 valid SKUs, 1 invalid
        assert result["success_count"] == 2
        assert result["error_count"] == 1

        # Check error message
        errors = result["errors"]
        assert len(errors) == 1
        assert errors[0]["field"] == "sku"
        assert "Unknown SKU" in errors[0]["message"]
        assert "INVALID_SKU" in errors[0]["message"]

    def test_upload_with_sku_validation_disabled(self, override_db: None) -> None:
        """Test upload with SKU validation disabled."""
        csv_content = b"Date,SKU,Qty Sold\n2026-01-15,CUSTOM_SKU1,24\n2026-01-16,CUSTOM_SKU2,12"

        client = TestClient(app)
        response = client.post(
            "/upload",
            files={"file": ("report.csv", BytesIO(csv_content), "text/csv")},
            data={"distributor": "RNDC", "validate_skus": "false"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        result = data["result"]
        # All rows should be valid since validation is disabled
        assert result["success_count"] == 2
        assert result["error_count"] == 0

    def test_upload_all_invalid_skus(self, override_db: None) -> None:
        """Test upload where all SKUs are invalid."""
        csv_content = b"Date,SKU,Qty Sold\n2026-01-15,BAD1,24\n2026-01-16,BAD2,12"

        client = TestClient(app)
        response = client.post(
            "/upload",
            files={"file": ("report.csv", BytesIO(csv_content), "text/csv")},
            data={"distributor": "RNDC"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        result = data["result"]
        assert result["success_count"] == 0
        assert result["error_count"] == 2
        assert "errors" in data["message"].lower() or result["error_count"] > 0

    def test_upload_southern_glazers_with_sku_validation(self, override_db: None) -> None:
        """Test SKU validation for Southern Glazers distributor."""
        csv_content = b"Ship Date,Item Code,Bottles\n01/15/2026,UFRos250,120\n01/16/2026,BAD_SKU,60"

        client = TestClient(app)
        response = client.post(
            "/upload",
            files={"file": ("report.csv", BytesIO(csv_content), "text/csv")},
            data={"distributor": "Southern Glazers"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        result = data["result"]
        assert result["success_count"] == 1
        assert result["error_count"] == 1

    def test_upload_winebow_with_sku_validation(self, override_db: None) -> None:
        """Test SKU validation for Winebow distributor."""
        csv_content = b"transaction_date,product_code,quantity\n2026-01-15,UFRed250,48\n2026-01-16,UNKNOWN,24"

        client = TestClient(app)
        response = client.post(
            "/upload",
            files={"file": ("report.csv", BytesIO(csv_content), "text/csv")},
            data={"distributor": "Winebow"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        result = data["result"]
        assert result["success_count"] == 1
        assert result["error_count"] == 1

    def test_sku_validation_preserves_parsing_errors(self, override_db: None) -> None:
        """Test that parsing errors are preserved along with SKU validation errors."""
        # Row 2: valid SKU, Row 3: invalid date, Row 4: invalid SKU
        csv_content = b"Date,SKU,Qty Sold\n2026-01-15,UFBub250,24\nbad-date,UFRos250,12\n2026-01-17,INVALID,36"

        client = TestClient(app)
        response = client.post(
            "/upload",
            files={"file": ("report.csv", BytesIO(csv_content), "text/csv")},
            data={"distributor": "RNDC"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        result = data["result"]
        # 1 valid row (UFBub250), 2 errors (bad date + invalid SKU)
        assert result["success_count"] == 1
        assert result["error_count"] == 2

        # Check that we have both types of errors
        error_messages = [e["message"] for e in result["errors"]]
        assert any("date" in msg.lower() for msg in error_messages)
        assert any("Unknown SKU" in msg for msg in error_messages)

    def test_valid_skus_constant_used(self, override_db: None) -> None:
        """Test that all 4 Une Femme SKUs are accepted."""
        # Test all 4 valid SKUs
        csv_content = b"Date,SKU,Qty Sold\n2026-01-15,UFBub250,24\n2026-01-16,UFRos250,12\n2026-01-17,UFRed250,36\n2026-01-18,UFCha250,48"

        client = TestClient(app)
        response = client.post(
            "/upload",
            files={"file": ("report.csv", BytesIO(csv_content), "text/csv")},
            data={"distributor": "RNDC"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        result = data["result"]
        assert result["success_count"] == 4
        assert result["error_count"] == 0
