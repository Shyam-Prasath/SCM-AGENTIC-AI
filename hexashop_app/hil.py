from __future__ import annotations


def set_hil(state: dict, agent: str, reason: str, payload: dict | None = None) -> dict:
    state["hil_required"] = True
    state["hil_agent"] = agent
    state["hil_reason"] = reason
    state["hil_payload"] = payload or {}
    return state


def apply_hil_decision(state: dict) -> dict:
    if not state.get("hil_required"):
        return state

    decision = (state.get("hil_decision") or "").upper().strip()
    if not decision:
        return state

    note = state.get("hil_decision_note") or ""
    decision_text = f"\n\nHuman-in-the-Loop Decision: {decision}"
    if note:
        decision_text += f"\nManager Note: {note}"

    agent = state.get("hil_agent")
    if agent == "demand_forecast" and state.get("forecast_result"):
        state["forecast_result"] += decision_text
    elif agent == "inventory_monitoring" and state.get("inventory_result"):
        state["inventory_result"] += decision_text
    elif agent == "procurement" and state.get("procurement_result"):
        state["procurement_result"] += decision_text
    elif agent == "logistics" and state.get("logistics_result"):
        state["logistics_result"] += decision_text
    elif agent == "communication" and state.get("communication_result"):
        state["communication_result"] += decision_text

    state["hil_required"] = False
    return state
