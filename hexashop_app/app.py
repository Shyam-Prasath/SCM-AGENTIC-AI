from __future__ import annotations

import pandas as pd
import streamlit as st

from langgraph_workflow import app_graph
from logger_config import read_recent_logs, log_event

st.set_page_config(
    page_title="HexaShop SCM Agentic AI",
    page_icon="📦",
    layout="wide",
)

st.title("📦 HexaShop SCM Multi-Agent System")
st.caption("LangGraph supervisor + CrewAI specialist agents + Guardrails + Human-in-the-Loop + Logging")

SAMPLE_QUESTIONS = [
    "Forecast demand for ELC-1001 for 7 days",
    "Show all low stock products below reorder level",
    "Which SKUs are below reorder level in the North warehouse?",
    "Create procurement plan for low stock items",
    "Find best supplier for ELC-1001 quantity 120",
    "Create balanced logistics plan for 10 pending orders",
    "Choose fastest carrier for 5 pending orders",
    "Check delay risk for all pending orders using cheapest mode",
    "Generate customer communication for order ORD-90017",
    "Run full end-to-end SCM workflow for ELC-1001 for 7 days",
]


def init_state():
    if "last_result" not in st.session_state:
        st.session_state.last_result = None
    if "pending_hil_state" not in st.session_state:
        st.session_state.pending_hil_state = None


init_state()

with st.sidebar:
    st.header("Controls")
    app_mode = st.radio(
        "Routing Mode",
        ["Auto Route", "Demand Forecast", "Inventory", "Procurement", "Logistics", "Communication", "Full Pipeline"],
    )

    st.subheader("Optional Inputs")
    sku = st.text_input("SKU", placeholder="ELC-1001")
    forecast_days = st.number_input("Forecast days", min_value=1, max_value=365, value=7)
    order_id = st.text_input("Order ID", placeholder="ORD-90017")
    quantity = st.number_input("Procurement quantity", min_value=0, value=0)
    logistics_mode = st.selectbox("Logistics mode", ["balanced", "cheapest", "fastest"])
    limit_all = st.checkbox("Use all pending orders for logistics")
    pending_limit = st.number_input("Pending order limit", min_value=1, max_value=500, value=5, disabled=limit_all)

    st.subheader("Sample Questions")
    selected_sample = st.selectbox("Pick a sample", [""] + SAMPLE_QUESTIONS)

route_map = {
    "Demand Forecast": "demand_forecast",
    "Inventory": "inventory_monitoring",
    "Procurement": "procurement",
    "Logistics": "logistics",
    "Communication": "communication",
    "Full Pipeline": "full_pipeline",
}

main_tab, logs_tab, help_tab = st.tabs(["Ask SCM Agent", "Logs", "Help / Test Questions"])

