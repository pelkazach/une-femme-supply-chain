"""LangGraph state machine for automated procurement workflows.

This module implements a multi-agent procurement workflow using LangGraph
that coordinates demand forecasting, inventory optimization, vendor analysis,
and purchase order generation with human-in-the-loop approval for high-value orders.

Key features:
- State-based workflow with persistent checkpointing (PostgreSQL)
- Human approval gates for orders >$10K
- Audit trail of all agent decisions
- Workflow interrupt/resume/rewind support
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Annotated, Any, Literal, TypedDict
from uuid import UUID

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ApprovalStatus(str, Enum):
    """Approval status for procurement orders."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_APPROVED = "auto_approved"


class WorkflowStatus(str, Enum):
    """Status of the procurement workflow."""

    INITIALIZED = "initialized"
    FORECASTING = "forecasting"
    OPTIMIZING = "optimizing"
    ANALYZING_VENDOR = "analyzing_vendor"
    AWAITING_APPROVAL = "awaiting_approval"
    GENERATING_PO = "generating_po"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class ForecastData:
    """Forecast data for a SKU.

    Attributes:
        week: Week number (1-26)
        date: Forecast date
        yhat: Point forecast
        yhat_lower: Lower bound (80% CI)
        yhat_upper: Upper bound (80% CI)
    """

    week: int
    date: datetime
    yhat: float
    yhat_lower: float
    yhat_upper: float


@dataclass(frozen=True)
class VendorInfo:
    """Vendor information for procurement.

    Attributes:
        vendor_id: Vendor UUID
        vendor_name: Vendor name
        unit_price: Price per unit
        lead_time_days: Lead time in days
        minimum_order_quantity: Minimum order quantity
        reliability_score: Vendor reliability (0-1)
    """

    vendor_id: UUID
    vendor_name: str
    unit_price: float
    lead_time_days: int
    minimum_order_quantity: int
    reliability_score: float


@dataclass
class AuditLogEntry:
    """Audit log entry for agent decisions.

    Attributes:
        timestamp: When the decision was made
        agent: Which agent made the decision
        action: What action was taken
        reasoning: Why the decision was made
        inputs: Input data for the decision
        outputs: Output data from the decision
        confidence: Confidence score (0-1) if applicable
    """

    timestamp: datetime
    agent: str
    action: str
    reasoning: str
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    confidence: float | None = None


def _add_messages(
    existing: list[AuditLogEntry], new: list[AuditLogEntry]
) -> list[AuditLogEntry]:
    """Reducer function to append audit log entries."""
    return existing + new


class ProcurementState(TypedDict, total=False):
    """State for the procurement workflow.

    This TypedDict defines all the state that flows through the procurement
    workflow graph. Each agent node can read and update this state.

    Attributes:
        sku_id: Product SKU UUID being procured
        sku: Product SKU code (e.g., "UFBub250")
        current_inventory: Current inventory level
        forecast: 26-week demand forecast
        forecast_confidence: Confidence score for the forecast
        safety_stock: Calculated safety stock level
        reorder_point: Inventory level that triggers reorder
        recommended_quantity: Recommended order quantity
        vendors: Available vendors for this SKU
        selected_vendor: Chosen vendor for the order
        order_value: Total order value (quantity * unit_price)
        approval_status: Current approval status
        approval_required_level: Required approval level (manager/executive)
        human_feedback: Feedback from human reviewer
        reviewer_id: ID of the human reviewer
        workflow_status: Current workflow status
        error_message: Error message if workflow failed
        created_at: Workflow creation timestamp
        updated_at: Last update timestamp
        audit_log: Audit trail of all agent decisions
    """

    # Input state
    sku_id: str
    sku: str
    current_inventory: int

    # Forecast state
    forecast: list[dict[str, Any]]
    forecast_confidence: float

    # Optimization state
    safety_stock: int
    reorder_point: int
    recommended_quantity: int

    # Vendor state
    vendors: list[dict[str, Any]]
    selected_vendor: dict[str, Any]
    order_value: float

    # Approval state
    approval_status: str
    approval_required_level: str
    human_feedback: str
    reviewer_id: str

    # Workflow state
    workflow_status: str
    error_message: str
    created_at: str
    updated_at: str

    # Audit trail (using Annotated for reducer support)
    audit_log: Annotated[list[dict[str, Any]], _add_messages]


