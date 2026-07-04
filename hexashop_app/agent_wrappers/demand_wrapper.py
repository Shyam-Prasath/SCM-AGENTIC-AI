from __future__ import annotations
from agents.demand_forecast_agent import run_forecast_agent, analyze_forecast_risk


def run_demand_node(query: str, sku: str, days: int) -> dict:
    risk = analyze_forecast_risk(sku=sku, days=days)
    text = run_forecast_agent(query=query, sku=sku, days=days)
    return {"text": text, **risk}
