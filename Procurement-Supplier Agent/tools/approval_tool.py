import json
import os
from datetime import datetime
from langchain.tools import tool 

Limit=100000
pending="data/pending.json"

@tool
def approval_tool(purchase_order: dict) -> dict:
    """
    Approves or rejects a purchase order based on the total cost.
    Args:
        purchase_order(dict): Purchase order details
    Returns:
        dict: Approval status and message
    """

    total_cost = purchase_order["total_cost"]

    if total_cost <= Limit:
        purchase_order["status"] = "APPROVED"
        purchase_order["approval_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return {
                "status": "APPROVED",
                "message": "Purchase order approved.",
                "purchase_order": purchase_order
            }
    #human approval required for orders above the limit
    purchase_order["status"] = "PENDING(HUMAN APPROVAL)"
    purchase_order["approval_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Save the pending purchase order to a JSON file
    if not os.path.exists(pending):
        with open(pending, 'w') as f:
            json.dump([], f)
    with open(pending, 'r+') as f:
        data = json.load(f)
    data.append(purchase_order)
    with open(pending, 'w') as f:
        json.dump(data, f, indent=4)
    return {
        "status": "PENDING(HUMAN APPROVAL)",
        "message": "Purchase order requires human approval.",
        "purchase_order": purchase_order
    }