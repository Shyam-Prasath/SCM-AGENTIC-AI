import json
import os
from datetime import datetime

from crewai.tools import BaseTool

LIMIT = 100000
PENDING_FILE = "data/pending.json"

class ApprovalTool(BaseTool):
    name: str = "Approval Tool"
    description: str = (
        "Approves purchase orders automatically if within the approval limit. "
        "Otherwise, stores them for manager approval."
    )

    def _run(self, purchase_order: dict) -> dict:
        """
        Approves or routes a purchase order for human approval.

        Args:
            purchase_order (dict): Purchase Order details.

        Returns:
            dict: Approval status and updated Purchase Order.
        """

        total_cost = purchase_order["total_cost"]

        # Auto Approval
        if total_cost <= LIMIT:
            purchase_order["status"] = "APPROVED"
            purchase_order["approval_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            return {
                "status": "APPROVED",
                "message": "Purchase order approved automatically.",
                "purchase_order": purchase_order,
            }

        # Human Approval Required
        purchase_order["status"] = "PENDING(HUMAN APPROVAL)"
        purchase_order["approval_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Create pending file if it doesn't exist
        if not os.path.exists(PENDING_FILE):
            with open(PENDING_FILE, "w") as file:
                json.dump([], file, indent=4)

        # Read existing pending orders
        with open(PENDING_FILE, "r") as file:
            pending_orders = json.load(file)

        # Append current order
        pending_orders.append(purchase_order)

        # Save updated pending orders
        with open(PENDING_FILE, "w") as file:
            json.dump(pending_orders, file, indent=4)

        return {
            "status": "PENDING(HUMAN APPROVAL)",
            "message": "Purchase order requires manager approval.",
            "purchase_order": purchase_order,
        }