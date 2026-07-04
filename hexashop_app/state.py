from __future__ import annotations
from typing import TypedDict, Optional, List, Dict, Any


class SCMState(TypedDict, total=False):
    query: str
    route: str

    sku: Optional[str]
    days: Optional[int]
    order_id: Optional[str]
    quantity: Optional[int]
    limit: Optional[int]
    mode: Optional[str]

    needs_follow_up: bool
    follow_up_question: Optional[str]

    forecast_result: Optional[str]
    inventory_result: Optional[str]
    procurement_result: Optional[str]
    logistics_result: Optional[str]
    communication_result: Optional[str]

    hil_required: bool
    hil_agent: Optional[str]
    hil_reason: Optional[str]
    hil_payload: Optional[Dict[str, Any]]
    hil_decision: Optional[str]
    hil_decision_note: Optional[str]

    guardrail_notes: List[str]
    errors: List[str]
    final_response: Optional[str]