# Approval thresholds from spec
APPROVAL_THRESHOLDS = {
    "auto_approve_max": 5000.0,  # <$5K with >85% confidence
    "manager_review_max": 10000.0,  # $5K-$10K any confidence
    "executive_review": 10000.0,  # >$10K any confidence
}

CONFIDENCE_THRESHOLDS = {
    "high": 0.85,  # Auto-approve eligible
    "medium": 0.60,  # Manager review
    "low": 0.60,  # Escalate
}


def demand_forecaster(state: ProcurementState) -> dict[str, Any]:
    """Generate demand forecast using Prophet (sync wrapper).

    This is a synchronous wrapper that returns placeholder data.
    For actual forecasting with database access, use demand_forecaster_async.

    Args:
        state: Current procurement state with sku_id

    Returns:
        Updated state with forecast data and confidence score
    """
    sku_id = state.get("sku_id", "")
    sku = state.get("sku", "")

    # Placeholder: In production, use demand_forecaster_async with a session
    forecast: list[dict[str, Any]] = []
    forecast_confidence = 0.85  # Placeholder confidence

    # Create audit log entry
    audit_entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "agent": "demand_forecaster",
        "action": "generate_forecast",
        "reasoning": f"Generated 26-week demand forecast for SKU {sku}",
        "inputs": {"sku_id": sku_id, "sku": sku},
        "outputs": {
            "forecast_periods": len(forecast),
            "forecast_confidence": forecast_confidence,
        },
        "confidence": forecast_confidence,
    }

    return {
        "forecast": forecast,
        "forecast_confidence": forecast_confidence,
        "workflow_status": WorkflowStatus.OPTIMIZING.value,
        "updated_at": datetime.now(UTC).isoformat(),
        "audit_log": [audit_entry],
    }


