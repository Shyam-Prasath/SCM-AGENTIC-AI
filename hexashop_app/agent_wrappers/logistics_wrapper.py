from __future__ import annotations
from agents.logistics_routing_agent import run_logistics_agent, build_shipping_plan, validate_mode


def run_logistics_node(query: str, limit=5, mode="balanced") -> dict:
    mode = validate_mode(mode)
    # First get structured data for guardrails/HIL.
    plan = build_shipping_plan(limit=limit, optimization_mode=mode)
    # Then ask the CrewAI logistics agent for a manager-friendly answer.
    text = str(run_logistics_agent(question=query, limit=limit, mode=mode))
    hil_required = int(plan.get("approval_required_count", 0)) > 0
    return {
        "text": text,
        "hil_required": hil_required,
        "reason": f"{plan.get('approval_required_count', 0)} shipment(s) require manager approval." if hil_required else "No logistics approval required.",
        "details": plan,
    }
