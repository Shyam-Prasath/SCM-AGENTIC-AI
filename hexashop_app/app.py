from __future__ import annotations

import os
import re
import json
from pathlib import Path
from datetime import datetime
from html import escape
from typing import Any

import pandas as pd
import streamlit as st

# =====================================================
# ENV SETTINGS
# =====================================================

os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("LITELLM_LOG", "ERROR")

from langgraph_workflow import build_graph


# =====================================================
# PAGE CONFIG
# =====================================================

st.set_page_config(
    page_title="HexaShop SCM Agent System",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =====================================================
# GLOBAL CSS
# =====================================================

st.markdown(
    """
<style>
    html, body, [class*="css"] {
        font-family: "Segoe UI", sans-serif;
    }

    .block-container {
        padding-top: 2.4rem !important;
        padding-bottom: 3rem !important;
        max-width: 1500px;
    }

    .hero-wrap {
        padding: 0.8rem 0 1.2rem 0;
        overflow: visible;
    }

    .hero-title {
        font-size: clamp(2rem, 4vw, 3.1rem);
        font-weight: 900;
        letter-spacing: 0.5px;
        line-height: 1.25;
        margin: 0;
        padding: 0.2rem 0;
        color: #ffffff;
        overflow: visible;
        white-space: normal;
    }

    .hero-subtitle {
        color: #b8beca;
        font-size: clamp(0.95rem, 1.4vw, 1.08rem);
        margin-top: 0.4rem;
        line-height: 1.5;
    }

    .result-title {
        font-size: 1.8rem;
        font-weight: 850;
        margin: 1.5rem 0 1rem 0;
        color: #ffffff;
    }

    .section-title {
        font-size: clamp(1.5rem, 2.6vw, 2rem);
        font-weight: 900;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin: 1.6rem 0 1rem 0;
        color: #ffffff;
    }

    .metric-card {
        background: linear-gradient(180deg, #151923 0%, #0f131c 100%);
        border: 1px solid #2a3142;
        border-radius: 16px;
        padding: 1.1rem 1.25rem;
        min-height: 120px;
        overflow-wrap: anywhere;
    }

    .metric-label {
        color: #aeb6c8;
        font-size: 0.78rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin-bottom: 0.6rem;
    }

    .metric-value {
        color: #ffffff;
        font-size: clamp(1.05rem, 1.8vw, 1.45rem);
        font-weight: 850;
        line-height: 1.3;
    }

    .metric-note {
        color: #aeb6c8;
        font-size: 0.88rem;
        margin-top: 0.7rem;
        line-height: 1.45;
    }

    .hil-warning {
        background: #2e2608;
        border: 1px solid #d4a514;
        border-radius: 16px;
        padding: 1.2rem 1.35rem;
        margin: 1.3rem 0;
        color: #ffffff;
    }

    .hil-completed {
        background: #0f3a24;
        border: 1px solid #24b36b;
        border-radius: 16px;
        padding: 1rem 1.2rem;
        margin: 1.1rem 0;
        color: #ffffff;
    }

    .hil-rejected {
        background: #3a1111;
        border: 1px solid #ef4444;
        border-radius: 16px;
        padding: 1rem 1.2rem;
        margin: 1.1rem 0;
        color: #ffffff;
    }

    .hil-hold {
        background: #31270d;
        border: 1px solid #f59e0b;
        border-radius: 16px;
        padding: 1rem 1.2rem;
        margin: 1.1rem 0;
        color: #ffffff;
    }

    .no-hil {
        background: #0f2f21;
        border: 1px solid #22c55e;
        border-radius: 16px;
        padding: 1rem 1.2rem;
        margin: 1.1rem 0;
        color: #ffffff;
    }

    .answer-card {
        background: #0f131c;
        border: 1px solid #2b3242;
        border-radius: 18px;
        padding: 1.4rem 1.6rem;
        margin-top: 1rem;
        line-height: 1.75;
        font-size: 1rem;
        overflow-x: auto;
    }

    .answer-card p {
        margin-bottom: 0.8rem;
    }

    .answer-card ul {
        margin-top: 0.3rem;
        margin-bottom: 1rem;
    }

    .answer-card li {
        margin-bottom: 0.35rem;
    }

    .clean-divider {
        border-top: 1px solid #2b3242;
        margin: 1.4rem 0;
    }

    div[data-testid="stMetricValue"] {
        font-size: 1.35rem;
    }

    textarea {
        font-size: 1rem !important;
        line-height: 1.5 !important;
    }

    .stButton > button {
        border-radius: 12px;
        min-height: 3rem;
        font-weight: 750;
    }

    div[data-testid="stDataFrame"] {
        border-radius: 14px;
        overflow: hidden;
    }

    @media (max-width: 900px) {
        .block-container {
            padding-top: 1.5rem !important;
        }

        .metric-card {
            min-height: auto;
        }
    }
</style>
""",
    unsafe_allow_html=True,
)


# =====================================================
# AGENT CONFIG
# =====================================================

AGENT_CONFIG = {
    "demand_forecast": {
        "label": "Demand Forecasting Agent",
        "icon": "📈",
        "title": "Demand Forecast",
        "purpose": "Predicts future demand and checks inventory risk.",
    },
    "inventory_monitoring": {
        "label": "Inventory Monitoring Agent",
        "icon": "🏬",
        "title": "Inventory Status",
        "purpose": "Checks stock levels, reorder points, shortages, and critical inventory risk.",
    },
    "procurement": {
        "label": "Procurement & Supplier Agent",
        "icon": "🧾",
        "title": "Procurement / Purchase Order",
        "purpose": "Finds suppliers, calculates purchase cost, creates POs, and checks approval.",
    },
    "logistics": {
        "label": "Logistics & Routing Agent",
        "icon": "🚚",
        "title": "Logistics Plan",
        "purpose": "Compares carriers, ETA, cost, delivery risk, and shipment approval.",
    },
    "communication": {
        "label": "Customer Communication Agent",
        "icon": "✉️",
        "title": "Customer Communication",
        "purpose": "Creates professional customer emails and manager summaries.",
    },
    "full_pipeline": {
        "label": "Full SCM Pipeline",
        "icon": "🔄",
        "title": "Full SCM Workflow",
        "purpose": "Runs the full supply-chain flow across all agents.",
    },
    "follow_up": {
        "label": "Follow-up Required",
        "icon": "❓",
        "title": "Follow-up Required",
        "purpose": "Needs extra details before running the correct agent.",
    },
    "fallback": {
        "label": "Fallback",
        "icon": "⚠️",
        "title": "Unsupported Request",
        "purpose": "The request could not be mapped to a supply-chain agent.",
    },
    "error": {
        "label": "Error",
        "icon": "🚨",
        "title": "Application Error",
        "purpose": "Something went wrong while running the system.",
    },
}


# =====================================================
# DETECTION HELPERS
# =====================================================

def clean_route(route: str | None) -> str:
    return str(route or "fallback").strip().lower()


def agent_config(route: str | None) -> dict:
    return AGENT_CONFIG.get(clean_route(route), AGENT_CONFIG["fallback"])


def extract_sku(text: str) -> str | None:
    match = re.search(r"\b[A-Z]{3}-\d{4}\b", text.upper())
    return match.group(0) if match else None


def extract_order_id(text: str) -> str | None:
    match = re.search(r"\bORD-\d{5}\b", text.upper())
    return match.group(0) if match else None


def extract_forecast_days(text: str) -> int | None:
    q = text.lower()

    patterns = [
        r"next\s+(\d+)\s+days?",
        r"for\s+(\d+)\s+days?",
        r"(\d+)\s+days?",
    ]

    for pattern in patterns:
        match = re.search(pattern, q)
        if match:
            value = int(match.group(1))
            return value if value > 0 else None

    return None


def extract_procurement_quantity(text: str) -> int | None:
    q = text.lower()

    patterns = [
        r"quantity\s+(\d+)",
        r"qty\s+(\d+)",
        r"purchase\s+order\s+for\s+[a-z]{3}-\d{4}\s+(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, q)
        if match:
            value = int(match.group(1))
            return value if value > 0 else None

    return None


def detect_logistics_mode(text: str) -> str | None:
    q = text.lower()

    if any(word in q for word in ["fastest", "faster", "quickest", "quick", "speed", "express"]):
        return "fastest"

    if any(word in q for word in ["cheapest", "lowest cost", "low cost", "budget", "economical"]):
        return "cheapest"

    if any(word in q for word in ["balanced", "best", "optimized", "optimised", "optimal"]):
        return "balanced"

    return None


def detect_logistics_limit(text: str) -> tuple[int | None, bool]:
    q = text.lower()

    if any(phrase in q for phrase in ["all pending orders", "all orders", "all pending"]):
        return None, True

    patterns = [
        r"for\s+(\d+)\s+pending\s+orders?",
        r"for\s+(\d+)\s+orders?",
        r"(\d+)\s+pending\s+orders?",
        r"(\d+)\s+orders?",
    ]

    for pattern in patterns:
        match = re.search(pattern, q)
        if match:
            value = int(match.group(1))
            return value if value > 0 else 5, False

    return None, False


# =====================================================
# RESULT EXTRACTION HELPERS
# =====================================================

def deep_find_key(obj: Any, target_key: str) -> Any:
    if isinstance(obj, dict):
        if target_key in obj:
            return obj[target_key]

        for value in obj.values():
            found = deep_find_key(value, target_key)
            if found is not None:
                return found

    elif isinstance(obj, list):
        for item in obj:
            found = deep_find_key(item, target_key)
            if found is not None:
                return found

    return None


def extract_payload_details(result: dict) -> dict:
    for key in ["details", "hil_details", "agent_details", "payload"]:
        value = result.get(key)
        if isinstance(value, dict):
            return value

    found = deep_find_key(result, "details")
    if isinstance(found, dict):
        return found

    return {}


def get_final_text(result: dict) -> str:
    for key in [
        "final_response",
        "text",
        "response",
        "procurement_result",
        "inventory_result",
        "forecast_result",
        "logistics_result",
        "communication_result",
    ]:
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value

        if isinstance(value, dict):
            inner_text = value.get("text") or value.get("final_response")
            if isinstance(inner_text, str) and inner_text.strip():
                return inner_text

    return "No result generated."


def get_hil_reason(result: dict, route: str) -> str:
    reason = (
        result.get("hil_reason")
        or result.get("reason")
        or deep_find_key(result, "reason")
        or "Manager approval required."
    )

    return str(reason)


def strip_hil_noise(text: str) -> str:
    cleaned = str(text)

    # Remove HIL block from final response because UI has its own HIL panel.
    patterns = [
        r"(?is)##\s*Human-in-the-Loop Required.*?(?=##\s*[A-Z][A-Z /\-&]+|#\s*[A-Z]|[A-Z][A-Z /\-&]{8,}\n)",
        r"(?is)Human-in-the-Loop Required\s*Agent:.*?(?=[A-Z][A-Z /\-&]{8,}\n)",
        r"(?is)Human-in-the-Loop approval is required before proceeding\.",
        r"(?is)Approval Details\s*Agent:.*?(?=\n[A-Z][A-Z /\-&]{8,}\n|$)",
        r"(?is)\{\s*\"text\"\s*:.*$",
    ]

    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned).strip()

    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def apply_hil_to_result(result: dict, decision: str) -> dict:
    """Patch the result dict so pending approval statuses reflect the actual HIL decision."""
    if not decision:
        return result

    status_map = {
        "APPROVE": "APPROVED",
        "REJECT": "REJECTED",
        "HOLD": "ON_HOLD",
    }
    new_status = status_map.get(decision.upper(), decision.upper())

    pending_patterns = [
        "PENDING_HUMAN_APPROVAL",
        "PENDING_MANAGER_APPROVAL",
        "AWAITING_APPROVAL",
        "PENDING_APPROVAL",
    ]

    def _patch_str(text: str) -> str:
        for pat in pending_patterns:
            text = text.replace(pat, new_status)
        return text

    def _patch_obj(obj: Any) -> Any:
        if isinstance(obj, str):
            return _patch_str(obj)
        if isinstance(obj, dict):
            return {k: _patch_obj(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_patch_obj(item) for item in obj]
        return obj

    return _patch_obj(result)


# =====================================================
# OUTPUT FORMATTERS
# =====================================================

def clean_procurement_output(text: str) -> str:
    text = strip_hil_noise(text)

    labels = [
        "Purchase Order ID:",
        "SKU:",
        "Supplier ID:",
        "Supplier Name:",
        "Quantity:",
        "Unit Cost:",
        "Total Cost:",
        "Lead Time:",
        "Reliability Score:",
        "On-Time Rate:",
        "Approval Status:",
        "Approval Reason:",
        "Approval Message:",
        "Unfulfilled low-stock items:",
        "Unfulfilled replenishment items:",
    ]

    for label in labels:
        text = re.sub(rf"\s*{re.escape(label)}", f"\n\n**{label}** ", text)

    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_communication_output(text: str) -> str:
    text = strip_hil_noise(text)

    labels = ["Subject:", "Email Draft:", "Email:", "Manager Summary:"]

    for label in labels:
        text = re.sub(rf"\s*{re.escape(label)}", f"\n\n### {label}", text)

    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_general_output(text: str) -> str:
    text = strip_hil_noise(text)
    text = text.replace("```", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def format_text(route: str, text: str) -> str:
    route = clean_route(route)

    if route == "procurement":
        return clean_procurement_output(text)

    if route == "communication":
        return clean_communication_output(text)

    return clean_general_output(text)


# =====================================================
# LOGISTICS TABLE EXTRACTION
# =====================================================

def logistics_plan_from_details(result: dict) -> tuple[pd.DataFrame, dict]:
    details = extract_payload_details(result)

    shipping_plan = None

    if isinstance(details, dict):
        shipping_plan = details.get("shipping_plan")

    if shipping_plan is None:
        shipping_plan = deep_find_key(result, "shipping_plan")

    if not isinstance(shipping_plan, list) or not shipping_plan:
        return pd.DataFrame(), details if isinstance(details, dict) else {}

    rows = []

    for item in shipping_plan:
        if not isinstance(item, dict):
            continue

        rows.append(
            {
                "Order ID": item.get("order_id", ""),
                "Customer ID": item.get("customer_id", ""),
                "SKU": item.get("sku", ""),
                "Product": item.get("product_name", ""),
                "Qty": item.get("qty", ""),
                "Region": item.get("ship_to_region", ""),
                "Carrier": item.get("chosen_carrier", ""),
                "Service": item.get("service_level", ""),
                "Cost": item.get("shipping_cost", ""),
                "ETA": item.get("eta_days", ""),
                "Expected Delivery": item.get("expected_delivery_date", ""),
                "Delivery Risk": item.get("delivery_risk", ""),
                "Approval Required": item.get("approval_required", ""),
                "Shipment Status": item.get("shipment_status", ""),
                "Tracking ID": item.get("tracking_id", ""),
                "Approval Reason": "; ".join(item.get("approval_reasons", []))
                if isinstance(item.get("approval_reasons", []), list)
                else item.get("approval_reasons", ""),
            }
        )

    return pd.DataFrame(rows), details if isinstance(details, dict) else {}


def extract_label(block: str, label: str) -> str:
    pattern = rf"{re.escape(label)}\s*:\s*(.*)"
    match = re.search(pattern, block, flags=re.IGNORECASE)
    if not match:
        return ""

    value = match.group(1).strip()
    value = value.split("\n")[0].strip()
    return value


def logistics_plan_from_text(text: str) -> pd.DataFrame:
    text = str(text)

    blocks = re.split(r"\n(?=\s*(?:\d+\)\s*)?Order ID\s*:)", text)

    rows = []

    for block in blocks:
        if "Order ID:" not in block:
            continue

        order_id = extract_label(block, "Order ID")
        if not order_id:
            continue

        rows.append(
            {
                "Order ID": order_id,
                "Customer ID": extract_label(block, "Customer ID"),
                "SKU": extract_label(block, "SKU"),
                "Product": extract_label(block, "Product"),
                "Qty": extract_label(block, "Quantity"),
                "Region": extract_label(block, "Region"),
                "Carrier": extract_label(block, "Chosen Carrier") or extract_label(block, "Carrier"),
                "Service": extract_label(block, "Service Level"),
                "Cost": extract_label(block, "Shipping Cost"),
                "ETA": extract_label(block, "ETA Days") or extract_label(block, "ETA"),
                "Expected Delivery": extract_label(block, "Expected Delivery Date"),
                "Delivery Risk": extract_label(block, "Delivery Risk"),
                "Approval Required": extract_label(block, "Approval Required"),
                "Shipment Status": extract_label(block, "Shipment status") or extract_label(block, "Shipment Status"),
                "Tracking ID": extract_label(block, "Tracking ID"),
                "Approval Reason": extract_label(block, "Approval reason") or extract_label(block, "Approval Reasons"),
            }
        )

    return pd.DataFrame(rows)


def remove_logistics_order_blocks(text: str) -> str:
    text = strip_hil_noise(text)

    markers = [
        "Order-wise fulfilment plan",
        "Order-wise fulfillment plan",
        "ORDER WISE PLAN",
    ]

    for marker in markers:
        index = text.lower().find(marker.lower())
        if index != -1:
            return text[:index].strip()

    # Remove numbered order blocks if they exist.
    text = re.sub(
        r"(?is)\n?\s*\d+\)\s*Order ID\s*:.*?(?=(?:\n\s*\d+\)\s*Order ID\s*:)|\Z)",
        "",
        text,
    )

    return re.sub(r"\n{3,}", "\n\n", text).strip()


# =====================================================
# UI COMPONENTS
# =====================================================

def metric_card(label: str, value: str, note: str | None = None):
    note_html = f"<div class='metric-note'>{escape(note)}</div>" if note else ""

    st.markdown(
        f"""
<div class="metric-card">
    <div class="metric-label">{escape(label)}</div>
    <div class="metric-value">{escape(str(value))}</div>
    {note_html}
</div>
""",
        unsafe_allow_html=True,
    )


def render_result_cards(route: str, result: dict, effective_mode: str, effective_limit: int | None):
    route = clean_route(route)
    config = agent_config(route)

    decision = st.session_state.get("hil_decision")
    hil_required = bool(result.get("hil_required", False))

    if decision:
        hil_display = f"Decision: {decision}"
    else:
        hil_display = "Yes" if hil_required else "No"

    if route == "logistics":
        c1, c2, c3, c4 = st.columns(4)

        with c1:
            metric_card("Route", f"{config['icon']} {config['label']}")

        with c2:
            metric_card("HIL Status", hil_display)

        with c3:
            metric_card("Logistics Mode", effective_mode)

        with c4:
            metric_card("Pending Orders", "All" if effective_limit is None else str(effective_limit))

    else:
        c1, c2, c3 = st.columns([1.2, 1, 1.2])

        with c1:
            metric_card("Route", f"{config['icon']} {config['label']}")

        with c2:
            metric_card("HIL Status", hil_display)

        with c3:
            metric_card("Agent Purpose", config["purpose"])


def render_hil_panel(route: str, result: dict):
    hil_required = bool(result.get("hil_required", False))
    reason = get_hil_reason(result, route)
    config = agent_config(route)

    if not hil_required:
        st.markdown(
            """
<div class="no-hil">
    ✅ <b>No Human-in-the-Loop approval required.</b><br>
    This result can proceed automatically.
</div>
""",
            unsafe_allow_html=True,
        )
        return

    decision = st.session_state.get("hil_decision")

    if decision == "APPROVE":
        st.markdown(
            f"""
<div class="hil-completed">
    ✅ <b>Human-in-the-Loop Decision Completed</b><br>
    <b>Decision:</b> APPROVED<br>
    <b>Reason reviewed:</b> {escape(reason)}<br>
    <b>Status:</b> Manager approved this recommendation. The action can proceed.
</div>
""",
            unsafe_allow_html=True,
        )

    elif decision == "REJECT":
        st.markdown(
            f"""
<div class="hil-rejected">
    ❌ <b>Human-in-the-Loop Decision Completed</b><br>
    <b>Decision:</b> REJECTED<br>
    <b>Reason reviewed:</b> {escape(reason)}<br>
    <b>Status:</b> Manager rejected this recommendation. The action should not proceed.
</div>
""",
            unsafe_allow_html=True,
        )

    elif decision == "HOLD":
        st.markdown(
            f"""
<div class="hil-hold">
    ⏸ <b>Human-in-the-Loop Decision Completed</b><br>
    <b>Decision:</b> HOLD<br>
    <b>Reason reviewed:</b> {escape(reason)}<br>
    <b>Status:</b> Manager kept this action on hold for later review.
</div>
""",
            unsafe_allow_html=True,
        )

    else:
        st.markdown(
            f"""
<div class="hil-warning">
    ⚠️ <b>Human-in-the-Loop Required</b><br>
    <b>Manager review reason:</b> {escape(reason)}<br>
    <b>Status:</b> Waiting for manager decision.
</div>
""",
            unsafe_allow_html=True,
        )

        st.subheader("Manager Decision")

        c1, c2, c3 = st.columns(3)

        with c1:
            if st.button("✅ APPROVE", use_container_width=True):
                st.session_state.hil_decision = "APPROVE"
                st.session_state.hil_decision_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if "last_result" in st.session_state:
                    st.session_state.last_result = apply_hil_to_result(st.session_state.last_result, "APPROVE")
                st.rerun()

        with c2:
            if st.button("❌ REJECT", use_container_width=True):
                st.session_state.hil_decision = "REJECT"
                st.session_state.hil_decision_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if "last_result" in st.session_state:
                    st.session_state.last_result = apply_hil_to_result(st.session_state.last_result, "REJECT")
                st.rerun()

        with c3:
            if st.button("⏸ HOLD", use_container_width=True):
                st.session_state.hil_decision = "HOLD"
                st.session_state.hil_decision_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if "last_result" in st.session_state:
                    st.session_state.last_result = apply_hil_to_result(st.session_state.last_result, "HOLD")
                st.rerun()

    with st.expander("Approval Details", expanded=True):
        st.markdown(f"**Agent:** {config['label']}")
        st.markdown(f"**Manager reason:** {reason}")

        if st.session_state.get("hil_decision"):
            st.markdown(f"**Decision:** {st.session_state.hil_decision}")
            st.markdown(f"**Decision time:** {st.session_state.get('hil_decision_time', 'NA')}")

        details = extract_payload_details(result)

        if details:
            st.markdown("**Structured details:**")
            st.json(details, expanded=False)


def render_text_answer(route: str, result: dict):
    config = agent_config(route)
    raw_text = get_final_text(result)
    formatted = format_text(route, raw_text)

    if not formatted.strip():
        return

    st.markdown(f"<div class='section-title'>{escape(config['title'])}</div>", unsafe_allow_html=True)
    st.markdown("<div class='clean-divider'></div>", unsafe_allow_html=True)
    st.markdown(formatted)


def render_logistics_answer(result: dict):
    raw_text = get_final_text(result)

    df, details = logistics_plan_from_details(result)

    if df.empty:
        df = logistics_plan_from_text(raw_text)

    summary_text = remove_logistics_order_blocks(raw_text)

    st.markdown("<div class='section-title'>Logistics Plan</div>", unsafe_allow_html=True)

    if details:
        total_orders = details.get("total_orders_planned", len(df))
        total_cost = details.get("total_shipping_cost", "")
        avg_eta = details.get("average_eta_days", "")
        approval_count = details.get("approval_required_count", "")

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            st.metric("Orders Planned", total_orders)

        with c2:
            st.metric("Total Shipping Cost", total_cost)

        with c3:
            st.metric("Average ETA", avg_eta)

        with c4:
            st.metric("Approval Count", approval_count)

    if summary_text and summary_text.strip():
        st.markdown("<div class='clean-divider'></div>", unsafe_allow_html=True)
        st.markdown(summary_text)

    if not df.empty:
        st.subheader("Order-wise Fulfilment Table")

        display_df = df.copy()

        # Keep only clean readable columns.
        preferred_cols = [
            "Order ID",
            "Customer ID",
            "SKU",
            "Product",
            "Qty",
            "Region",
            "Carrier",
            "Service",
            "Cost",
            "ETA",
            "Expected Delivery",
            "Delivery Risk",
            "Approval Required",
            "Shipment Status",
            "Tracking ID",
            "Approval Reason",
        ]

        display_df = display_df[[col for col in preferred_cols if col in display_df.columns]]

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            height=min(620, 120 + len(display_df) * 36),
        )

        if "Delivery Risk" in display_df.columns:
            st.subheader("Delivery Risk Summary")
            risk_counts = display_df["Delivery Risk"].astype(str).value_counts().reset_index()
            risk_counts.columns = ["Delivery Risk", "Orders"]
            st.dataframe(risk_counts, use_container_width=True, hide_index=True)

        if "Approval Required" in display_df.columns:
            approval_rows = display_df[
                display_df["Approval Required"].astype(str).str.lower().isin(["true", "yes", "1"])
            ]

            if not approval_rows.empty:
                st.subheader("Orders Requiring Approval")
                st.dataframe(
                    approval_rows,
                    use_container_width=True,
                    hide_index=True,
                    height=min(420, 120 + len(approval_rows) * 36),
                )

    else:
        fallback_text = clean_general_output(raw_text)
        if fallback_text.strip():
            st.markdown("<div class='clean-divider'></div>", unsafe_allow_html=True)
            st.markdown(fallback_text)


def render_answer(route: str, result: dict):
    route = clean_route(route)

    if route == "logistics":
        render_logistics_answer(result)
    else:
        render_text_answer(route, result)


def read_recent_logs(limit: int = 80) -> str:
    paths = [
        Path("logs") / "scm_agent.log",
        Path("logs") / "scm_runs.jsonl",
        Path("logs") / "crew_output.log",
    ]

    parts = []

    for path in paths:
        if path.exists():
            try:
                lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
                parts.append(f"\n===== {path} =====\n")
                parts.extend(lines[-limit:])
            except Exception as e:
                parts.append(f"Could not read {path}: {e}")

    return "\n".join(parts).strip() if parts else "No logs found yet."


# =====================================================
# GRAPH
# =====================================================

@st.cache_resource
def get_graph():
    return build_graph()


app = get_graph()


# =====================================================
# HEADER
# =====================================================

st.markdown(
    """
<div class="hero-wrap">
    <div class="hero-title">📦 HexaShop SCM Multi-Agent System</div>
    <div class="hero-subtitle">
        LangGraph supervisor + CrewAI specialist agents + Guardrails + Human-in-the-Loop + Logging
    </div>
</div>
""",
    unsafe_allow_html=True,
)


# =====================================================
# SIDEBAR
# =====================================================

with st.sidebar:
    st.header("⚙️ Optional Inputs")
    st.caption("These are fallback values. If the question contains the value, the question gets priority.")

    st.divider()

    st.subheader("Common")
    sidebar_order_id = st.text_input("Order ID", value="ORD-90017")
    sidebar_sku = st.text_input("SKU", value="ELC-1001")

    st.subheader("Demand Forecasting")
    sidebar_forecast_days = st.number_input(
        "Forecast days",
        min_value=1,
        max_value=365,
        value=7,
        step=1,
    )

    st.subheader("Procurement")
    sidebar_procurement_quantity = st.number_input(
        "Procurement quantity",
        min_value=0,
        value=0,
        step=1,
        help="Use 0 when the quantity is already in the question or not required.",
    )

    st.subheader("Logistics")
    sidebar_mode = st.selectbox(
        "Fallback logistics mode",
        ["balanced", "cheapest", "fastest"],
        index=0,
        help="Question text has priority. Example: 'fastest carrier' overrides this.",
    )

    sidebar_use_all = st.checkbox("Use all pending orders for logistics", value=False)

    sidebar_limit = st.number_input(
        "Fallback pending order limit",
        min_value=1,
        max_value=100,
        value=5,
        step=1,
        disabled=sidebar_use_all,
    )

    st.divider()

    st.subheader("Sample Questions")

    sample_questions = [
        "Forecast demand for SKU ELC-1001 for the next 7 days.",
        "Which SKUs are below reorder level in the North warehouse?",
        "Show critical shortage products",
        "Create purchase order for ELC-1001 quantity 564",
        "Generate the complete procurement recommendation for all inventory items that need replenishment",
        "Choose the fastest carrier for 10 pending orders.",
        "Check delay risk for all pending orders using cheapest mode",
        "Generate communication for Order ID ORD-90059",
        "Run full end-to-end SCM workflow",
    ]

    selected_sample = st.selectbox("Pick a sample", [""] + sample_questions)


# =====================================================
# TABS
# =====================================================

tab_ask, tab_logs, tab_help = st.tabs(["Ask SCM Agent", "Logs", "Help / Test Questions"])


# =====================================================
# ASK TAB
# =====================================================

with tab_ask:
    manager_question = st.text_area(
        "Manager Question",
        value=selected_sample,
        height=125,
        placeholder="Example: Choose the fastest carrier for 10 pending orders.",
    )

    c1, c2 = st.columns([1, 1])

    with c1:
        run_clicked = st.button("🚀 Run Agent", type="primary", use_container_width=True)

    with c2:
        clear_clicked = st.button("🧹 Clear Result", use_container_width=True)

    if clear_clicked:
        for key in [
            "last_result",
            "last_route",
            "last_mode",
            "last_limit",
            "last_question",
            "hil_decision",
            "hil_decision_time",
        ]:
            st.session_state.pop(key, None)

        st.rerun()

    if run_clicked:
        if not manager_question.strip():
            st.warning("Please enter a manager question.")
        else:
            query = manager_question.strip()

            extracted_sku = extract_sku(query) or (sidebar_sku.strip().upper() if sidebar_sku.strip() else None)
            extracted_order_id = extract_order_id(query) or (
                sidebar_order_id.strip().upper() if sidebar_order_id.strip() else None
            )

            forecast_days = extract_forecast_days(query) or int(sidebar_forecast_days)

            procurement_quantity = extract_procurement_quantity(query)

            if procurement_quantity is None and int(sidebar_procurement_quantity) > 0:
                procurement_quantity = int(sidebar_procurement_quantity)

            detected_mode = detect_logistics_mode(query)
            effective_mode = detected_mode or sidebar_mode

            detected_limit, query_says_all = detect_logistics_limit(query)

            if detected_limit is not None:
                effective_limit = detected_limit
            elif query_says_all:
                effective_limit = None
            elif sidebar_use_all:
                effective_limit = None
            else:
                effective_limit = int(sidebar_limit)

            state = {
                "query": query,

                # Shared extracted inputs
                "sku": extracted_sku,
                "order_id": extracted_order_id,
                "forecast_days": forecast_days,

                # Procurement compatibility keys
                "quantity": procurement_quantity,
                "procurement_quantity": procurement_quantity,

                # Logistics
                "mode": effective_mode,
                "limit": effective_limit,

                # HIL
                "hil_required": False,
                "hil_reason": None,
                "hil_decision": None,
            }

            with st.spinner("Running SCM agent..."):
                try:
                    result = app.invoke(state)
                except Exception as e:
                    result = {
                        "route": "error",
                        "final_response": f"Application Error: {e}",
                        "hil_required": False,
                        "hil_reason": str(e),
                    }

            route = clean_route(result.get("route", "fallback"))

            # Preserve effective UI values, because graph may not return them.
            result["mode"] = effective_mode
            result["limit"] = effective_limit

            st.session_state.last_result = result
            st.session_state.last_route = route
            st.session_state.last_mode = effective_mode
            st.session_state.last_limit = effective_limit
            st.session_state.last_question = query
            st.session_state.hil_decision = None
            st.session_state.hil_decision_time = None

            st.rerun()

    if "last_result" in st.session_state:
        result = st.session_state.last_result
        route = clean_route(st.session_state.get("last_route", result.get("route", "fallback")))
        effective_mode = st.session_state.get("last_mode", result.get("mode", "balanced"))
        effective_limit = st.session_state.get("last_limit", result.get("limit", 5))

        st.markdown("<div class='clean-divider'></div>", unsafe_allow_html=True)
        st.markdown("<div class='result-title'>Result</div>", unsafe_allow_html=True)

        render_result_cards(route, result, effective_mode, effective_limit)
        render_hil_panel(route, result)
        render_answer(route, result)


# =====================================================
# LOGS TAB
# =====================================================

with tab_logs:
    st.subheader("Recent Logs")

    c1, c2 = st.columns([1, 1])

    with c1:
        if st.button("🔄 Refresh Logs", use_container_width=True):
            st.rerun()

    with c2:
        log_limit = st.number_input(
            "Lines per log file",
            min_value=20,
            max_value=500,
            value=80,
            step=20,
        )

    st.code(read_recent_logs(limit=int(log_limit)), language="text")


# =====================================================
# HELP TAB
# =====================================================

with tab_help:
    st.subheader("Recommended Test Questions")

    st.markdown(
        """
### Demand Forecasting
- Forecast demand for SKU ELC-1001 for the next 7 days.
- Forecast demand for HOM-3004 for 30 days.
- Predict demand for FSH-2012 for 10 days.

### Inventory Monitoring
- Show all low stock products.
- Which SKUs are below reorder level in the North warehouse?
- Show critical shortage products.
- Show SKU profile for ELC-1001.

### Procurement
- Create purchase order for ELC-1001 quantity 564.
- Generate the complete procurement recommendation for all inventory items that need replenishment.
- Find best supplier for FSH-2012 quantity 113.
- Create procurement plan for low stock items.

### Logistics
- Choose the fastest carrier for 10 pending orders.
- Create balanced logistics plan for 10 pending orders.
- Check delay risk for all pending orders using cheapest mode.
- Find shipments that need manager approval.

### Customer Communication
- Generate communication for Order ID ORD-90059.
- Draft customer email for order ORD-90017.
- Generate customer communication for delayed order ORD-90017.

### Full Pipeline
- Run full end-to-end SCM workflow.
- Run complete HexaShop supply chain analysis.
"""
    )