async def demand_forecaster_async(
    state: ProcurementState,
    session: AsyncSession,
) -> dict[str, Any]:
    """Generate demand forecast using Prophet (async with database).

    This agent node calls the Prophet forecasting service to generate
    a 26-week demand forecast for the specified SKU. It retrieves
    historical depletion data from the database and trains a Prophet
    model with wine industry holidays and multiplicative seasonality.

    Args:
        state: Current procurement state with sku_id
        session: Async database session for retrieving training data

    Returns:
        Updated state with forecast data and confidence score

    Note:
        - Requires minimum 2 years (104 weeks) of training data
        - Uses multiplicative seasonality for champagne's holiday spikes
        - Returns 80% confidence intervals by default
        - Confidence score is derived from model MAPE (1 - MAPE)
    """
    import uuid as uuid_module

    from src.services.forecast import (
        DEFAULT_FORECAST_WEEKS,
        MIN_TRAINING_DAYS,
        TARGET_MAPE,
        get_training_data,
        train_forecast_model_for_sku,
    )

    sku_id_str = state.get("sku_id", "")
    sku = state.get("sku", "")

    # Parse SKU ID as UUID
    try:
        sku_uuid = uuid_module.UUID(sku_id_str)
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid SKU ID format: {sku_id_str}: {e}")
        return _create_forecast_error_response(
            sku_id_str,
            sku,
            f"Invalid SKU ID format: {sku_id_str}",
        )

    # Check if we have enough training data
    try:
        training_df = await get_training_data(session, sku_uuid)
        training_data_days = len(training_df)

        if training_data_days < MIN_TRAINING_DAYS:
            logger.warning(
                f"Insufficient training data for SKU {sku}: "
                f"{training_data_days} days, need {MIN_TRAINING_DAYS}"
            )
            return _create_insufficient_data_response(
                sku_id_str,
                sku,
                training_data_days,
                MIN_TRAINING_DAYS,
            )
    except Exception as e:
        logger.error(f"Error fetching training data for SKU {sku}: {e}")
        return _create_forecast_error_response(
            sku_id_str,
            sku,
            f"Error fetching training data: {e}",
        )

    # Train model and generate forecast
    try:
        model, forecast_result, performance = await train_forecast_model_for_sku(
            session=session,
            sku_id=sku_uuid,
            validate=True,
        )

        # Convert forecast points to dict format for state
        forecast_list = [
            {
                "week": i + 1,
                "date": fp.ds.isoformat(),
                "yhat": fp.yhat,
                "yhat_lower": fp.yhat_lower,
                "yhat_upper": fp.yhat_upper,
            }
            for i, fp in enumerate(forecast_result.forecasts)
        ]

        # Calculate confidence score from model performance
        # Confidence = 1 - MAPE, bounded between 0 and 1
        if performance is not None:
            # MAPE is typically 0-1 (0% to 100%), so 1 - MAPE gives confidence
            # If MAPE > 1, model is very poor, so clamp confidence to 0
            mape = min(performance.mape, 1.0)
            forecast_confidence = max(0.0, 1.0 - mape)

            # Adjust confidence if MAPE exceeds target
            if performance.mape > TARGET_MAPE:
                logger.warning(
                    f"Model MAPE ({performance.mape:.2%}) exceeds target "
                    f"({TARGET_MAPE:.0%}) for SKU {sku}"
                )
        else:
            # No validation performed, use conservative estimate
            forecast_confidence = 0.75

        reasoning = (
            f"Generated {DEFAULT_FORECAST_WEEKS}-week demand forecast for SKU {sku}. "
            f"Training data: {forecast_result.training_data_points} days "
            f"({forecast_result.training_data_start} to {forecast_result.training_data_end}). "
        )

        if performance is not None:
            reasoning += (
                f"Model MAPE: {performance.mape:.2%}, RMSE: {performance.rmse:.1f}. "
            )

        reasoning += f"Forecast confidence: {forecast_confidence:.0%}."

        audit_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "agent": "demand_forecaster",
            "action": "generate_forecast",
            "reasoning": reasoning,
            "inputs": {
                "sku_id": sku_id_str,
                "sku": sku,
                "training_data_days": forecast_result.training_data_points,
            },
            "outputs": {
                "forecast_periods": len(forecast_list),
                "forecast_confidence": forecast_confidence,
                "mape": performance.mape if performance else None,
                "rmse": performance.rmse if performance else None,
            },
            "confidence": forecast_confidence,
        }

        return {
            "forecast": forecast_list,
            "forecast_confidence": forecast_confidence,
            "workflow_status": WorkflowStatus.OPTIMIZING.value,
            "updated_at": datetime.now(UTC).isoformat(),
            "audit_log": [audit_entry],
        }

    except ValueError as e:
        # Insufficient training data or other validation error
        logger.error(f"Forecast validation error for SKU {sku}: {e}")
        return _create_forecast_error_response(sku_id_str, sku, str(e))

    except Exception as e:
        logger.error(f"Forecast generation failed for SKU {sku}: {e}")
        return _create_forecast_error_response(
            sku_id_str,
            sku,
            f"Forecast generation failed: {e}",
        )


def _create_forecast_error_response(
    sku_id: str,
    sku: str,
    error_message: str,
) -> dict[str, Any]:
    """Create an error response for failed forecast generation.

    Args:
        sku_id: SKU UUID string
        sku: SKU code
        error_message: Description of the error

    Returns:
        State update dict with error information
    """
    audit_entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "agent": "demand_forecaster",
        "action": "forecast_error",
        "reasoning": f"Forecast generation failed for SKU {sku}: {error_message}",
        "inputs": {"sku_id": sku_id, "sku": sku},
        "outputs": {"error": error_message},
        "confidence": 0.0,
    }

    return {
        "forecast": [],
        "forecast_confidence": 0.0,
        "workflow_status": WorkflowStatus.FAILED.value,
        "error_message": error_message,
        "updated_at": datetime.now(UTC).isoformat(),
        "audit_log": [audit_entry],
    }


def _create_insufficient_data_response(
    sku_id: str,
    sku: str,
    available_days: int,
    required_days: int,
) -> dict[str, Any]:
    """Create a response for insufficient training data.

    This returns a low-confidence state that allows the workflow
    to continue with human review rather than failing outright.

    Args:
        sku_id: SKU UUID string
        sku: SKU code
        available_days: Number of training data days available
        required_days: Minimum required training data days

    Returns:
        State update dict with low confidence (triggers human review)
    """
    # Calculate a proportional confidence based on available data
    # More data = higher confidence, capped at 0.60 (below high threshold)
    data_ratio = available_days / required_days
    forecast_confidence = min(0.60, data_ratio * 0.60)

    reasoning = (
        f"Insufficient training data for SKU {sku}. "
        f"Available: {available_days} days, required: {required_days} days. "
        f"Proceeding with low confidence ({forecast_confidence:.0%}) to trigger human review."
    )

    audit_entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "agent": "demand_forecaster",
        "action": "insufficient_data",
        "reasoning": reasoning,
        "inputs": {
            "sku_id": sku_id,
            "sku": sku,
            "available_days": available_days,
            "required_days": required_days,
        },
        "outputs": {
            "forecast_periods": 0,
            "forecast_confidence": forecast_confidence,
            "data_ratio": data_ratio,
        },
        "confidence": forecast_confidence,
    }

    return {
        "forecast": [],
        "forecast_confidence": forecast_confidence,
        "workflow_status": WorkflowStatus.OPTIMIZING.value,
        "updated_at": datetime.now(UTC).isoformat(),
        "audit_log": [audit_entry],
    }


