from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4
from crewai import Crew, Task, Process

from agents.procurement_agent import (
    get_procurement_agent,
    PROCUREMENT_PROMPT,
    SupplierTool,
    CalculatorTool,
    ApprovalTool,
)


DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def run_direct_procurement(sku: str, quantity: int) -> dict:
    supplier_result = SupplierTool()._run(sku=sku, quantity=quantity)
    if supplier_result.get("status") != "SUCCESS":
        text = f"Procurement failed: {supplier_result.get('message', 'No eligible supplier found.')}"
        return {"text": text, "hil_required": False, "reason": text, "details": supplier_result}

    cost_result = CalculatorTool()._run(
        unit_cost=supplier_result["unit_cost"],
        quantity=quantity,
    )
    purchase_order = {
        "purchase_order_id": f"PO-{str(uuid4())[:8].upper()}",
        "sku": supplier_result["sku"],
        "supplier_id": supplier_result["supplier_id"],
        "supplier_name": supplier_result["supplier_name"],
        "quantity": quantity,
        "unit_cost": supplier_result["unit_cost"],
        "total_cost": cost_result["total_cost"],
        "lead_time_days": supplier_result["lead_time_days"],
        "reliability_score": supplier_result["reliability_score"],
        "on_time_rate": supplier_result["on_time_rate"],
    }
    approval = ApprovalTool()._run(purchase_order=purchase_order)
    po = approval["purchase_order"]
    text = f"""
Purchase Order ID: {po['purchase_order_id']}
SKU: {po['sku']}
Supplier ID: {po['supplier_id']}
Supplier Name: {po['supplier_name']}
Quantity: {po['quantity']}
Unit Cost: {po['unit_cost']}
Total Cost: {po['total_cost']}
Lead Time: {po['lead_time_days']} days
Reliability Score: {po['reliability_score']}
On-Time Rate: {po['on_time_rate']}
Approval Status: {po['status']}
Approval Message: {approval['message']}
""".strip()
    hil_required = approval["status"] == "PENDING_HUMAN_APPROVAL"
    return {
        "text": text,
        "hil_required": hil_required,
        "reason": "Purchase order value exceeds approval limit." if hil_required else "Purchase order auto-approved.",
        "details": approval,
    }


def run_procurement_agent(query: str, sku: str | None = None, quantity: int | None = None) -> dict:
    if sku and quantity:
        return run_direct_procurement(sku=sku, quantity=quantity)

    inventory_json = DATA_DIR / "inventory.json"
    if not inventory_json.exists():
        return {
            "text": "Procurement cannot run because data/inventory.json is missing.",
            "hil_required": False,
            "reason": "Missing inventory.json",
            "details": {},
        }

    with open(inventory_json, "r", encoding="utf-8") as file:
        inventory_data = json.load(file)

    procurement_agent = get_procurement_agent()
    task = Task(
        description=f"""
{PROCUREMENT_PROMPT}

Manager question:
{query}

Inventory Data:
{json.dumps(inventory_data, indent=4)}

Use available tools to:
1. Identify the best supplier.
2. Calculate procurement cost.
3. Generate Purchase Order.
4. Perform Human-in-the-Loop approval check.
5. Return the final Purchase Order.
""",
        expected_output="Structured Purchase Order with approval status.",
        agent=procurement_agent,
    )
    crew = Crew(agents=[procurement_agent], tasks=[task], process=Process.sequential, verbose=True)
    result = str(crew.kickoff())
    hil_required = any(x in result.upper() for x in ["PENDING_HUMAN_APPROVAL", "PENDING(HUMAN APPROVAL)", "MANAGER APPROVAL"])
    return {
        "text": result,
        "hil_required": hil_required,
        "reason": "Purchase order requires manager approval." if hil_required else "No manager approval required.",
        "details": {},
    }
