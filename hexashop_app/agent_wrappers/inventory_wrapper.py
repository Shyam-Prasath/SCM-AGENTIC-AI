from __future__ import annotations
from agents.inventory_monitoring_agent import run_inventory_agent, inventory_risk_metadata


def run_inventory_node(query: str) -> dict:
    text = run_inventory_agent(query)
    risk = inventory_risk_metadata(query)
    return {"text": text, **risk}