def inventory_optimizer(state: ProcurementState) -> dict[str, Any]:
    """Calculate reorder quantity and safety stock.

    This agent analyzes the forecast and current inventory to determine
    the optimal reorder quantity and safety stock level.

    Args:
        state: Current procurement state with forecast and inventory data

    Returns:
        Updated state with safety_stock, reorder_point, and recommended_quantity
    """
    current_inventory = state.get("current_inventory", 0)
    forecast = state.get("forecast", [])
    forecast_confidence = state.get("forecast_confidence", 0.85)
    sku = state.get("sku", "")

    # Placeholder: Calculate safety stock based on forecast variability
    # safety_stock = calculate_safety_stock(forecast_df, service_level=0.95)
    safety_stock = 100  # Placeholder

    # Placeholder: Calculate reorder point
    # reorder_point = average_daily_demand * lead_time + safety_stock
    reorder_point = 200  # Placeholder

    # Placeholder: Calculate recommended quantity
    # Based on EOQ or weeks of supply model
    recommended_quantity = 500  # Placeholder

    reasoning = (
        f"Calculated safety stock of {safety_stock} units and "
        f"recommended order of {recommended_quantity} units for SKU {sku}. "
        f"Current inventory: {current_inventory}, reorder point: {reorder_point}."
    )

    audit_entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "agent": "inventory_optimizer",
        "action": "calculate_reorder",
        "reasoning": reasoning,
        "inputs": {
            "current_inventory": current_inventory,
            "forecast_periods": len(forecast),
            "forecast_confidence": forecast_confidence,
        },
        "outputs": {
            "safety_stock": safety_stock,
            "reorder_point": reorder_point,
            "recommended_quantity": recommended_quantity,
        },
        "confidence": forecast_confidence,
    }

    return {
        "safety_stock": safety_stock,
        "reorder_point": reorder_point,
        "recommended_quantity": recommended_quantity,
        "workflow_status": WorkflowStatus.ANALYZING_VENDOR.value,
        "updated_at": datetime.now(UTC).isoformat(),
        "audit_log": [audit_entry],
    }


def vendor_analyzer(state: ProcurementState) -> dict[str, Any]:
    """Evaluate and select optimal vendor.

    This agent analyzes available vendors and selects the optimal one
    based on price, lead time, reliability, and minimum order quantity.

    Args:
        state: Current procurement state with recommended_quantity

    Returns:
        Updated state with selected_vendor and order_value
    """
    recommended_quantity = state.get("recommended_quantity", 0)
    sku = state.get("sku", "")

    # Placeholder: Fetch vendors from database
    # vendors = await get_vendors_for_sku(session, sku_id)
    vendors: list[dict[str, Any]] = [
        {
            "vendor_id": "vendor-1",
            "vendor_name": "Primary Supplier",
            "unit_price": 25.00,
            "lead_time_days": 14,
            "minimum_order_quantity": 100,
            "reliability_score": 0.95,
        }
    ]

    # Placeholder: Select optimal vendor
    # selected = select_optimal_vendor(vendors, recommended_quantity)
    selected_vendor = vendors[0] if vendors else {}

    # Calculate order value
    unit_price = selected_vendor.get("unit_price", 0.0)
    order_value = unit_price * recommended_quantity

    reasoning = (
        f"Selected vendor '{selected_vendor.get('vendor_name', 'N/A')}' for SKU {sku}. "
        f"Order value: ${order_value:,.2f} ({recommended_quantity} units @ ${unit_price}/unit). "
        f"Lead time: {selected_vendor.get('lead_time_days', 0)} days, "
        f"reliability: {selected_vendor.get('reliability_score', 0):.0%}."
    )

    audit_entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "agent": "vendor_analyzer",
        "action": "select_vendor",
        "reasoning": reasoning,
        "inputs": {
            "recommended_quantity": recommended_quantity,
            "vendors_evaluated": len(vendors),
        },
        "outputs": {
            "selected_vendor": selected_vendor.get("vendor_name"),
            "unit_price": unit_price,
            "order_value": order_value,
        },
        "confidence": selected_vendor.get("reliability_score", 0.0),
    }

    return {
        "vendors": vendors,
        "selected_vendor": selected_vendor,
        "order_value": order_value,
        "workflow_status": WorkflowStatus.AWAITING_APPROVAL.value,
        "updated_at": datetime.now(UTC).isoformat(),
        "audit_log": [audit_entry],
    }


