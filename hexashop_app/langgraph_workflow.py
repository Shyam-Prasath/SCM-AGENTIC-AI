from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from state import SCMState
from guardrails import apply_input_guardrails
from hil import set_hil, apply_hil_decision
from logger_config import log_event

from agent_wrappers.demand_wrapper import run_demand_node
from agent_wrappers.inventory_wrapper import run_inventory_node
from agent_wrappers.procurement_wrapper import run_procurement_agent
from agent_wrappers.logistics_wrapper import run_logistics_node
from agent_wrappers.communication_wrapper import run_communication_node


ROUTE_TO_NODE = {
    "demand_forecast": "demand_forecast",
    "inventory_monitoring": "inventory_monitoring",
    "procurement": "procurement",
    "logistics": "logistics",
    "communication": "communication",
    "full_pipeline": "full_pipeline",
    "fallback": "fallback",
    "follow_up": "follow_up",
}


def supervisor_node(state: SCMState) -> SCMState:
    state = apply_input_guardrails(state)
    if state.get("needs_follow_up"):
        state["route"] = "follow_up"
    log_event("supervisor_route", {
        "query": state.get("query"),
        "route": state.get("route"),
        "sku": state.get("sku"),
        "order_id": state.get("order_id"),
        "mode": state.get("mode"),
        "limit": state.get("limit"),
        "follow_up": state.get("follow_up_question"),
    })
    return state


def route_decider(state: SCMState) -> str:
    return ROUTE_TO_NODE.get(state.get("route", "fallback"), "fallback")


def follow_up_node(state: SCMState) -> SCMState:
    state["final_response"] = state.get("follow_up_question") or "Please provide the missing information."
    return state


def fallback_node(state: SCMState) -> SCMState:
    state["final_response"] = (
        "I could not map this request to a supply-chain agent. Try asking about demand forecasting, "
        "inventory, procurement, logistics, customer communication, or full pipeline."
    )
    return state


def demand_forecast_node(state: SCMState) -> SCMState:
    result = run_demand_node(
        query=state["query"],
        sku=state["sku"],
        days=int(state.get("days") or 7),
    )
    state["forecast_result"] = result["text"]
    if result.get("hil_required"):
        state = set_hil(state, "demand_forecast", result.get("reason", "Forecast requires review."), result)
    log_event("agent_result", {"agent": "demand_forecast", "hil_required": state.get("hil_required"), "reason": state.get("hil_reason")})
    return state


def inventory_node(state: SCMState) -> SCMState:
    result = run_inventory_node(state["query"])
    state["inventory_result"] = result["text"]
    if result.get("hil_required"):
        state = set_hil(state, "inventory_monitoring", result.get("reason", "Inventory risk requires review."), result)
    log_event("agent_result", {"agent": "inventory_monitoring", "hil_required": state.get("hil_required"), "reason": state.get("hil_reason")})
    return state


def procurement_node(state: SCMState) -> SCMState:
    result = run_procurement_agent(
        query=state["query"],
        sku=state.get("sku"),
        quantity=state.get("quantity"),
    )
    state["procurement_result"] = result["text"]
    if result.get("hil_required"):
        state = set_hil(state, "procurement", result.get("reason", "Procurement requires manager approval."), result)
    log_event("agent_result", {"agent": "procurement", "hil_required": state.get("hil_required"), "reason": state.get("hil_reason")})
    return state


def logistics_node(state: SCMState) -> SCMState:
    result = run_logistics_node(
        query=state["query"],
        limit=state.get("limit", 5),
        mode=state.get("mode", "balanced"),
    )
    state["logistics_result"] = result["text"]
    if result.get("hil_required"):
        state = set_hil(state, "logistics", result.get("reason", "Logistics requires manager approval."), result)
    log_event("agent_result", {"agent": "logistics", "hil_required": state.get("hil_required"), "reason": state.get("hil_reason")})
    return state


def communication_node(state: SCMState) -> SCMState:
    result = run_communication_node(
        query=state["query"],
        order_id=state["order_id"],
    )
    state["communication_result"] = result["text"]
    if result.get("hil_required"):
        state = set_hil(state, "communication", result.get("reason", "Communication requires manager approval."), result)
    log_event("agent_result", {"agent": "communication", "hil_required": state.get("hil_required"), "reason": state.get("hil_reason")})
    return state


