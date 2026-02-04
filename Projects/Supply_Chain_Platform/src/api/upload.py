"""FastAPI routes for file upload and distributor report processing."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.services.distributor import parse_rndc_report, parse_southern_glazers_report

# Maximum file size: 10MB
MAX_FILE_SIZE = 10 * 1024 * 1024

# Supported file extensions
SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}

# Supported content types
SUPPORTED_CONTENT_TYPES = {
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

router = APIRouter(prefix="/upload", tags=["upload"])


class ValidationError(BaseModel):
    """Schema for a single validation error."""

    row: int = Field(description="Row number where the error occurred (1-indexed)")
    field: str | None = Field(
        default=None, description="Field name that caused the error"
    )
    message: str = Field(description="Error message describing the issue")


class ProcessingResult(BaseModel):
    """Schema for file processing results."""

    filename: str = Field(description="Name of the uploaded file")
    distributor: str | None = Field(
        default=None, description="Detected or specified distributor"
    )
    total_rows: int = Field(description="Total number of data rows in the file")
    success_count: int = Field(
        description="Number of rows successfully processed"
    )
    error_count: int = Field(description="Number of rows with errors")
    errors: list[ValidationError] = Field(
        default_factory=list,
        description="List of validation errors for failed rows",
    )


class UploadResponse(BaseModel):
    """Response schema for file upload endpoint."""

    message: str = Field(description="Status message")
    result: ProcessingResult = Field(description="Processing results")


def validate_file_extension(filename: str) -> str:
    """Validate and return the file extension.

    Args:
        filename: The uploaded filename.

    Returns:
        The lowercase file extension including the dot.

    Raises:
        HTTPException: If the file extension is not supported.
    """
    if not filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required",
        )

    # Get the extension
    ext = ""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Supported types: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    return ext


def validate_content_type(content_type: str | None, extension: str) -> None:
    """Validate the content type matches the file extension.

    Args:
        content_type: The content type from the upload.
        extension: The file extension.

    Raises:
        HTTPException: If content type doesn't match the extension.
    """
    # Allow application/octet-stream as some clients send this for any file
    if content_type and content_type != "application/octet-stream":
        # Check if content type is valid for the extension
        if extension == ".csv":
            valid_types = {"text/csv", "application/csv", "text/plain"}
        else:  # .xlsx, .xls
            valid_types = {
                "application/vnd.ms-excel",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }

        if content_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Content type '{content_type}' does not match file extension '{extension}'",
            )


async def validate_file_size(file: UploadFile) -> bytes:
    """Read and validate the file size.

    Args:
        file: The uploaded file.

    Returns:
        The file contents as bytes.

    Raises:
        HTTPException: If the file exceeds the size limit or is empty.
    """
    contents = await file.read()

    if len(contents) == 0:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty",
        )

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE // (1024 * 1024)}MB",
        )

    return contents


@router.post("", response_model=UploadResponse)
async def upload_distributor_file(
    file: Annotated[UploadFile, File(description="CSV or Excel file to upload")],
    db: Annotated[AsyncSession, Depends(get_db)],
    distributor: Annotated[
        str | None,
        Form(description="Distributor name (RNDC, Southern Glazers, Winebow)"),
    ] = None,
) -> UploadResponse:
    """Upload a distributor report file for processing.

    Accepts CSV and Excel (.xlsx, .xls) files containing distributor
    depletion reports. The file will be validated and queued for processing.

    Supported distributors:
    - RNDC
    - Southern Glazers
    - Winebow

    If distributor is not specified, the system will attempt to auto-detect
    the format based on column headers.

    Args:
        file: The uploaded file (CSV or Excel format).
        distributor: Optional distributor name to specify the report format.

    Returns:
        UploadResponse: Processing summary with success/error counts.

    Raises:
        HTTPException: 400 if file validation fails (wrong type, too large, empty).
    """
    # Validate file extension
    filename = file.filename or ""
    extension = validate_file_extension(filename)

    # Validate content type
    validate_content_type(file.content_type, extension)

    # Read and validate file size
    contents = await validate_file_size(file)

    # Parse the file based on distributor type
    distributor_upper = distributor.upper() if distributor else None

    if distributor_upper == "RNDC":
        parse_result = parse_rndc_report(contents, extension)
        result = ProcessingResult(
            filename=filename,
            distributor="RNDC",
            total_rows=parse_result.total_rows,
            success_count=parse_result.success_count,
            error_count=parse_result.error_count,
            errors=[
                ValidationError(
                    row=err.row_number,
                    field=err.field,
                    message=err.message,
                )
                for err in parse_result.errors
            ],
        )
        message = (
            f"File parsed successfully. {parse_result.success_count} rows processed."
            if parse_result.success_count > 0
            else "File parsing completed with errors."
        )
    elif distributor_upper in ("SOUTHERN GLAZERS", "SOUTHERN_GLAZERS", "SOUTHERNGLAZERS"):
        parse_result = parse_southern_glazers_report(contents, extension)
        result = ProcessingResult(
            filename=filename,
            distributor="Southern Glazers",
            total_rows=parse_result.total_rows,
            success_count=parse_result.success_count,
            error_count=parse_result.error_count,
            errors=[
                ValidationError(
                    row=err.row_number,
                    field=err.field,
                    message=err.message,
                )
                for err in parse_result.errors
            ],
        )
        message = (
            f"File parsed successfully. {parse_result.success_count} rows processed."
            if parse_result.success_count > 0
            else "File parsing completed with errors."
        )
    else:
        # For other distributors, return placeholder
        # Parser for Winebow will be implemented in task 1.4.4
        result = ProcessingResult(
            filename=filename,
            distributor=distributor,
            total_rows=0,
            success_count=0,
            error_count=0,
            errors=[
                ValidationError(
                    row=0,
                    field=None,
                    message=f"Parser for distributor '{distributor or 'auto-detect'}' not yet implemented.",
                )
            ],
        )
        message = "File received. Parser not yet implemented for this distributor."

    return UploadResponse(
        message=message,
        result=result,
    )
