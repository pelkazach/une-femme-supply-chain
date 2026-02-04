"""Workflow orchestration service for procurement workflows.

This module provides high-level functions to:
- Start new procurement workflows with PostgreSQL checkpointing
- Resume workflows after human approval decisions
- Query workflow state and status
- Configure checkpointing for production and testing

The orchestrator handles the integration between:
- LangGraph state machine (procurement.py)
- PostgreSQL persistence (ProcurementWorkflow model)
- Checkpoint storage (langgraph-checkpoint-postgres)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.procurement import (
    ApprovalStatus,
    ProcurementState,
    WorkflowStatus,
    build_procurement_workflow,
    create_initial_state,
    process_approval,
)
from src.models.procurement_workflow import ProcurementWorkflow

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# Global checkpointer - can be configured for production or testing
_checkpointer: BaseCheckpointSaver | None = None


def get_memory_checkpointer() -> MemorySaver:
    """Get an in-memory checkpointer for testing.

    Returns:
        MemorySaver instance for testing without PostgreSQL
    """
    return MemorySaver()


async def get_postgres_checkpointer(connection_string: str) -> BaseCheckpointSaver[Any]:
    """Get a PostgreSQL checkpointer for production.

    Args:
        connection_string: PostgreSQL connection string

    Returns:
        PostgresSaver instance for production checkpointing

    Note:
        This requires the langgraph-checkpoint-postgres package.
        The checkpoint tables are created automatically on first use.
    """
    try:
        from langgraph.checkpoint.postgres.aio import (  # type: ignore[import-not-found]
            AsyncPostgresSaver,
        )

        checkpointer = AsyncPostgresSaver.from_conn_string(connection_string)
        # Setup creates the checkpoint tables if they don't exist
        await checkpointer.setup()
        return cast(BaseCheckpointSaver[Any], checkpointer)
    except ImportError:
        logger.warning(
            "langgraph-checkpoint-postgres not installed, falling back to MemorySaver"
        )
        return MemorySaver()


def set_checkpointer(checkpointer: BaseCheckpointSaver | None) -> None:
    """Set the global checkpointer for workflow persistence.

    Args:
        checkpointer: Checkpointer instance or None to use default
    """
    global _checkpointer
    _checkpointer = checkpointer


def get_checkpointer() -> BaseCheckpointSaver:
    """Get the current checkpointer, defaulting to MemorySaver.

    Returns:
        The configured checkpointer or a MemorySaver if none configured
    """
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = MemorySaver()
    return _checkpointer


async def start_workflow(
    session: AsyncSession,
    sku_id: str,
    sku: str,
    current_inventory: int,
    thread_id: str | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
) -> tuple[str, ProcurementState]:
    """Start a new procurement workflow.

    This function:
    1. Creates a ProcurementWorkflow record in the database
    2. Initializes the LangGraph state machine
    3. Runs the workflow until it hits an interrupt point (human approval)
    4. Persists the workflow state for later resumption

    Args:
        session: Database session for persisting workflow
        sku_id: Product SKU UUID
        sku: Product SKU code (e.g., "UFBub250")
        current_inventory: Current inventory level
        thread_id: Optional thread ID (generated if not provided)
        checkpointer: Optional checkpointer (uses global if not provided)

    Returns:
        Tuple of (workflow_id, final_state)

    Raises:
        ValueError: If SKU ID is invalid
    """
    # Generate IDs
    workflow_id = str(uuid4())
    if thread_id is None:
        thread_id = f"workflow-{workflow_id}"

    logger.info(f"Starting procurement workflow for SKU {sku} (thread: {thread_id})")

    # Create database record
    workflow = ProcurementWorkflow(
        id=workflow_id,
        thread_id=thread_id,
        sku_id=sku_id,
        sku=sku,
        current_inventory=current_inventory,
        approval_status=ApprovalStatus.PENDING.value,
        workflow_status=WorkflowStatus.INITIALIZED.value,
        audit_log=[],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(workflow)
    await session.flush()

    # Create initial state
    initial_state = create_initial_state(
        sku_id=sku_id,
        sku=sku,
        current_inventory=current_inventory,
    )

    # Get checkpointer
    cp = checkpointer or get_checkpointer()

    # Compile and run workflow
    graph = build_procurement_workflow()
    compiled = graph.compile(
        checkpointer=cp,
        interrupt_before=["run_approval"],
    )

    # Run workflow with config
    config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}

    try:
        # Invoke runs until interrupt or completion
        result = cast(
            dict[str, Any], compiled.invoke(initial_state, config)  # type: ignore[arg-type]
        )

        # Update database record with workflow results
        await _sync_workflow_to_db(session, workflow_id, result)

        logger.info(
            f"Workflow {workflow_id} reached status: {result.get('workflow_status')}"
        )

        return workflow_id, cast(ProcurementState, result)

    except Exception as e:
        logger.error(f"Workflow {workflow_id} failed: {e}")
        # Update workflow with error
        await session.execute(
            update(ProcurementWorkflow)
            .where(ProcurementWorkflow.id == workflow_id)
            .values(
                workflow_status=WorkflowStatus.FAILED.value,
                error_message=str(e),
                updated_at=datetime.now(UTC),
            )
        )
        await session.commit()
        raise


async def resume_workflow(
    session: AsyncSession,
    workflow_id: str,
    approved: bool,
    reviewer_id: str,
    feedback: str = "",
    checkpointer: BaseCheckpointSaver | None = None,
) -> ProcurementState:
    """Resume a workflow after human approval decision.

    This function:
    1. Loads the workflow from the database
    2. Validates it's in the correct state for resumption
    3. Processes the approval decision
    4. Resumes the LangGraph workflow
    5. Returns the final state

    Args:
        session: Database session
        workflow_id: Workflow UUID to resume
        approved: True if approved, False if rejected
        reviewer_id: ID/email of the reviewer
        feedback: Optional feedback/reason for decision
        checkpointer: Optional checkpointer (uses global if not provided)

    Returns:
        Final workflow state after resumption

    Raises:
        ValueError: If workflow not found or not in correct state
    """
    # Load workflow from database
    db_result = await session.execute(
        select(ProcurementWorkflow).where(ProcurementWorkflow.id == workflow_id)
    )
    workflow = db_result.scalar_one_or_none()

    if not workflow:
        raise ValueError(f"Workflow '{workflow_id}' not found")

    if workflow.approval_status != ApprovalStatus.PENDING.value:
        raise ValueError(
            f"Workflow '{workflow_id}' is not pending approval "
            f"(status: {workflow.approval_status})"
        )

    if workflow.workflow_status != WorkflowStatus.AWAITING_APPROVAL.value:
        raise ValueError(
            f"Workflow '{workflow_id}' is not awaiting approval "
            f"(status: {workflow.workflow_status})"
        )

    logger.info(
        f"Resuming workflow {workflow_id} with decision: "
        f"{'approved' if approved else 'rejected'} by {reviewer_id}"
    )

    # Build state from database record
    current_state: ProcurementState = {
        "sku_id": workflow.sku_id,
        "sku": workflow.sku,
        "current_inventory": workflow.current_inventory,
        "forecast": [],  # Loaded from checkpoint
        "forecast_confidence": workflow.forecast_confidence or 0.0,
        "safety_stock": workflow.safety_stock or 0,
        "reorder_point": workflow.reorder_point or 0,
        "recommended_quantity": workflow.recommended_quantity or 0,
        "vendors": [],
        "selected_vendor": workflow.selected_vendor or {},
        "order_value": workflow.order_value or 0.0,
        "approval_status": workflow.approval_status,
        "approval_required_level": workflow.approval_required_level or "",
        "human_feedback": "",
        "reviewer_id": "",
        "workflow_status": workflow.workflow_status,
        "error_message": "",
        "created_at": workflow.created_at.isoformat(),
        "updated_at": workflow.updated_at.isoformat(),
        "audit_log": workflow.audit_log or [],
    }

    # Process approval decision - this updates the state
    approval_update = process_approval(
        state=current_state,
        approved=approved,
        reviewer_id=reviewer_id,
        feedback=feedback,
    )

    # Get checkpointer
    cp = checkpointer or get_checkpointer()

    # Compile workflow without interrupt (approval is done)
    graph = build_procurement_workflow()
    compiled = graph.compile(
        checkpointer=cp,
        interrupt_before=[],  # No more interrupts
    )

    # Config with same thread_id to continue from checkpoint
    config: dict[str, Any] = {"configurable": {"thread_id": workflow.thread_id}}

    try:
        # Merge approval update into current state
        merged_state: dict[str, Any] = {**current_state, **approval_update}

        # Resume workflow - approval continues to generate_po, rejection ends workflow
        workflow_result: dict[str, Any] = (
            cast(dict[str, Any], compiled.invoke(merged_state, config))  # type: ignore[arg-type]
            if approved
            else merged_state
        )

        # Update database record
        await _sync_workflow_to_db(session, workflow_id, workflow_result)

        logger.info(
            f"Workflow {workflow_id} completed with status: {workflow_result.get('workflow_status')}"
        )

        return cast(ProcurementState, workflow_result)

    except Exception as e:
        logger.error(f"Workflow {workflow_id} resume failed: {e}")
        # Update workflow with error
        await session.execute(
            update(ProcurementWorkflow)
            .where(ProcurementWorkflow.id == workflow_id)
            .values(
                workflow_status=WorkflowStatus.FAILED.value,
                error_message=str(e),
                updated_at=datetime.now(UTC),
            )
        )
        await session.commit()
        raise


async def get_workflow_state(
    session: AsyncSession,
    workflow_id: str,
) -> ProcurementWorkflow | None:
    """Get the current state of a workflow.

    Args:
        session: Database session
        workflow_id: Workflow UUID

    Returns:
        ProcurementWorkflow record or None if not found
    """
    result = await session.execute(
        select(ProcurementWorkflow).where(ProcurementWorkflow.id == workflow_id)
    )
    return result.scalar_one_or_none()


async def get_pending_approvals(
    session: AsyncSession,
    approval_level: str | None = None,
    limit: int = 100,
) -> list[ProcurementWorkflow]:
    """Get workflows pending approval.

    Args:
        session: Database session
        approval_level: Optional filter by level ("manager" or "executive")
        limit: Maximum number of results

    Returns:
        List of ProcurementWorkflow records pending approval
    """
    query = select(ProcurementWorkflow).where(
        ProcurementWorkflow.approval_status == ApprovalStatus.PENDING.value,
        ProcurementWorkflow.workflow_status == WorkflowStatus.AWAITING_APPROVAL.value,
    )

    if approval_level:
        query = query.where(
            ProcurementWorkflow.approval_required_level == approval_level.lower()
        )

    query = query.order_by(ProcurementWorkflow.order_value.desc()).limit(limit)

    result = await session.execute(query)
    return list(result.scalars().all())


async def _sync_workflow_to_db(
    session: AsyncSession,
    workflow_id: str,
    state: dict[str, Any],
) -> None:
    """Sync workflow state from LangGraph to database.

    Args:
        session: Database session
        workflow_id: Workflow UUID
        state: Current LangGraph state
    """
    await session.execute(
        update(ProcurementWorkflow)
        .where(ProcurementWorkflow.id == workflow_id)
        .values(
            forecast_confidence=state.get("forecast_confidence"),
            safety_stock=state.get("safety_stock"),
            reorder_point=state.get("reorder_point"),
            recommended_quantity=state.get("recommended_quantity"),
            selected_vendor=state.get("selected_vendor"),
            order_value=state.get("order_value"),
            approval_status=state.get("approval_status", ApprovalStatus.PENDING.value),
            approval_required_level=state.get("approval_required_level"),
            reviewer_id=state.get("reviewer_id"),
            human_feedback=state.get("human_feedback"),
            workflow_status=state.get("workflow_status", WorkflowStatus.INITIALIZED.value),
            error_message=state.get("error_message"),
            audit_log=state.get("audit_log", []),
            updated_at=datetime.now(UTC),
        )
    )
    await session.commit()


def is_workflow_paused_for_approval(state: ProcurementState) -> bool:
    """Check if a workflow is paused waiting for human approval.

    Args:
        state: Workflow state

    Returns:
        True if workflow is awaiting human approval
    """
    return (
        state.get("approval_status") == ApprovalStatus.PENDING.value
        and state.get("workflow_status") == WorkflowStatus.AWAITING_APPROVAL.value
    )


def requires_executive_approval(state: ProcurementState) -> bool:
    """Check if a workflow requires executive approval (>$10K).

    Args:
        state: Workflow state

    Returns:
        True if order value exceeds $10,000
    """
    order_value = state.get("order_value", 0.0)
    return order_value > 10000.0


def requires_manager_approval(state: ProcurementState) -> bool:
    """Check if a workflow requires manager approval ($5K-$10K or low confidence).

    Args:
        state: Workflow state

    Returns:
        True if order requires manager review
    """
    order_value = state.get("order_value", 0.0)
    confidence = state.get("forecast_confidence", 0.0)

    # $5K-$10K range, or low confidence (<85%) for orders under $5K
    return (
        5000.0 < order_value <= 10000.0
        or (order_value <= 5000.0 and confidence < 0.85)
    )
