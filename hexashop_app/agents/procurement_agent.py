"""
Procurement & Supplier Management Agent
"""

# =====================================================
# IMPORTS
# =====================================================

import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from crewai import Agent, LLM
from crewai.tools import BaseTool


# =====================================================
# LOAD ENVIRONMENT VARIABLES
# =====================================================

load_dotenv(override=True)


# =====================================================
# PROCUREMENT PROMPT
# =====================================================

PROCUREMENT_PROMPT = """
You are an intelligent Procurement & Supplier Management Agent for HexaShop.

Responsibilities:
1. Receive procurement requests from inventory and forecasting agents.
2. Analyze SKU and required reorder quantity.
3. Identify eligible suppliers capable of fulfilling the request.
4. Compare suppliers using unit cost, available quantity, lead time, reliability score, and on-time delivery rate.
5. Select the best supplier based on overall business value.
6. Calculate total procurement cost.
7. Determine whether managerial approval is required.
8. Generate a structured Purchase Order.
9. Return the final procurement decision.

Rules:
- Never select a supplier that cannot fulfill the requested quantity.
- Prefer lower unit cost, higher reliability, better on-time rate, and shorter lead time.
- Never invent supplier information.
- Use only available tool outputs.
- If PO value is within the approval threshold, approve automatically.
- If PO value exceeds the threshold, mark it as PENDING_HUMAN_APPROVAL.

Output format:
- Purchase Order ID
- SKU
- Supplier ID
- Supplier Name
- Quantity
- Unit Cost
- Total Cost
- Lead Time
- Approval Status
- Approval Reason if any
"""


# =====================================================
# SUPPLIER TOOL
# =====================================================

CATALOG_PATH = Path("data") / "supplier_catalog.json"
SUPPLIER_PATH = Path("data") / "suppliers.csv"


class SupplierTool(BaseTool):
    name: str = "Supplier Tool"
    description: str = (
        "Finds the best supplier for a SKU and required quantity based on cost, "
        "available quantity, reliability, on-time delivery, and lead time."
    )

    def _run(self, sku: str, quantity: int) -> dict:
        sku = str(sku).strip().upper()
        quantity = int(quantity)

        with open(CATALOG_PATH, "r", encoding="utf-8") as file:
            catalog = json.load(file)

        suppliers = pd.read_csv(SUPPLIER_PATH)

        matching_suppliers = [
            item for item in catalog
            if str(item.get("sku", "")).upper() == sku
            and int(item.get("available_qty", 0)) >= quantity
        ]

        if not matching_suppliers:
            return {
                "status": "FAILED",
                "message": "No supplier found with sufficient stock.",
                "sku": sku,
                "quantity": quantity,
            }

        catalog_df = pd.DataFrame(matching_suppliers)
        merged_df = catalog_df.merge(suppliers, on="supplier_id", how="inner")

        # Best business value: sufficient stock first, then low cost,
        # higher reliability, better on-time rate, and shorter lead time.
        merged_df = merged_df.sort_values(
            by=["unit_cost", "reliability_score", "on_time_rate", "lead_time_days"],
            ascending=[True, False, False, True],
        )

        best = merged_df.iloc[0]

        return {
            "status": "SUCCESS",
            "supplier_id": best["supplier_id"],
            "supplier_name": best["supplier_name"],
            "sku": best["sku"],
            "unit_cost": float(best["unit_cost"]),
            "quantity": quantity,
            "total_cost": round(float(best["unit_cost"]) * quantity, 2),
            "available_qty": int(best["available_qty"]),
            "reliability_score": float(best["reliability_score"]),
            "on_time_rate": float(best["on_time_rate"]),
            "payment_terms": best["payment_terms"],
            "country": best["country"],
            "lead_time_days": int(best["lead_time_days"]),
        }


# =====================================================
# CALCULATOR TOOL
# =====================================================

class CalculatorTool(BaseTool):
    name: str = "Calculator Tool"
    description: str = "Calculates total procurement cost from unit cost and quantity."

    def _run(self, unit_cost: float, quantity: int) -> dict:
        total_cost = float(unit_cost) * int(quantity)

        return {
            "unit_cost": float(unit_cost),
            "quantity": int(quantity),
            "total_cost": round(total_cost, 2),
        }


# =====================================================
# APPROVAL TOOL
# =====================================================

LIMIT = float(os.getenv("PROCUREMENT_APPROVAL_LIMIT", "100000"))
PENDING_FILE = Path("data") / "pending_approvals.json"


class ApprovalTool(BaseTool):
    name: str = "Approval Tool"
    description: str = (
        "Approves purchase orders automatically if within the approval limit. "
        "Otherwise stores them for manager approval."
    )

    def _run(self, purchase_order: dict) -> dict:
        total_cost = float(purchase_order.get("total_cost", 0))
        purchase_order["approval_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if total_cost <= LIMIT:
            purchase_order["status"] = "APPROVED"

            return {
                "status": "APPROVED",
                "message": "Purchase order approved automatically.",
                "approval_limit": LIMIT,
                "purchase_order": purchase_order,
            }

        purchase_order["status"] = "PENDING_HUMAN_APPROVAL"

        PENDING_FILE.parent.mkdir(exist_ok=True)

        if not PENDING_FILE.exists():
            PENDING_FILE.write_text("[]", encoding="utf-8")

        try:
            pending_orders = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
        except Exception:
            pending_orders = []

        pending_orders.append(purchase_order)
        PENDING_FILE.write_text(json.dumps(pending_orders, indent=4), encoding="utf-8")

        return {
            "status": "PENDING_HUMAN_APPROVAL",
            "message": "Purchase order requires manager approval.",
            "approval_limit": LIMIT,
            "purchase_order": purchase_order,
        }


# =====================================================
# AZURE OPENAI LLM
# =====================================================

llm = LLM(
    model=f"azure/{os.getenv('AZURE_OPENAI_DEPLOYMENT')}",
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
)


# =====================================================
# PROCUREMENT AGENT FACTORY
# =====================================================

def get_procurement_agent():
    """
    Creates and returns the Procurement & Supplier Management Agent.
    """

    return Agent(
        role="Senior Procurement & Supplier Management Specialist",
        goal=(
            "Select the most suitable supplier, optimize procurement cost, generate accurate "
            "purchase orders, and ensure high-value purchase orders follow Human-in-the-Loop approval."
        ),
        backstory=(
            "You are an experienced Procurement Specialist for HexaShop. You make decisions using supplier "
            "performance, cost efficiency, stock availability, and delivery reliability. You never fabricate "
            "information and always rely on tools."
        ),
        llm=llm,
        tools=[
            SupplierTool(),
            CalculatorTool(),
            ApprovalTool(),
        ],
        allow_delegation=False,
        verbose=True,
    )
