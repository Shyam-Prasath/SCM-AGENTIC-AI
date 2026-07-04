from __future__ import annotations

import re
from typing import Optional

ROUTES = [
    "demand_forecast",
    "inventory_monitoring",
    "procurement",
    "logistics",
    "communication",
    "full_pipeline",
    "fallback",
    "follow_up",
]

SKU_RE = re.compile(r"\b[A-Z]{2,5}-\d{3,5}\b", re.IGNORECASE)
ORDER_RE = re.compile(r"\bORD[-_]?\d{3,6}\b", re.IGNORECASE)


def extract_sku(text: str) -> Optional[str]:
    match = SKU_RE.search(text or "")
    return match.group(0).upper() if match else None


def extract_order_id(text: str) -> Optional[str]:
    match = ORDER_RE.search(text or "")
    return match.group(0).replace("_", "-").upper() if match else None


def extract_days(text: str) -> Optional[int]:
    text = (text or "").lower()
    patterns = [r"for\s+(\d+)\s+days?", r"next\s+(\d+)\s+days?", r"(\d+)\s+day\s+forecast"]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = int(match.group(1))
            return value if value > 0 else None
    return None


def extract_quantity(text: str) -> Optional[int]:
    text = (text or "").lower()
    patterns = [r"quantity\s*(?:=|:)?\s*(\d+)", r"qty\s*(?:=|:)?\s*(\d+)", r"procure\s+(\d+)"]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = int(match.group(1))
            return value if value > 0 else None
    return None


def detect_logistics_mode(text: str) -> Optional[str]:
    text = (text or "").lower()
    if any(word in text for word in ["fastest", "quickest", "speed", "fast eta"]):
        return "fastest"
    if any(word in text for word in ["cheapest", "lowest cost", "low cost", "economical"]):
        return "cheapest"
    if any(word in text for word in ["balanced", "optimized", "optimised", "best"]):
        return "balanced"
    return None


def extract_limit(text: str) -> Optional[int]:
    text = (text or "").lower()
    if "all" in text:
        return None
    patterns = [r"for\s+(\d+)\s+(?:pending\s+)?orders?", r"(\d+)\s+(?:pending\s+)?orders?"]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = int(match.group(1))
            return value if value > 0 else 5
    return None


def route_query(query: str) -> str:
    q = (query or "").lower()

    # Full pipeline
    if any(x in q for x in [
        "full pipeline",
        "end-to-end",
        "end to end",
        "daily scm",
        "complete workflow",
        "complete supply chain",
        "run full",
        "full workflow"
    ]):
        return "full_pipeline"

    # Customer communication
    if any(x in q for x in [
        "email",
        "communication",
        "customer update",
        "notify customer",
        "draft",
        "apology",
        "customer message",
        "manager summary"
    ]):
        return "communication"

    # Logistics
    if any(x in q for x in [
        "logistics",
        "shipping",
        "shipment",
        "carrier",
        "fulfilment",
        "fulfillment",
        "eta",
        "delay risk",
        "routing",
        "delivery plan",
        "delivery risk"
    ]):
        return "logistics"

    # Procurement
    if any(x in q for x in [
        "procurement",
        "purchase order",
        "generate po",
        "supplier",
        "procure",
        "approval status",
        "best supplier",
        "po"
    ]):
        return "procurement"

    # Demand forecasting
    if any(x in q for x in [
        "forecast",
        "predict demand",
        "demand",
        "stock-out risk",
        "stockout",
        "sales prediction",
        "future demand"
    ]):
        return "demand_forecast"

    # Inventory monitoring
    if any(x in q for x in [
        "low stock",
        "below reorder",
        "reorder level",
        "inventory",
        "sku profile",
        "replenishment",
        "critical shortage",
        "shortage",
        "severe shortage",
        "stock shortage",
        "out of stock",
        "stock level",
        "on hand"
    ]):
        return "inventory_monitoring"

    return "fallback"

def build_follow_up_question(route: str, state: dict) -> Optional[str]:
    if route == "demand_forecast":
        if not state.get("sku"):
            return "Please provide the SKU for demand forecasting, for example: ELC-1001."
        if not state.get("days"):
            return "Please provide forecast days, for example: 7 days."
    if route == "communication":
        if not state.get("order_id"):
            return "Please provide the Order ID for customer communication, for example: ORD-90017."
    if route == "procurement":
        # Procurement can run a general low-stock procurement plan without SKU/quantity.
        return None
    return None


def apply_input_guardrails(raw_state: dict) -> dict:
    state = dict(raw_state)
    query = state.get("query", "")
    notes = state.get("guardrail_notes", []) or []

    route = state.get("route") or route_query(query)
    state["route"] = route

    state["sku"] = state.get("sku") or extract_sku(query)
    state["order_id"] = state.get("order_id") or extract_order_id(query)
    state["days"] = state.get("days") or extract_days(query)
    state["quantity"] = state.get("quantity") or extract_quantity(query)
    state["mode"] = state.get("mode") or detect_logistics_mode(query) or "balanced"

    if "all" in (query or "").lower() and route == "logistics":
        state["limit"] = None
    else:
        state["limit"] = state.get("limit") or extract_limit(query) or 5

    if route == "fallback":
        state["needs_follow_up"] = False
        notes.append("Unsupported or unclear SCM query routed to fallback.")
    else:
        follow_up = build_follow_up_question(route, state)
        state["needs_follow_up"] = bool(follow_up)
        state["follow_up_question"] = follow_up
        if follow_up:
            notes.append(f"Follow-up required for route {route}.")

    state["guardrail_notes"] = notes
    state.setdefault("errors", [])
    return state
