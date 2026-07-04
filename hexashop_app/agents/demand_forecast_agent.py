from __future__ import annotations

import os
import pandas as pd
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool

load_dotenv()

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
SALES_PATH = os.path.join(DATA_DIR, "sales_history.csv")
INVENTORY_PATH = os.path.join(DATA_DIR, "inventory.csv")

sales_df = pd.read_csv(SALES_PATH)
inventory_df = pd.read_csv(INVENTORY_PATH)

gpt_llm = LLM(
    model=f"azure/{os.getenv('AZURE_OPENAI_DEPLOYMENT')}",
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
    temperature=0.2,
)


def _forecast_model_logic(sku: str, days: int) -> dict:
    sku = str(sku).strip().upper()
    days = int(days)
    sku_sales = sales_df[sales_df["sku"].astype(str).str.upper() == sku]
    if sku_sales.empty:
        return {"error": "SKU not found", "sku": sku}
    last_7_days = sku_sales.tail(7)
    avg_daily_sales = float(last_7_days["units_sold"].mean())
    predicted_demand = round(avg_daily_sales * days)
    return {
        "sku": sku,
        "forecast_days": days,
        "avg_daily_sales": round(avg_daily_sales, 2),
        "predicted_demand": int(predicted_demand),
    }


def _inventory_lookup_logic(sku: str) -> dict:
    sku = str(sku).strip().upper()
    item = inventory_df[inventory_df["sku"].astype(str).str.upper() == sku]
    if item.empty:
        return {"error": "SKU not found", "sku": sku}
    on_hand = int(item["on_hand"].sum())
    reorder_point = int(item["reorder_point"].max())
    reorder_qty = int(item["reorder_qty"].max())
    warehouses = ", ".join(sorted(item["warehouse"].astype(str).unique()))
    if on_hand < reorder_point:
        risk = "Stock-Out Risk"
    elif on_hand > reorder_qty:
        risk = "Overstock Risk"
    else:
        risk = "Normal"
    return {
        "sku": sku,
        "warehouses": warehouses,
        "on_hand": on_hand,
        "reorder_point": reorder_point,
        "reorder_qty": reorder_qty,
        "risk": risk,
    }


@tool
def forecast_model(sku: str, days: int) -> dict:
    """Predict near-term demand for a SKU using the last 7 days of sales history."""
    return _forecast_model_logic(sku, days)


@tool
def inventory_db_lookup(sku: str) -> dict:
    """Retrieve inventory information for a SKU and identify stock-out or overstock risk."""
    return _inventory_lookup_logic(sku)


forecasting_agent = Agent(
    role="Demand Forecasting Analyst",
    goal="Predict near-term demand per SKU from sales history and identify stock-out or overstock risk.",
    backstory=(
        "You are a senior demand forecasting analyst at HexaShop. You analyze historical sales, forecast demand, "
        "compare it with inventory, and recommend replenishment actions. Always use forecast_model and "
        "inventory_db_lookup. Never fabricate values."
    ),
    tools=[forecast_model, inventory_db_lookup],
    llm=gpt_llm,
    verbose=True,
    allow_delegation=False,
)


def run_forecast_agent(query: str, sku: str, days: int = 7) -> str:
    task = Task(
        description=f"""
        Forecast demand for SKU {sku} for {days} days.

        Manager question:
        {query}

        Rules:
        - Use forecast_model.
        - Use inventory_db_lookup.
        - Compare predicted demand with current inventory.
        - Mention stock-out or overstock risk.
        - Do not invent values.
        """,
        expected_output="Forecast demand, inventory comparison, risk level, and recommendation.",
        agent=forecasting_agent,
    )
    crew = Crew(agents=[forecasting_agent], tasks=[task], verbose=True)
    return str(crew.kickoff())


def analyze_forecast_risk(sku: str, days: int = 7) -> dict:
    """Deterministic risk metadata for LangGraph guardrails and HIL."""
    forecast = _forecast_model_logic(sku=sku, days=days)
    inventory = _inventory_lookup_logic(sku=sku)
    if "error" in forecast or "error" in inventory:
        return {"hil_required": False, "reason": "Data unavailable", "forecast": forecast, "inventory": inventory}

    predicted = int(forecast["predicted_demand"])
    on_hand = int(inventory["on_hand"])
    reorder_qty = int(inventory["reorder_qty"])
    multiplier = float(os.getenv("HIGH_FORECAST_MULTIPLIER", "1.5"))

    hil_required = False
    reasons = []
    if predicted > on_hand:
        hil_required = True
        reasons.append("Predicted demand exceeds available inventory.")
    if inventory["risk"] == "Stock-Out Risk":
        hil_required = True
        reasons.append("SKU is already in stock-out risk.")
    if predicted > reorder_qty * multiplier:
        hil_required = True
        reasons.append("Unusually high forecast demand detected.")

    return {
        "hil_required": hil_required,
        "reason": "; ".join(reasons) if reasons else "No high-risk forecast condition.",
        "forecast": forecast,
        "inventory": inventory,
    }
