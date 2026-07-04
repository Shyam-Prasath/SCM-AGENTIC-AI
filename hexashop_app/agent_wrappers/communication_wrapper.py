from __future__ import annotations
from agents.communication_agent import run_communication_agent


def run_communication_node(query: str, order_id: str) -> dict:
    return run_communication_agent(order_id=order_id, query=query)