def human_approval(state: ProcurementState) -> dict[str, Any]:
    """Human review node - execution pauses here.

    This node is an interrupt point where the workflow pauses for
    human review and approval. The workflow resumes when the human
    provides feedback via the workflow API.

    Args:
        state: Current procurement state

    Returns:
        State with approval status updated
    """
    order_value = state.get("order_value", 0.0)
    sku = state.get("sku", "")
    forecast_confidence = state.get("forecast_confidence", 0.0)

    # Determine required approval level
    if order_value > APPROVAL_THRESHOLDS["executive_review"]:
        approval_level = "executive"
    elif (
        order_value > APPROVAL_THRESHOLDS["auto_approve_max"]
        or forecast_confidence < CONFIDENCE_THRESHOLDS["high"]
    ):
        approval_level = "manager"
    else:
        approval_level = "auto"

    reasoning = (
        f"Order for SKU {sku} requires {approval_level} approval. "
        f"Order value: ${order_value:,.2f}, forecast confidence: {forecast_confidence:.0%}."
    )

    audit_entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "agent": "human_approval",
        "action": "request_approval",
        "reasoning": reasoning,
        "inputs": {
            "order_value": order_value,
            "forecast_confidence": forecast_confidence,
        },
        "outputs": {
            "approval_required_level": approval_level,
            "approval_status": ApprovalStatus.PENDING.value,
        },
        "confidence": None,
    }

    return {
        "approval_status": ApprovalStatus.PENDING.value,
        "approval_required_level": approval_level,
        "updated_at": datetime.now(UTC).isoformat(),
        "audit_log": [audit_entry],
    }


def generate_purchase_order(state: ProcurementState) -> dict[str, Any]:
    """Generate the purchase order.

    This agent creates the final purchase order after approval
    has been granted (either automatic or human).

    Args:
        state: Current procurement state with all required data

    Returns:
        Updated state with completed workflow status
    """
    sku = state.get("sku", "")
    recommended_quantity = state.get("recommended_quantity", 0)
    selected_vendor = state.get("selected_vendor", {})
    order_value = state.get("order_value", 0.0)
    approval_status = state.get("approval_status", "")

    # Placeholder: Create purchase order in system
    # po_id = await create_purchase_order(session, state)

    reasoning = (
        f"Generated purchase order for SKU {sku}. "
        f"Quantity: {recommended_quantity} units, "
        f"Vendor: {selected_vendor.get('vendor_name', 'N/A')}, "
        f"Total: ${order_value:,.2f}. "
        f"Approval status: {approval_status}."
    )

    audit_entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "agent": "generate_po",
        "action": "create_purchase_order",
        "reasoning": reasoning,
        "inputs": {
            "sku": sku,
            "quantity": recommended_quantity,
            "vendor": selected_vendor.get("vendor_name"),
            "order_value": order_value,
        },
        "outputs": {
            "workflow_status": WorkflowStatus.COMPLETED.value,
        },
        "confidence": None,
    }

    return {
        "workflow_status": WorkflowStatus.COMPLETED.value,
        "updated_at": datetime.now(UTC).isoformat(),
        "audit_log": [audit_entry],
    }


