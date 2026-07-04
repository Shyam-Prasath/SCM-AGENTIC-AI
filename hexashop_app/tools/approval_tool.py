import json
import os
from datetime import datetime
from pathlib import Path
from crewai.tools import BaseTool

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
