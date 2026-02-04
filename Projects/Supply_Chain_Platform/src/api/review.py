"""FastAPI routes for human review queue of email classifications."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.email_classification import EmailClassification

router = APIRouter(prefix="/review", tags=["review"])


# --- Pydantic Schemas ---


class EmailClassificationResponse(BaseModel):
    """Response schema for an email classification."""

    id: UUID = Field(description="Classification UUID")
    message_id: str = Field(description="Gmail message ID")
    thread_id: str = Field(description="Gmail thread ID")
    subject: str = Field(description="Email subject")
    sender: str = Field(description="Sender email address")
    recipient: str = Field(description="Recipient email address")
    received_at: datetime = Field(description="When email was received")
    category: str = Field(description="Classified category (PO, BOL, INVOICE, GENERAL)")
    confidence: float = Field(description="Classification confidence (0.0-1.0)")
    reasoning: str = Field(description="LLM reasoning for classification")
    needs_review: bool = Field(description="Whether human review is needed")
    reviewed: bool = Field(description="Whether a human has reviewed this")
    reviewed_by: str | None = Field(description="Who reviewed (if applicable)")
    reviewed_at: datetime | None = Field(description="When reviewed (if applicable)")
    corrected_category: str | None = Field(
        description="Corrected category if changed during review"
    )
    has_attachments: bool = Field(description="Whether email has attachments")
    attachment_names: str = Field(description="JSON list of attachment filenames")
    processing_time_ms: int | None = Field(description="Time to classify in ms")
    ollama_used: bool = Field(description="Whether Ollama was used (vs rule-based)")
    created_at: datetime = Field(description="When record was created")
    updated_at: datetime = Field(description="When record was last updated")

    model_config = {"from_attributes": True}


class ReviewQueueResponse(BaseModel):
    """Response schema for the review queue listing."""

    items: list[EmailClassificationResponse] = Field(
        description="List of classifications needing review"
    )
    total: int = Field(description="Total number of items needing review")
    page: int = Field(description="Current page number")
    page_size: int = Field(description="Items per page")
    total_pages: int = Field(description="Total number of pages")


class ReviewQueueStats(BaseModel):
    """Statistics about the review queue."""

    pending_review: int = Field(description="Items needing review")
    reviewed_today: int = Field(description="Items reviewed today")
    total_reviewed: int = Field(description="Total items ever reviewed")
    avg_confidence: float | None = Field(
        description="Average confidence of pending items"
    )
    by_category: dict[str, int] = Field(
        description="Pending review count by category"
    )


class ReviewRequest(BaseModel):
    """Request schema for reviewing a classification."""

    reviewer: str = Field(description="Who is reviewing (email or username)")
    approved: bool = Field(
        default=True,
        description="Whether the classification is approved as-is",
    )
    corrected_category: str | None = Field(
        default=None,
        description="Corrected category if not approved (PO, BOL, INVOICE, GENERAL)",
    )


class ReviewResponse(BaseModel):
    """Response schema for a review action."""

    id: UUID = Field(description="Classification UUID")
    message_id: str = Field(description="Gmail message ID")
    original_category: str = Field(description="Original classification")
    corrected_category: str | None = Field(description="Corrected category if changed")
    reviewed_by: str = Field(description="Who reviewed")
    reviewed_at: datetime = Field(description="When reviewed")
    approved: bool = Field(description="Whether original classification was approved")


# --- API Endpoints ---


@router.get("/queue", response_model=ReviewQueueResponse)
async def get_review_queue(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=100, description="Items per page")
    ] = 20,
    category: Annotated[
        str | None,
        Query(description="Filter by category (PO, BOL, INVOICE, GENERAL)"),
    ] = None,
    min_confidence: Annotated[
        float | None,
        Query(ge=0.0, le=1.0, description="Minimum confidence filter"),
    ] = None,
    max_confidence: Annotated[
        float | None,
        Query(ge=0.0, le=1.0, description="Maximum confidence filter"),
    ] = None,
) -> ReviewQueueResponse:
    """Get the human review queue of low-confidence email classifications.

    Returns paginated list of email classifications that need human review
    (confidence < 85% or flagged for other reasons).

    Items are ordered by received_at descending (newest first).
    """
    # Build the base query for pending review items
    query = select(EmailClassification).where(
        EmailClassification.needs_review == True,  # noqa: E712
        EmailClassification.reviewed == False,  # noqa: E712
    )

    # Apply filters
    if category:
        query = query.where(EmailClassification.category == category.upper())
    if min_confidence is not None:
        query = query.where(EmailClassification.confidence >= min_confidence)
    if max_confidence is not None:
        query = query.where(EmailClassification.confidence <= max_confidence)

    # Count total items
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Calculate pagination
    total_pages = max(1, (total + page_size - 1) // page_size)
    offset = (page - 1) * page_size

    # Fetch items with pagination
    items_query = (
        query.order_by(EmailClassification.received_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(items_query)
    items = result.scalars().all()

    return ReviewQueueResponse(
        items=[EmailClassificationResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/queue/stats", response_model=ReviewQueueStats)
async def get_review_queue_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReviewQueueStats:
    """Get statistics about the review queue.

    Returns counts of pending, reviewed, and total items,
    plus breakdown by category.
    """
    # Count pending review items
    pending_query = select(func.count()).where(
        EmailClassification.needs_review == True,  # noqa: E712
        EmailClassification.reviewed == False,  # noqa: E712
    )
    pending_result = await db.execute(pending_query)
    pending_review = pending_result.scalar() or 0

    # Count items reviewed today
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    reviewed_today_query = select(func.count()).where(
        EmailClassification.reviewed == True,  # noqa: E712
        EmailClassification.reviewed_at >= today_start,
    )
    reviewed_today_result = await db.execute(reviewed_today_query)
    reviewed_today = reviewed_today_result.scalar() or 0

    # Count total reviewed
    total_reviewed_query = select(func.count()).where(
        EmailClassification.reviewed == True,  # noqa: E712
    )
    total_reviewed_result = await db.execute(total_reviewed_query)
    total_reviewed = total_reviewed_result.scalar() or 0

    # Average confidence of pending items
    avg_confidence_query = select(func.avg(EmailClassification.confidence)).where(
        EmailClassification.needs_review == True,  # noqa: E712
        EmailClassification.reviewed == False,  # noqa: E712
    )
    avg_confidence_result = await db.execute(avg_confidence_query)
    avg_confidence = avg_confidence_result.scalar()

    # Count by category for pending items
    by_category_query = (
        select(
            EmailClassification.category,
            func.count().label("count"),
        )
        .where(
            EmailClassification.needs_review == True,  # noqa: E712
            EmailClassification.reviewed == False,  # noqa: E712
        )
        .group_by(EmailClassification.category)
    )
    by_category_result = await db.execute(by_category_query)
    by_category = {row[0]: row[1] for row in by_category_result}

    return ReviewQueueStats(
        pending_review=pending_review,
        reviewed_today=reviewed_today,
        total_reviewed=total_reviewed,
        avg_confidence=float(avg_confidence) if avg_confidence else None,
        by_category=by_category,
    )


@router.get("/queue/{classification_id}", response_model=EmailClassificationResponse)
async def get_classification(
    classification_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EmailClassificationResponse:
    """Get a specific email classification by ID.

    Returns the full classification record.
    """
    result = await db.execute(
        select(EmailClassification).where(EmailClassification.id == classification_id)
    )
    classification = result.scalar_one_or_none()

    if not classification:
        raise HTTPException(
            status_code=404,
            detail=f"Classification with ID '{classification_id}' not found",
        )

    return EmailClassificationResponse.model_validate(classification)


@router.post("/queue/{classification_id}/review", response_model=ReviewResponse)
async def review_classification(
    classification_id: UUID,
    review: ReviewRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReviewResponse:
    """Mark a classification as reviewed.

    Can optionally correct the category if the original classification was wrong.
    """
    # Validate corrected_category if provided
    valid_categories = {"PO", "BOL", "INVOICE", "GENERAL"}
    if review.corrected_category and review.corrected_category.upper() not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category '{review.corrected_category}'. "
            f"Must be one of: {', '.join(sorted(valid_categories))}",
        )

    # Find the classification
    result = await db.execute(
        select(EmailClassification).where(EmailClassification.id == classification_id)
    )
    classification = result.scalar_one_or_none()

    if not classification:
        raise HTTPException(
            status_code=404,
            detail=f"Classification with ID '{classification_id}' not found",
        )

    if classification.reviewed:
        raise HTTPException(
            status_code=400,
            detail=f"Classification '{classification_id}' has already been reviewed "
            f"by {classification.reviewed_by} at {classification.reviewed_at}",
        )

    # Update the classification
    reviewed_at = datetime.now(UTC)
    corrected = (
        review.corrected_category.upper()
        if review.corrected_category and not review.approved
        else None
    )

    await db.execute(
        update(EmailClassification)
        .where(EmailClassification.id == classification_id)
        .values(
            reviewed=True,
            reviewed_by=review.reviewer,
            reviewed_at=reviewed_at,
            corrected_category=corrected,
        )
    )
    await db.commit()

    return ReviewResponse(
        id=classification.id,
        message_id=classification.message_id,
        original_category=classification.category,
        corrected_category=corrected,
        reviewed_by=review.reviewer,
        reviewed_at=reviewed_at,
        approved=review.approved,
    )


@router.get("/history", response_model=ReviewQueueResponse)
async def get_review_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=100, description="Items per page")
    ] = 20,
    reviewer: Annotated[
        str | None,
        Query(description="Filter by reviewer"),
    ] = None,
    corrected_only: Annotated[
        bool,
        Query(description="Only show items where category was corrected"),
    ] = False,
) -> ReviewQueueResponse:
    """Get history of reviewed classifications.

    Returns paginated list of email classifications that have been reviewed.
    Ordered by reviewed_at descending (most recent first).
    """
    # Build the base query for reviewed items
    query = select(EmailClassification).where(
        EmailClassification.reviewed == True,  # noqa: E712
    )

    # Apply filters
    if reviewer:
        query = query.where(EmailClassification.reviewed_by == reviewer)
    if corrected_only:
        query = query.where(EmailClassification.corrected_category.isnot(None))

    # Count total items
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Calculate pagination
    total_pages = max(1, (total + page_size - 1) // page_size)
    offset = (page - 1) * page_size

    # Fetch items with pagination
    items_query = (
        query.order_by(EmailClassification.reviewed_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(items_query)
    items = result.scalars().all()

    return ReviewQueueResponse(
        items=[EmailClassificationResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
