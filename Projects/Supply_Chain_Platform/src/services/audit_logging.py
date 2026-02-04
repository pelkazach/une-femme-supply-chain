"""Audit logging service for agent decision tracking.

This module provides functions for:
- Logging agent decisions to the normalized agent_audit_logs table
- Querying audit logs by various criteria
- Aggregating audit statistics for analysis
- Syncing JSON audit logs to normalized storage
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent_audit_log import AgentAuditLog


@dataclass(frozen=True)
class AuditLogFilters:
    """Filters for querying audit logs.

    Attributes:
        workflow_id: Filter by workflow UUID
        thread_id: Filter by LangGraph thread ID
        agent: Filter by agent name
        action: Filter by action type
        sku_id: Filter by SKU UUID
        sku: Filter by SKU code
        min_confidence: Filter for confidence >= this value
        max_confidence: Filter for confidence <= this value
        start_time: Filter for timestamp >= this value
        end_time: Filter for timestamp <= this value
    """

    workflow_id: str | None = None
    thread_id: str | None = None
    agent: str | None = None
    action: str | None = None
    sku_id: str | None = None
    sku: str | None = None
    min_confidence: float | None = None
    max_confidence: float | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None


@dataclass(frozen=True)
class AuditLogStats:
    """Statistics for audit log analysis.

    Attributes:
        total_entries: Total number of audit entries
        entries_by_agent: Count by agent name
        entries_by_action: Count by action type
        avg_confidence: Average confidence across all entries
        low_confidence_count: Count of entries with confidence < 0.85
        entries_by_sku: Count by SKU code
        earliest_entry: Timestamp of oldest entry
        latest_entry: Timestamp of newest entry
    """

    total_entries: int
    entries_by_agent: dict[str, int]
    entries_by_action: dict[str, int]
    avg_confidence: float | None
    low_confidence_count: int
    entries_by_sku: dict[str, int]
    earliest_entry: datetime | None
    latest_entry: datetime | None


async def log_agent_decision(
    session: AsyncSession,
    agent: str,
    action: str,
    reasoning: str,
    inputs: dict[str, Any] | None = None,
    outputs: dict[str, Any] | None = None,
    confidence: float | None = None,
    workflow_id: str | None = None,
    thread_id: str | None = None,
    sku_id: str | None = None,
    sku: str | None = None,
    timestamp: datetime | None = None,
) -> AgentAuditLog:
    """Log an agent decision to the audit trail.

    Creates a new AgentAuditLog entry in the database for tracking
    agent decisions with full context and reasoning.

    Args:
        session: Database session
        agent: Name of the agent making the decision
        action: Type of action taken
        reasoning: Human-readable explanation of the decision
        inputs: Optional input data for the decision
        outputs: Optional output data from the decision
        confidence: Optional confidence score (0.0-1.0)
        workflow_id: Optional workflow UUID for correlation
        thread_id: Optional LangGraph thread ID for correlation
        sku_id: Optional SKU UUID for filtering
        sku: Optional SKU code for display
        timestamp: Optional timestamp (defaults to now)

    Returns:
        The created AgentAuditLog instance
    """
    entry = AgentAuditLog(
        workflow_id=workflow_id,
        thread_id=thread_id,
        timestamp=timestamp or datetime.now(UTC),
        agent=agent,
        action=action,
        reasoning=reasoning,
        inputs=inputs,
        outputs=outputs,
        confidence=confidence,
        sku_id=sku_id,
        sku=sku,
    )
    session.add(entry)
    await session.flush()
    return entry


async def log_audit_entries_from_state(
    session: AsyncSession,
    audit_log: list[dict[str, Any]],
    workflow_id: str | None = None,
    thread_id: str | None = None,
    sku_id: str | None = None,
    sku: str | None = None,
) -> list[AgentAuditLog]:
    """Sync audit log entries from workflow state to normalized storage.

    Converts the JSON-based audit log entries from the workflow state
    into normalized AgentAuditLog records in the database.

    Args:
        session: Database session
        audit_log: List of audit entry dictionaries from workflow state
        workflow_id: Optional workflow UUID for correlation
        thread_id: Optional LangGraph thread ID for correlation
        sku_id: Optional SKU UUID for filtering (overrides entry values)
        sku: Optional SKU code for display (overrides entry values)

    Returns:
        List of created AgentAuditLog instances
    """
    entries = []
    for entry_dict in audit_log:
        entry = AgentAuditLog.from_dict(
            entry_dict,
            workflow_id=workflow_id,
            thread_id=thread_id,
            sku_id=sku_id,
            sku=sku,
        )
        session.add(entry)
        entries.append(entry)

    await session.flush()
    return entries


async def get_audit_logs(
    session: AsyncSession,
    filters: AuditLogFilters | None = None,
    limit: int = 100,
    offset: int = 0,
    order_desc: bool = True,
) -> list[AgentAuditLog]:
    """Query audit logs with optional filters.

    Retrieves audit log entries matching the specified filters,
    ordered by timestamp (most recent first by default).

    Args:
        session: Database session
        filters: Optional filters to apply
        limit: Maximum number of results (default 100)
        offset: Number of results to skip (for pagination)
        order_desc: Order by timestamp descending (default True)

    Returns:
        List of matching AgentAuditLog entries
    """
    query = select(AgentAuditLog)

    if filters:
        if filters.workflow_id:
            query = query.where(AgentAuditLog.workflow_id == filters.workflow_id)
        if filters.thread_id:
            query = query.where(AgentAuditLog.thread_id == filters.thread_id)
        if filters.agent:
            query = query.where(AgentAuditLog.agent == filters.agent)
        if filters.action:
            query = query.where(AgentAuditLog.action == filters.action)
        if filters.sku_id:
            query = query.where(AgentAuditLog.sku_id == filters.sku_id)
        if filters.sku:
            query = query.where(AgentAuditLog.sku == filters.sku)
        if filters.min_confidence is not None:
            query = query.where(AgentAuditLog.confidence >= filters.min_confidence)
        if filters.max_confidence is not None:
            query = query.where(AgentAuditLog.confidence <= filters.max_confidence)
        if filters.start_time:
            query = query.where(AgentAuditLog.timestamp >= filters.start_time)
        if filters.end_time:
            query = query.where(AgentAuditLog.timestamp <= filters.end_time)

    if order_desc:
        query = query.order_by(desc(AgentAuditLog.timestamp))
    else:
        query = query.order_by(AgentAuditLog.timestamp)

    query = query.offset(offset).limit(limit)

    result = await session.execute(query)
    return list(result.scalars().all())


async def get_audit_log_by_id(
    session: AsyncSession,
    audit_id: str,
) -> AgentAuditLog | None:
    """Get a specific audit log entry by ID.

    Args:
        session: Database session
        audit_id: Audit log UUID

    Returns:
        The AgentAuditLog entry or None if not found
    """
    result = await session.execute(
        select(AgentAuditLog).where(AgentAuditLog.id == audit_id)
    )
    return result.scalar_one_or_none()


async def get_workflow_audit_trail(
    session: AsyncSession,
    workflow_id: str,
) -> list[AgentAuditLog]:
    """Get all audit entries for a specific workflow.

    Retrieves the complete audit trail for a workflow,
    ordered chronologically by timestamp.

    Args:
        session: Database session
        workflow_id: Workflow UUID

    Returns:
        List of AgentAuditLog entries for the workflow
    """
    return await get_audit_logs(
        session,
        filters=AuditLogFilters(workflow_id=workflow_id),
        limit=1000,  # Get all entries
        order_desc=False,  # Chronological order
    )


async def get_low_confidence_decisions(
    session: AsyncSession,
    threshold: float = 0.85,
    limit: int = 100,
    start_time: datetime | None = None,
) -> list[AgentAuditLog]:
    """Get audit entries with confidence below threshold.

    Useful for identifying decisions that may need human review.

    Args:
        session: Database session
        threshold: Confidence threshold (default 0.85)
        limit: Maximum number of results
        start_time: Optional start time filter

    Returns:
        List of low-confidence AgentAuditLog entries
    """
    return await get_audit_logs(
        session,
        filters=AuditLogFilters(
            max_confidence=threshold,
            start_time=start_time,
        ),
        limit=limit,
    )


async def get_audit_stats(
    session: AsyncSession,
    filters: AuditLogFilters | None = None,
) -> AuditLogStats:
    """Get aggregate statistics for audit logs.

    Computes counts and averages for audit log analysis.

    Args:
        session: Database session
        filters: Optional filters to apply

    Returns:
        AuditLogStats with aggregate statistics
    """
    # Build base query with filters
    base_filter = []
    if filters:
        if filters.workflow_id:
            base_filter.append(AgentAuditLog.workflow_id == filters.workflow_id)
        if filters.agent:
            base_filter.append(AgentAuditLog.agent == filters.agent)
        if filters.sku_id:
            base_filter.append(AgentAuditLog.sku_id == filters.sku_id)
        if filters.start_time:
            base_filter.append(AgentAuditLog.timestamp >= filters.start_time)
        if filters.end_time:
            base_filter.append(AgentAuditLog.timestamp <= filters.end_time)

    # Total count and average confidence
    total_query = select(
        func.count(AgentAuditLog.id),
        func.avg(AgentAuditLog.confidence),
        func.min(AgentAuditLog.timestamp),
        func.max(AgentAuditLog.timestamp),
    )
    if base_filter:
        total_query = total_query.where(*base_filter)
    total_result = await session.execute(total_query)
    total_row = total_result.one()
    total_entries = total_row[0] or 0
    avg_confidence = float(total_row[1]) if total_row[1] is not None else None
    earliest_entry = total_row[2]
    latest_entry = total_row[3]

    # Low confidence count
    low_conf_query = select(func.count(AgentAuditLog.id)).where(
        AgentAuditLog.confidence < 0.85
    )
    if base_filter:
        low_conf_query = low_conf_query.where(*base_filter)
    low_conf_result = await session.execute(low_conf_query)
    low_confidence_count = low_conf_result.scalar() or 0

    # Count by agent
    agent_query = select(
        AgentAuditLog.agent,
        func.count(AgentAuditLog.id),
    ).group_by(AgentAuditLog.agent)
    if base_filter:
        agent_query = agent_query.where(*base_filter)
    agent_result = await session.execute(agent_query)
    entries_by_agent = {row[0]: row[1] for row in agent_result}

    # Count by action
    action_query = select(
        AgentAuditLog.action,
        func.count(AgentAuditLog.id),
    ).group_by(AgentAuditLog.action)
    if base_filter:
        action_query = action_query.where(*base_filter)
    action_result = await session.execute(action_query)
    entries_by_action = {row[0]: row[1] for row in action_result}

    # Count by SKU
    sku_query = select(
        AgentAuditLog.sku,
        func.count(AgentAuditLog.id),
    ).where(AgentAuditLog.sku.isnot(None)).group_by(AgentAuditLog.sku)
    if base_filter:
        sku_query = sku_query.where(*base_filter)
    sku_result = await session.execute(sku_query)
    entries_by_sku = {row[0]: row[1] for row in sku_result}

    return AuditLogStats(
        total_entries=total_entries,
        entries_by_agent=entries_by_agent,
        entries_by_action=entries_by_action,
        avg_confidence=avg_confidence,
        low_confidence_count=low_confidence_count,
        entries_by_sku=entries_by_sku,
        earliest_entry=earliest_entry,
        latest_entry=latest_entry,
    )


async def count_audit_logs(
    session: AsyncSession,
    filters: AuditLogFilters | None = None,
) -> int:
    """Count audit log entries matching filters.

    Args:
        session: Database session
        filters: Optional filters to apply

    Returns:
        Number of matching entries
    """
    query = select(func.count(AgentAuditLog.id))

    if filters:
        if filters.workflow_id:
            query = query.where(AgentAuditLog.workflow_id == filters.workflow_id)
        if filters.thread_id:
            query = query.where(AgentAuditLog.thread_id == filters.thread_id)
        if filters.agent:
            query = query.where(AgentAuditLog.agent == filters.agent)
        if filters.action:
            query = query.where(AgentAuditLog.action == filters.action)
        if filters.sku_id:
            query = query.where(AgentAuditLog.sku_id == filters.sku_id)
        if filters.min_confidence is not None:
            query = query.where(AgentAuditLog.confidence >= filters.min_confidence)
        if filters.max_confidence is not None:
            query = query.where(AgentAuditLog.confidence <= filters.max_confidence)
        if filters.start_time:
            query = query.where(AgentAuditLog.timestamp >= filters.start_time)
        if filters.end_time:
            query = query.where(AgentAuditLog.timestamp <= filters.end_time)

    result = await session.execute(query)
    return result.scalar() or 0


async def delete_old_audit_logs(
    session: AsyncSession,
    older_than: datetime,
) -> int:
    """Delete audit logs older than specified date.

    Use for audit log retention/cleanup. Be careful with this
    as deleted audit logs cannot be recovered.

    Args:
        session: Database session
        older_than: Delete entries with timestamp before this date

    Returns:
        Number of deleted entries
    """
    result = await session.execute(
        delete(AgentAuditLog).where(AgentAuditLog.timestamp < older_than)
    )
    await session.commit()
    # CursorResult has rowcount attribute for DML statements
    return getattr(result, "rowcount", 0) or 0


async def get_agent_decision_summary(
    session: AsyncSession,
    agent: str,
    days: int = 30,
) -> dict[str, Any]:
    """Get a summary of decisions made by a specific agent.

    Useful for analyzing agent behavior over time.

    Args:
        session: Database session
        agent: Agent name to analyze
        days: Number of days to look back (default 30)

    Returns:
        Dictionary with summary statistics
    """
    start_time = datetime.now(UTC) - timedelta(days=days)

    filters = AuditLogFilters(
        agent=agent,
        start_time=start_time,
    )

    stats = await get_audit_stats(session, filters)

    return {
        "agent": agent,
        "period_days": days,
        "total_decisions": stats.total_entries,
        "actions": stats.entries_by_action,
        "avg_confidence": stats.avg_confidence,
        "low_confidence_count": stats.low_confidence_count,
        "affected_skus": stats.entries_by_sku,
    }
