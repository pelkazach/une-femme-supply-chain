"""FastAPI routes for procurement approval workflow."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.procurement import (
    ApprovalStatus,
    WorkflowStatus,
    determine_approval_level,
    process_approval,
)
from src.database import get_db
from src.models.procurement_workflow import ProcurementWorkflow

router = APIRouter(prefix="/approvals", tags=["approvals"])


# --- Pydantic Schemas ---


class VendorInfo(BaseModel):
    """Vendor information in workflow state."""

    vendor_id: str | None = Field(description="Vendor UUID")
    vendor_name: str | None = Field(description="Vendor name")
    unit_price: float | None = Field(description="Price per unit")
    lead_time_days: int | None = Field(description="Lead time in days")
    minimum_order_quantity: int | None = Field(description="Minimum order quantity")
    reliability_score: float | None = Field(description="Vendor reliability (0-1)")


class WorkflowResponse(BaseModel):
    """Response schema for a procurement workflow."""

    id: UUID = Field(description="Workflow UUID")
    thread_id: str = Field(description="LangGraph thread ID")
    sku_id: UUID = Field(description="Product SKU UUID")
    sku: str = Field(description="Product SKU code")
    current_inventory: int = Field(description="Inventory level when workflow started")
    forecast_confidence: float | None = Field(description="Forecast confidence score")
    safety_stock: int | None = Field(description="Calculated safety stock level")
    reorder_point: int | None = Field(description="Inventory level that triggers reorder")
    recommended_quantity: int | None = Field(description="Recommended order quantity")
    selected_vendor: dict | None = Field(description="Selected vendor details")
    order_value: float | None = Field(description="Total order value")
    approval_status: str = Field(description="Approval status (pending, approved, rejected)")
    approval_required_level: str | None = Field(description="Required approval level")
    reviewer_id: str | None = Field(description="ID of the reviewer")
    human_feedback: str | None = Field(description="Feedback from reviewer")
    workflow_status: str = Field(description="Current workflow status")
    error_message: str | None = Field(description="Error message if failed")
    created_at: datetime = Field(description="When workflow was created")
    updated_at: datetime = Field(description="When workflow was last updated")

    model_config = {"from_attributes": True}


class ApprovalQueueResponse(BaseModel):
    """Response schema for the approval queue listing."""

    items: list[WorkflowResponse] = Field(description="List of workflows pending approval")
    total: int = Field(description="Total number of items pending approval")
    page: int = Field(description="Current page number")
    page_size: int = Field(description="Items per page")
    total_pages: int = Field(description="Total number of pages")


class ApprovalQueueStats(BaseModel):
    """Statistics about the approval queue."""

    pending_total: int = Field(description="Total items pending approval")
    pending_executive: int = Field(description="Items pending executive approval (>$10K)")
    pending_manager: int = Field(description="Items pending manager approval ($5K-$10K)")
    approved_today: int = Field(description="Items approved today")
    rejected_today: int = Field(description="Items rejected today")
    total_value_pending: float = Field(description="Total order value pending approval")
    avg_order_value: float | None = Field(description="Average order value of pending items")
    by_sku: dict[str, int] = Field(description="Pending approval count by SKU")


class ApprovalDecisionRequest(BaseModel):
    """Request schema for submitting an approval decision."""

    approved: bool = Field(description="True to approve, False to reject")
    reviewer_id: str = Field(description="ID/email of the reviewer")
    feedback: str = Field(
        default="",
        description="Optional feedback or reason for decision",
    )


class ApprovalDecisionResponse(BaseModel):
    """Response schema for an approval decision."""

    workflow_id: UUID = Field(description="Workflow UUID")
    sku: str = Field(description="Product SKU code")
    order_value: float = Field(description="Order value")
    approved: bool = Field(description="Whether order was approved")
    reviewer_id: str = Field(description="Who made the decision")
    reviewed_at: datetime = Field(description="When decision was made")
    next_status: str = Field(description="Workflow status after decision")


# --- API Endpoints ---


@router.get("/queue", response_model=ApprovalQueueResponse)
async def get_approval_queue(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=100, description="Items per page")
    ] = 20,
    approval_level: Annotated[
        str | None,
        Query(description="Filter by approval level (manager, executive)"),
    ] = None,
    sku: Annotated[
        str | None,
        Query(description="Filter by SKU code"),
    ] = None,
    min_value: Annotated[
        float | None,
        Query(ge=0, description="Minimum order value filter"),
    ] = None,
    max_value: Annotated[
        float | None,
        Query(ge=0, description="Maximum order value filter"),
    ] = None,
) -> ApprovalQueueResponse:
    """Get the queue of procurement orders pending approval.

    Returns paginated list of procurement workflows awaiting human approval.
    Orders are sorted by order value descending (highest value first).

    Orders >$10K require executive approval.
    Orders $5K-$10K or with low confidence require manager approval.
    """
    # Build the base query for pending approvals
    query = select(ProcurementWorkflow).where(
        ProcurementWorkflow.approval_status == ApprovalStatus.PENDING.value,
        ProcurementWorkflow.workflow_status == WorkflowStatus.AWAITING_APPROVAL.value,
    )

    # Apply filters
    if approval_level:
        query = query.where(
            ProcurementWorkflow.approval_required_level == approval_level.lower()
        )
    if sku:
        query = query.where(ProcurementWorkflow.sku == sku.upper())
    if min_value is not None:
        query = query.where(ProcurementWorkflow.order_value >= min_value)
    if max_value is not None:
        query = query.where(ProcurementWorkflow.order_value <= max_value)

    # Count total items
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Calculate pagination
    total_pages = max(1, (total + page_size - 1) // page_size)
    offset = (page - 1) * page_size

    # Fetch items with pagination, ordered by order_value descending
    items_query = (
        query.order_by(ProcurementWorkflow.order_value.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(items_query)
    items = result.scalars().all()

    return ApprovalQueueResponse(
        items=[WorkflowResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/queue/stats", response_model=ApprovalQueueStats)
async def get_approval_queue_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApprovalQueueStats:
    """Get statistics about the approval queue.

    Returns counts of pending approvals by level, today's decisions,
    and total value pending.
    """
    # Base filter for pending approvals
    pending_filter = (
        ProcurementWorkflow.approval_status == ApprovalStatus.PENDING.value,
        ProcurementWorkflow.workflow_status == WorkflowStatus.AWAITING_APPROVAL.value,
    )

    # Count total pending
    pending_query = select(func.count()).where(*pending_filter)
    pending_result = await db.execute(pending_query)
    pending_total = pending_result.scalar() or 0

    # Count pending by level
    exec_query = select(func.count()).where(
        *pending_filter,
        ProcurementWorkflow.approval_required_level == "executive",
    )
    exec_result = await db.execute(exec_query)
    pending_executive = exec_result.scalar() or 0

    manager_query = select(func.count()).where(
        *pending_filter,
        ProcurementWorkflow.approval_required_level == "manager",
    )
    manager_result = await db.execute(manager_query)
    pending_manager = manager_result.scalar() or 0

    # Count approved/rejected today
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    approved_today_query = select(func.count()).where(
        ProcurementWorkflow.approval_status == ApprovalStatus.APPROVED.value,
        ProcurementWorkflow.updated_at >= today_start,
    )
    approved_result = await db.execute(approved_today_query)
    approved_today = approved_result.scalar() or 0

    rejected_today_query = select(func.count()).where(
        ProcurementWorkflow.approval_status == ApprovalStatus.REJECTED.value,
        ProcurementWorkflow.updated_at >= today_start,
    )
    rejected_result = await db.execute(rejected_today_query)
    rejected_today = rejected_result.scalar() or 0

    # Total and average value of pending items
    value_query = select(
        func.sum(ProcurementWorkflow.order_value),
        func.avg(ProcurementWorkflow.order_value),
    ).where(*pending_filter)
    value_result = await db.execute(value_query)
    value_row = value_result.one()
    total_value_pending = float(value_row[0]) if value_row[0] else 0.0
    avg_order_value = float(value_row[1]) if value_row[1] else None

    # Count by SKU for pending items
    by_sku_query = (
        select(
            ProcurementWorkflow.sku,
            func.count().label("count"),
        )
        .where(*pending_filter)
        .group_by(ProcurementWorkflow.sku)
    )
    by_sku_result = await db.execute(by_sku_query)
    by_sku = {row[0]: row[1] for row in by_sku_result}

    return ApprovalQueueStats(
        pending_total=pending_total,
        pending_executive=pending_executive,
        pending_manager=pending_manager,
        approved_today=approved_today,
        rejected_today=rejected_today,
        total_value_pending=total_value_pending,
        avg_order_value=avg_order_value,
        by_sku=by_sku,
    )


@router.get("/queue/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkflowResponse:
    """Get a specific procurement workflow by ID.

    Returns the full workflow record including audit log.
    """
    result = await db.execute(
        select(ProcurementWorkflow).where(ProcurementWorkflow.id == str(workflow_id))
    )
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow with ID '{workflow_id}' not found",
        )

    return WorkflowResponse.model_validate(workflow)


@router.post("/queue/{workflow_id}/decide", response_model=ApprovalDecisionResponse)
async def submit_approval_decision(
    workflow_id: UUID,
    decision: ApprovalDecisionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApprovalDecisionResponse:
    """Submit an approval or rejection decision for a pending workflow.

    This endpoint processes a human approval decision:
    - If approved, the workflow continues to generate the purchase order
    - If rejected, the workflow is marked as completed without generating a PO

    The decision is recorded in the audit log with the reviewer's ID and feedback.
    """
    # Find the workflow
    result = await db.execute(
        select(ProcurementWorkflow).where(ProcurementWorkflow.id == str(workflow_id))
    )
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow with ID '{workflow_id}' not found",
        )

    # Verify workflow is pending approval
    if workflow.approval_status != ApprovalStatus.PENDING.value:
        raise HTTPException(
            status_code=400,
            detail=f"Workflow '{workflow_id}' is not pending approval. "
            f"Current status: {workflow.approval_status}",
        )

    if workflow.workflow_status != WorkflowStatus.AWAITING_APPROVAL.value:
        raise HTTPException(
            status_code=400,
            detail=f"Workflow '{workflow_id}' is not in awaiting_approval state. "
            f"Current status: {workflow.workflow_status}",
        )

    # Process the approval decision
    # Build a minimal state dict for process_approval
    current_state = {
        "sku": workflow.sku,
        "order_value": workflow.order_value or 0.0,
        "recommended_quantity": workflow.recommended_quantity or 0,
        "approval_required_level": workflow.approval_required_level,
    }

    state_update = process_approval(
        state=current_state,
        approved=decision.approved,
        reviewer_id=decision.reviewer_id,
        feedback=decision.feedback,
    )

    # Update the workflow in the database
    reviewed_at = datetime.now(UTC)

    # Merge new audit log entry with existing audit log
    existing_audit_log = workflow.audit_log or []
    new_audit_log = existing_audit_log + state_update.get("audit_log", [])

    await db.execute(
        update(ProcurementWorkflow)
        .where(ProcurementWorkflow.id == str(workflow_id))
        .values(
            approval_status=state_update["approval_status"],
            workflow_status=state_update["workflow_status"],
            reviewer_id=decision.reviewer_id,
            human_feedback=decision.feedback if decision.feedback else None,
            audit_log=new_audit_log,
            updated_at=reviewed_at,
        )
    )
    await db.commit()

    return ApprovalDecisionResponse(
        workflow_id=workflow_id,
        sku=workflow.sku,
        order_value=workflow.order_value or 0.0,
        approved=decision.approved,
        reviewer_id=decision.reviewer_id,
        reviewed_at=reviewed_at,
        next_status=state_update["workflow_status"],
    )


@router.get("/history", response_model=ApprovalQueueResponse)
async def get_approval_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=100, description="Items per page")
    ] = 20,
    status: Annotated[
        str | None,
        Query(description="Filter by approval status (approved, rejected)"),
    ] = None,
    reviewer_id: Annotated[
        str | None,
        Query(description="Filter by reviewer ID"),
    ] = None,
    sku: Annotated[
        str | None,
        Query(description="Filter by SKU code"),
    ] = None,
) -> ApprovalQueueResponse:
    """Get history of approval decisions.

    Returns paginated list of workflows that have been approved or rejected.
    Ordered by updated_at descending (most recent first).
    """
    # Build the base query for decided workflows
    query = select(ProcurementWorkflow).where(
        ProcurementWorkflow.approval_status.in_([
            ApprovalStatus.APPROVED.value,
            ApprovalStatus.REJECTED.value,
        ])
    )

    # Apply filters
    if status:
        query = query.where(ProcurementWorkflow.approval_status == status.lower())
    if reviewer_id:
        query = query.where(ProcurementWorkflow.reviewer_id == reviewer_id)
    if sku:
        query = query.where(ProcurementWorkflow.sku == sku.upper())

    # Count total items
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Calculate pagination
    total_pages = max(1, (total + page_size - 1) // page_size)
    offset = (page - 1) * page_size

    # Fetch items with pagination
    items_query = (
        query.order_by(ProcurementWorkflow.updated_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(items_query)
    items = result.scalars().all()

    return ApprovalQueueResponse(
        items=[WorkflowResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
