from crewai.tools import BaseTool
from config import PO_APPROVAL_THRESHOLD

class ApprovalTool(BaseTool):
    name: str = "PO Approval Check Tool"
    description: str = (
        "Check if a purchase order total value requires human approval. "
        "Inputs the total order cost value (float)."
    )

    def _run(self, total_value: float) -> str:
        try:
            total_value = float(total_value)
            if total_value > PO_APPROVAL_THRESHOLD:
                return (
                    f"PO value ${total_value:.2f} exceeds threshold of ${PO_APPROVAL_THRESHOLD:.2f}. "
                    "Status: PENDING_HUMAN_APPROVAL"
                )
            return f"PO value ${total_value:.2f} is within threshold. Status: APPROVED"
        except Exception as e:
            return f"Error checking approval threshold: {str(e)}"
