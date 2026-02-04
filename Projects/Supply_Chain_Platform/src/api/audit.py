"""FastAPI routes for agent audit log queries.

This module provides API endpoints for:
- Querying audit logs with filters and pagination
- Getting audit statistics
- Retrieving workflow audit trails
- Analyzing agent decision patterns
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.services.audit_logging import (
    AuditLogFilters,
    count_audit_logs,
    get_agent_decision_summary,
    get_audit_log_by_id,
    get_audit_logs,
    get_audit_stats,
    get_low_confidence_decisions,
    get_workflow_audit_trail,
)

router = APIRouter(prefix="/audit", tags=["audit"])


# --- Pydantic Schemas ---


class AuditLogResponse(BaseModel):
    """Response schema for a single audit log entry."""

    id: UUID = Field(description="Audit log UUID")
    workflow_id: UUID | None = Field(description="Workflow UUID")
    thread_id: str | None = Field(description="LangGraph thread ID")
    timestamp: datetime = Field(description="When the decision was made")
    agent: str = Field(description="Agent that made the decision")
    action: str = Field(description="Action taken")
    reasoning: str = Field(description="Explanation of the decision")
    inputs: dict[str, Any] | None = Field(description="Input data for the decision")
    outputs: dict[str, Any] | None = Field(description="Output data from the decision")
    confidence: float | None = Field(description="Confidence score (0.0-1.0)")
    sku_id: UUID | None = Field(description="Product SKU UUID")
    sku: str | None = Field(description="Product SKU code")
    created_at: datetime = Field(description="Record creation timestamp")

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    """Response schema for audit log listing with pagination."""

    items: list[AuditLogResponse] = Field(description="List of audit log entries")
    total: int = Field(description="Total number of matching entries")
    page: int = Field(description="Current page number")
    page_size: int = Field(description="Items per page")
    total_pages: int = Field(description="Total number of pages")


class AuditStatsResponse(BaseModel):
    """Response schema for audit log statistics."""

    total_entries: int = Field(description="Total number of audit entries")
    entries_by_agent: dict[str, int] = Field(description="Count by agent name")
    entries_by_action: dict[str, int] = Field(description="Count by action type")
    avg_confidence: float | None = Field(description="Average confidence score")
    low_confidence_count: int = Field(description="Entries with confidence < 0.85")
    entries_by_sku: dict[str, int] = Field(description="Count by SKU code")
    earliest_entry: datetime | None = Field(description="Oldest entry timestamp")
    latest_entry: datetime | None = Field(description="Newest entry timestamp")


class AgentSummaryResponse(BaseModel):
    """Response schema for agent decision summary."""

    agent: str = Field(description="Agent name")
    period_days: int = Field(description="Analysis period in days")
    total_decisions: int = Field(description="Total decisions in period")
    actions: dict[str, int] = Field(description="Count by action type")
    avg_confidence: float | None = Field(description="Average confidence score")
    low_confidence_count: int = Field(description="Low confidence decision count")
    affected_skus: dict[str, int] = Field(description="Decisions by SKU")


# --- API Endpoints ---


@router.get("/logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=100, description="Items per page")
    ] = 20,
    workflow_id: Annotated[
        UUID | None,
        Query(description="Filter by workflow UUID"),
    ] = None,
    agent: Annotated[
        str | None,
        Query(description="Filter by agent name"),
    ] = None,
    action: Annotated[
        str | None,
        Query(description="Filter by action type"),
    ] = None,
    sku: Annotated[
        str | None,
        Query(description="Filter by SKU code"),
    ] = None,
    min_confidence: Annotated[
        float | None,
        Query(ge=0.0, le=1.0, description="Minimum confidence filter"),
    ] = None,
    max_confidence: Annotated[
        float | None,
        Query(ge=0.0, le=1.0, description="Maximum confidence filter"),
    ] = None,
    start_time: Annotated[
        datetime | None,
        Query(description="Filter for entries after this time"),
    ] = None,
    end_time: Annotated[
        datetime | None,
        Query(description="Filter for entries before this time"),
    ] = None,
) -> AuditLogListResponse:
    """List audit log entries with filtering and pagination.

    Returns paginated list of agent decision audit entries.
    Entries are sorted by timestamp descending (most recent first).

    Use filters to narrow down results:
    - workflow_id: Find all decisions for a specific workflow
    - agent: Analyze decisions by a specific agent
    - action: Find specific types of actions
    - sku: Track decisions affecting a specific product
    - confidence thresholds: Find low/high confidence decisions
    - time range: Audit decisions over a specific period
    """
    filters = AuditLogFilters(
        workflow_id=str(workflow_id) if workflow_id else None,
        agent=agent,
        action=action,
        sku=sku.upper() if sku else None,
        min_confidence=min_confidence,
        max_confidence=max_confidence,
        start_time=start_time,
        end_time=end_time,
    )

    # Get total count
    total = await count_audit_logs(db, filters)

    # Calculate pagination
    total_pages = max(1, (total + page_size - 1) // page_size)
    offset = (page - 1) * page_size

    # Get items
    items = await get_audit_logs(
        db,
        filters=filters,
        limit=page_size,
        offset=offset,
    )

    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/logs/{audit_id}", response_model=AuditLogResponse)
async def get_audit_log(
    audit_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuditLogResponse:
    """Get a specific audit log entry by ID.

    Returns the full audit log entry including inputs, outputs, and reasoning.
    """
    entry = await get_audit_log_by_id(db, str(audit_id))
    if not entry:
        raise HTTPException(
            status_code=404,
            detail=f"Audit log entry '{audit_id}' not found",
        )
    return AuditLogResponse.model_validate(entry)


@router.get("/workflow/{workflow_id}", response_model=list[AuditLogResponse])
async def get_workflow_audit(
    workflow_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AuditLogResponse]:
    """Get the complete audit trail for a workflow.

    Returns all audit log entries for the specified workflow,
    ordered chronologically (oldest first).

    This provides a complete history of all agent decisions
    made during the workflow execution.
    """
    entries = await get_workflow_audit_trail(db, str(workflow_id))
    return [AuditLogResponse.model_validate(entry) for entry in entries]


@router.get("/stats", response_model=AuditStatsResponse)
async def get_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    workflow_id: Annotated[
        UUID | None,
        Query(description="Filter by workflow UUID"),
    ] = None,
    agent: Annotated[
        str | None,
        Query(description="Filter by agent name"),
    ] = None,
    sku_id: Annotated[
        UUID | None,
        Query(description="Filter by SKU UUID"),
    ] = None,
    start_time: Annotated[
        datetime | None,
        Query(description="Filter for entries after this time"),
    ] = None,
    end_time: Annotated[
        datetime | None,
        Query(description="Filter for entries before this time"),
    ] = None,
) -> AuditStatsResponse:
    """Get aggregate statistics for audit logs.

    Returns counts and averages for analyzing agent decision patterns.
    Use filters to narrow down the analysis scope.
    """
    filters = AuditLogFilters(
        workflow_id=str(workflow_id) if workflow_id else None,
        agent=agent,
        sku_id=str(sku_id) if sku_id else None,
        start_time=start_time,
        end_time=end_time,
    )

    stats = await get_audit_stats(db, filters)

    return AuditStatsResponse(
        total_entries=stats.total_entries,
        entries_by_agent=stats.entries_by_agent,
        entries_by_action=stats.entries_by_action,
        avg_confidence=stats.avg_confidence,
        low_confidence_count=stats.low_confidence_count,
        entries_by_sku=stats.entries_by_sku,
        earliest_entry=stats.earliest_entry,
        latest_entry=stats.latest_entry,
    )


@router.get("/low-confidence", response_model=list[AuditLogResponse])
async def get_low_confidence(
    db: Annotated[AsyncSession, Depends(get_db)],
    threshold: Annotated[
        float,
        Query(ge=0.0, le=1.0, description="Confidence threshold"),
    ] = 0.85,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Maximum results"),
    ] = 50,
    days: Annotated[
        int | None,
        Query(ge=1, description="Look back this many days"),
    ] = None,
) -> list[AuditLogResponse]:
    """Get audit entries with confidence below threshold.

    Returns decisions that may need human review due to
    low confidence scores.

    This is useful for:
    - Identifying problematic agent behavior
    - Finding decisions that need verification
    - Quality assurance of automated decisions
    """
    start_time = datetime.now(UTC) - timedelta(days=days) if days else None

    entries = await get_low_confidence_decisions(
        db,
        threshold=threshold,
        limit=limit,
        start_time=start_time,
    )

    return [AuditLogResponse.model_validate(entry) for entry in entries]


@router.get("/agents/{agent}/summary", response_model=AgentSummaryResponse)
async def get_agent_summary(
    agent: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    days: Annotated[
        int,
        Query(ge=1, le=365, description="Analysis period in days"),
    ] = 30,
) -> AgentSummaryResponse:
    """Get a summary of decisions made by a specific agent.

    Analyzes the agent's behavior over the specified period,
    including:
    - Total decision count
    - Breakdown by action type
    - Average confidence
    - Low confidence decision count
    - Affected SKUs

    Useful for monitoring agent performance and identifying issues.
    """
    summary = await get_agent_decision_summary(db, agent, days)

    return AgentSummaryResponse(
        agent=summary["agent"],
        period_days=summary["period_days"],
        total_decisions=summary["total_decisions"],
        actions=summary["actions"],
        avg_confidence=summary["avg_confidence"],
        low_confidence_count=summary["low_confidence_count"],
        affected_skus=summary["affected_skus"],
    )


@router.get("/agents", response_model=list[str])
async def list_agents(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[str]:
    """List all unique agent names in the audit log.

    Returns a list of all agent names that have logged decisions.
    """
    stats = await get_audit_stats(db)
    return sorted(stats.entries_by_agent.keys())


@router.get("/actions", response_model=list[str])
async def list_actions(
    db: Annotated[AsyncSession, Depends(get_db)],
    agent: Annotated[
        str | None,
        Query(description="Filter by agent name"),
    ] = None,
) -> list[str]:
    """List all unique action types in the audit log.

    Optionally filter by agent to see actions for a specific agent.
    """
    filters = AuditLogFilters(agent=agent) if agent else None
    stats = await get_audit_stats(db, filters)
    return sorted(stats.entries_by_action.keys())