def should_require_approval(state: ProcurementState) -> Literal["human_approval", "generate_po"]:
    """Route based on order value and confidence.

    This conditional edge function determines whether the order
    requires human approval or can be auto-approved.

    Approval rules from spec:
    - <$5K with >85% confidence: Auto-approve
    - <$5K with 60-85% confidence: Manager review
    - $5K-$10K any confidence: Manager review
    - >$10K any confidence: Executive review

    Args:
        state: Current procurement state

    Returns:
        Next node name: "human_approval" or "generate_po"
    """
    order_value = state.get("order_value", 0.0)
    forecast_confidence = state.get("forecast_confidence", 0.0)

    # Orders >$10K always require approval
    if order_value > APPROVAL_THRESHOLDS["executive_review"]:
        return "human_approval"

    # Orders $5K-$10K require manager review
    if order_value > APPROVAL_THRESHOLDS["auto_approve_max"]:
        return "human_approval"

    # Orders <$5K but low confidence require review
    if forecast_confidence < CONFIDENCE_THRESHOLDS["high"]:
        return "human_approval"

    # Auto-approve: <$5K with >85% confidence
    return "generate_po"


def build_procurement_workflow() -> StateGraph:
    """Build the procurement workflow state graph.

    Creates a LangGraph StateGraph with the following nodes:
    - run_forecast: Demand forecasting agent
    - run_optimize: Inventory optimization agent
    - run_vendor_analysis: Vendor analysis agent
    - run_approval: Human review interrupt node
    - run_po_generation: Purchase order generation agent

    Node names are prefixed with 'run_' to avoid conflicts with state keys.

    Returns:
        Configured StateGraph ready for compilation
    """
    # Create the state graph
    workflow = StateGraph(ProcurementState)

    # Add nodes (prefixed with 'run_' to avoid state key conflicts)
    workflow.add_node("run_forecast", demand_forecaster)
    workflow.add_node("run_optimize", inventory_optimizer)
    workflow.add_node("run_vendor_analysis", vendor_analyzer)
    workflow.add_node("run_approval", human_approval)
    workflow.add_node("run_po_generation", generate_purchase_order)

    # Set entry point
    workflow.set_entry_point("run_forecast")

    # Add edges
    workflow.add_edge("run_forecast", "run_optimize")
    workflow.add_edge("run_optimize", "run_vendor_analysis")

    # Conditional edge for approval routing
    workflow.add_conditional_edges(
        "run_vendor_analysis",
        should_require_approval,
        {
            "human_approval": "run_approval",
            "generate_po": "run_po_generation",
        },
    )

    # Human approval leads to PO generation
    workflow.add_edge("run_approval", "run_po_generation")

    # PO generation ends the workflow
    workflow.add_edge("run_po_generation", END)

    return workflow


def compile_workflow(
    checkpointer: Any | None = None,
    interrupt_before: list[str] | None = None,
) -> CompiledStateGraph:
    """Compile the procurement workflow with optional checkpointing.

    Args:
        checkpointer: Optional checkpointer for state persistence
            (e.g., PostgresSaver for production)
        interrupt_before: List of nodes to interrupt before
            (default: ["run_approval"] for HITL)

    Returns:
        Compiled workflow graph ready for execution
    """
    workflow = build_procurement_workflow()

    # Default interrupt points for human-in-the-loop
    if interrupt_before is None:
        interrupt_before = ["run_approval"]

    # Compile with checkpointing if provided
    if checkpointer is not None:
        return workflow.compile(
            checkpointer=checkpointer,
            interrupt_before=interrupt_before,
        )

    # Compile without checkpointing (for testing)
    return workflow.compile(interrupt_before=interrupt_before)


def create_initial_state(
    sku_id: str,
    sku: str,
    current_inventory: int,
) -> ProcurementState:
    """Create initial state for a new procurement workflow.

    Args:
        sku_id: Product SKU UUID
        sku: Product SKU code (e.g., "UFBub250")
        current_inventory: Current inventory level

    Returns:
        Initial ProcurementState for workflow execution
    """
    now = datetime.now(UTC).isoformat()

    return ProcurementState(
        sku_id=sku_id,
        sku=sku,
        current_inventory=current_inventory,
        forecast=[],
        forecast_confidence=0.0,
        safety_stock=0,
        reorder_point=0,
        recommended_quantity=0,
        vendors=[],
        selected_vendor={},
        order_value=0.0,
        approval_status=ApprovalStatus.PENDING.value,
        approval_required_level="",
        human_feedback="",
        reviewer_id="",
        workflow_status=WorkflowStatus.INITIALIZED.value,
        error_message="",
        created_at=now,
        updated_at=now,
        audit_log=[],
    )