with main_tab:
    default_question = selected_sample if selected_sample else ""
    query = st.text_area(
        "Manager Question",
        value=default_question,
        placeholder="Example: Create balanced logistics plan for 10 pending orders",
        height=120,
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        run_clicked = st.button("🚀 Run Agent", type="primary", use_container_width=True)
    with col2:
        clear_clicked = st.button("🧹 Clear Result", use_container_width=True)

    if clear_clicked:
        st.session_state.last_result = None
        st.session_state.pending_hil_state = None
        st.rerun()

    if run_clicked:
        if not query.strip():
            st.warning("Please enter a manager question.")
        else:
            route = None if app_mode == "Auto Route" else route_map[app_mode]
            state = {
                "query": query.strip(),
                "route": route,
                "sku": sku.strip().upper() if sku.strip() else None,
                "days": int(forecast_days) if forecast_days else None,
                "order_id": order_id.strip().upper() if order_id.strip() else None,
                "quantity": int(quantity) if quantity else None,
                "mode": logistics_mode,
                "limit": None if limit_all else int(pending_limit),
                "guardrail_notes": [],
                "errors": [],
            }
            with st.spinner("Running LangGraph workflow..."):
                try:
                    result = app_graph.invoke(state)
                    st.session_state.last_result = result
                    if result.get("hil_required"):
                        st.session_state.pending_hil_state = result
                    log_event("streamlit_run", {"query": query, "route": result.get("route"), "hil_required": result.get("hil_required")})
                except Exception as exc:
                    st.error(f"Application error: {exc}")
                    log_event("streamlit_error", {"query": query, "error": str(exc)})

    result = st.session_state.last_result
    if result:
        st.divider()
        st.subheader("Result")
        cols = st.columns(4)
        cols[0].metric("Route", result.get("route", "-"))
        cols[1].metric("HIL Required", "Yes" if result.get("hil_required") else "No")
        cols[2].metric("Mode", result.get("mode", "-"))
        cols[3].metric("Limit", "All" if result.get("limit") is None else result.get("limit", "-"))

        if result.get("final_response"):
            st.markdown(result["final_response"])

        if result.get("hil_required") and not result.get("hil_decision"):
            st.warning("Human-in-the-Loop approval is required before proceeding.")
            with st.expander("Approval Details", expanded=True):
                st.write("**Agent:**", result.get("hil_agent"))
                st.write("**Reason:**", result.get("hil_reason"))
                st.json(result.get("hil_payload", {}))

            decision_col1, decision_col2, decision_col3 = st.columns(3)
            note = st.text_input("Manager note optional")
            if decision_col1.button("✅ APPROVE", use_container_width=True):
                hil_state = dict(st.session_state.pending_hil_state or result)
                hil_state["hil_decision"] = "APPROVE"
                hil_state["hil_decision_note"] = note
                hil_state["final_response"] = None
                with st.spinner("Applying approval..."):
                    new_result = app_graph.invoke(hil_state)
                st.session_state.last_result = new_result
                st.session_state.pending_hil_state = None
                st.rerun()
            if decision_col2.button("❌ REJECT", use_container_width=True):
                hil_state = dict(st.session_state.pending_hil_state or result)
                hil_state["hil_decision"] = "REJECT"
                hil_state["hil_decision_note"] = note
                hil_state["final_response"] = None
                with st.spinner("Applying rejection..."):
                    new_result = app_graph.invoke(hil_state)
                st.session_state.last_result = new_result
                st.session_state.pending_hil_state = None
                st.rerun()
            if decision_col3.button("⏸ HOLD", use_container_width=True):
                hil_state = dict(st.session_state.pending_hil_state or result)
                hil_state["hil_decision"] = "HOLD"
                hil_state["hil_decision_note"] = note
                hil_state["final_response"] = None
                with st.spinner("Applying hold decision..."):
                    new_result = app_graph.invoke(hil_state)
                st.session_state.last_result = new_result
                st.session_state.pending_hil_state = None
                st.rerun()

with logs_tab:
    st.subheader("Recent Project Logs")
    logs = read_recent_logs(limit=100)
    if not logs:
        st.info("No logs yet. Run an agent first.")
    else:
        df = pd.DataFrame(logs)
        st.dataframe(df, use_container_width=True)
        with st.expander("Raw logs"):
            st.json(logs)

with help_tab:
    st.subheader("Sample Questions to Test")
    st.markdown("### Demand Forecasting")
    st.code("Forecast demand for ELC-1001 for 7 days\nCheck stock-out risk for FSH-2001 for 10 days")
    st.markdown("### Inventory Monitoring")
    st.code("Show all low stock products below reorder level\nWhich SKUs are below reorder level in the North warehouse?")
    st.markdown("### Procurement")
    st.code("Create procurement plan for low stock items\nFind best supplier for ELC-1001 quantity 120")
    st.markdown("### Logistics")
    st.code("Create balanced logistics plan for 10 pending orders\nChoose fastest carrier for 5 pending orders\nCheck delay risk for all pending orders using cheapest mode")
    st.markdown("### Customer Communication")
    st.code("Generate customer communication for order ORD-90017\nDraft customer email for delayed order ORD-90018")
    st.markdown("### Full Pipeline")
    st.code("Run full end-to-end SCM workflow for ELC-1001 for 7 days")

    st.subheader("Human-in-the-Loop Scenarios")
    st.markdown(
        "- Procurement: high-value purchase order exceeds approval limit.\n"
        "- Logistics: delay risk, high shipment weight, or high shipping cost.\n"
        "- Inventory: critical shortage exceeds threshold.\n"
        "- Demand: predicted demand exceeds stock or is unusually high.\n"
        "- Communication: high-priority customer message requires review."
    )
