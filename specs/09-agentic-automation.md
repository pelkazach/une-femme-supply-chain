# Spec: Agentic Procurement Automation

## Job to Be Done
As a supply chain manager, I need AI agents to analyze demand, optimize inventory, and generate procurement recommendations with human oversight so that reorder decisions are data-driven while maintaining control over significant purchases.

## Requirements
- Implement LangGraph state machine for agent orchestration
- Create demand forecaster agent (Prophet-based)
- Create inventory optimizer agent (safety stock, reorder points)
- Create vendor analyzer agent (lead times, pricing)
- Implement orchestrator agent to coordinate workflows
- Add human-in-the-loop approval gates for high-value decisions
- Support workflow interrupt/resume/rewind
- Maintain complete audit trail of agent decisions

## Acceptance Criteria
- [ ] LangGraph state machine deployed and operational
- [ ] Demand forecaster agent generates 26-week forecasts
- [ ] Inventory optimizer recommends reorder quantities
- [ ] Vendor analyzer evaluates supplier options
- [ ] Orchestrator coordinates multi-agent workflows
- [ ] Orders >$10K trigger human approval gate
- [ ] Workflow can be paused and resumed
- [ ] All agent decisions logged with reasoning

## Test Cases
| Input | Expected Output |
|-------|-----------------|
| Low DOH_T30 for UFBub250 | Reorder recommendation generated |
| Forecast shows NYE spike | Safety stock increase recommended |
| Order value $15K | Routed to human approval queue |
| Multiple vendors available | Recommendation with vendor comparison |
| Agent makes error | Workflow rewound, corrected |

## Technical Notes
- LangGraph: Native human-in-the-loop with interrupt nodes
- Confidence routing: >85% auto-approve, 60-85% human review, <60% escalate
- Memory: Conversation history + entity memory for context
- State persistence: PostgreSQL-backed for durability
- Checkpointing enables rollback to any previous state

## Agent Architecture

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from typing import TypedDict, Annotated, Literal

class ProcurementState(TypedDict):
    sku_id: str
    current_inventory: int
    forecast: list[dict]
    safety_stock: int
    recommended_quantity: int
    selected_vendor: dict
    order_value: float
    approval_status: Literal["pending", "approved", "rejected"]
    human_feedback: str

# Define agents as graph nodes
def demand_forecaster(state: ProcurementState) -> ProcurementState:
    """Generate demand forecast using Prophet"""
    forecast = prophet_forecast(state["sku_id"], periods=26)
    return {"forecast": forecast}

def inventory_optimizer(state: ProcurementState) -> ProcurementState:
    """Calculate reorder quantity and safety stock"""
    safety = calculate_safety_stock(state["forecast"])
    quantity = calculate_reorder_quantity(
        state["current_inventory"],
        state["forecast"],
        safety
    )
    return {"safety_stock": safety, "recommended_quantity": quantity}

def vendor_analyzer(state: ProcurementState) -> ProcurementState:
    """Evaluate and select optimal vendor"""
    vendors = get_vendors(state["sku_id"])
    selected = select_optimal_vendor(vendors, state["recommended_quantity"])
    order_value = selected["unit_price"] * state["recommended_quantity"]
    return {"selected_vendor": selected, "order_value": order_value}

def human_approval(state: ProcurementState) -> ProcurementState:
    """Human review node - execution pauses here"""
    # LangGraph interrupt - waits for human input
    return state

def should_require_approval(state: ProcurementState) -> str:
    """Route based on order value"""
    if state["order_value"] > 10000:
        return "human_approval"
    return "generate_po"

# Build the graph
workflow = StateGraph(ProcurementState)
workflow.add_node("forecast", demand_forecaster)
workflow.add_node("optimize", inventory_optimizer)
workflow.add_node("analyze_vendor", vendor_analyzer)
workflow.add_node("human_approval", human_approval)
workflow.add_node("generate_po", generate_purchase_order)

workflow.add_edge("forecast", "optimize")
workflow.add_edge("optimize", "analyze_vendor")
workflow.add_conditional_edges(
    "analyze_vendor",
    should_require_approval,
    {"human_approval": "human_approval", "generate_po": "generate_po"}
)
workflow.add_edge("human_approval", "generate_po")
workflow.add_edge("generate_po", END)

# Compile with checkpointing
checkpointer = PostgresSaver(conn_string)
app = workflow.compile(checkpointer=checkpointer)
```

## Approval Workflow

| Order Value | Confidence | Action |
|-------------|------------|--------|
| <$5K | >85% | Auto-approve |
| <$5K | 60-85% | Manager review |
| $5K-$10K | Any | Manager review |
| >$10K | Any | Executive review |

## Source Reference
- [[langgraph-agents]] - LangGraph state machine patterns
- [[hitl-patterns]] - Human-in-the-loop implementation
- [[agent-memory]] - Memory and context management