def full_pipeline_node(state: SCMState) -> SCMState:
    # Full pipeline is intentionally guarded: it can run partial sections if required inputs are missing.
    query = state["query"]

    if state.get("sku") and state.get("days"):
        forecast = run_demand_node(query=query, sku=state["sku"], days=int(state["days"]))
        state["forecast_result"] = forecast["text"]
        if forecast.get("hil_required") and not state.get("hil_required"):
            state = set_hil(state, "demand_forecast", forecast.get("reason", "Forecast requires review."), forecast)
    else:
        state["forecast_result"] = "Skipped: SKU and forecast days not provided."

    inventory = run_inventory_node("Show all low stock products below reorder level")
    state["inventory_result"] = inventory["text"]
    if inventory.get("hil_required") and not state.get("hil_required"):
        state = set_hil(state, "inventory_monitoring", inventory.get("reason", "Inventory critical shortage requires review."), inventory)

    procurement = run_procurement_agent(query="Create procurement plan for low stock items")
    state["procurement_result"] = procurement["text"]
    if procurement.get("hil_required") and not state.get("hil_required"):
        state = set_hil(state, "procurement", procurement.get("reason", "Procurement requires manager approval."), procurement)

    logistics = run_logistics_node(query="Create optimized fulfilment plan for pending orders", limit=state.get("limit", 5), mode=state.get("mode", "balanced"))
    state["logistics_result"] = logistics["text"]
    if logistics.get("hil_required") and not state.get("hil_required"):
        state = set_hil(state, "logistics", logistics.get("reason", "Logistics requires manager approval."), logistics)

    if state.get("order_id"):
        communication = run_communication_node(query="Create customer communication for full pipeline", order_id=state["order_id"])
        state["communication_result"] = communication["text"]
        if communication.get("hil_required") and not state.get("hil_required"):
            state = set_hil(state, "communication", communication.get("reason", "Communication requires manager approval."), communication)
    else:
        state["communication_result"] = "Skipped: Order ID not provided."

    log_event("agent_result", {"agent": "full_pipeline", "hil_required": state.get("hil_required"), "reason": state.get("hil_reason")})
    return state


def hil_gate_node(state: SCMState) -> SCMState:
    state = apply_hil_decision(state)
    if state.get("hil_required") and not state.get("hil_decision"):
        log_event("hil_required", {
            "agent": state.get("hil_agent"),
            "reason": state.get("hil_reason"),
            "query": state.get("query"),
        })
    elif state.get("hil_decision"):
        log_event("hil_decision", {
            "agent": state.get("hil_agent"),
            "decision": state.get("hil_decision"),
            "note": state.get("hil_decision_note"),
        })
    return state


def finalize_node(state: SCMState) -> SCMState:
    if state.get("final_response"):
        return state

    parts = []
    if state.get("hil_required") and not state.get("hil_decision"):
        parts.append("## Human-in-the-Loop Required")
        parts.append(f"**Agent:** {state.get('hil_agent')}\n\n**Reason:** {state.get('hil_reason')}\n")
        parts.append("Please approve, reject, or hold this action from the Streamlit approval panel.")

    labels = [
        ("forecast_result", "DEMAND FORECAST"),
        ("inventory_result", "INVENTORY STATUS"),
        ("procurement_result", "PROCUREMENT / PURCHASE ORDER"),
        ("logistics_result", "LOGISTICS PLAN"),
        ("communication_result", "CUSTOMER COMMUNICATION"),
    ]
    for key, label in labels:
        if state.get(key):
            parts.append(f"## {label}\n{state[key]}")

    if state.get("guardrail_notes"):
        parts.append("## Guardrail Notes\n" + "\n".join(f"- {note}" for note in state["guardrail_notes"]))
    if state.get("errors"):
        parts.append("## Errors\n" + "\n".join(f"- {err}" for err in state["errors"]))

    state["final_response"] = "\n\n".join(parts) if parts else "No result generated."
    log_event("final_response", {
        "route": state.get("route"),
        "hil_required": state.get("hil_required"),
        "final_response_preview": state["final_response"][:500],
    })
    return state


def build_graph():
    graph = StateGraph(SCMState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("follow_up", follow_up_node)
    graph.add_node("fallback", fallback_node)
    graph.add_node("demand_forecast", demand_forecast_node)
    graph.add_node("inventory_monitoring", inventory_node)
    graph.add_node("procurement", procurement_node)
    graph.add_node("logistics", logistics_node)
    graph.add_node("communication", communication_node)
    graph.add_node("full_pipeline", full_pipeline_node)
    graph.add_node("hil_gate", hil_gate_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges("supervisor", route_decider, ROUTE_TO_NODE)

    for node in ["demand_forecast", "inventory_monitoring", "procurement", "logistics", "communication", "full_pipeline"]:
        graph.add_edge(node, "hil_gate")

    graph.add_edge("hil_gate", "finalize")
    graph.add_edge("follow_up", END)
    graph.add_edge("fallback", END)
    graph.add_edge("finalize", END)

    return graph.compile()


app_graph = build_graph()
