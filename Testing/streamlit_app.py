import streamlit as st
import time
from orchestrator import orchestrator_graph, extract_po_value
from config import PO_APPROVAL_THRESHOLD

# Configure page metadata
st.set_page_config(
    page_title="HexaShop SCM Agentic Portal",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Premium Design & Sleek Dark Mode (Glassmorphism, animations)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Space+Grotesk:wght@300;500;700&display=swap');
    
    /* Overall Background and Fonts */
    .stApp {
        background-color: #0b0e17;
        color: #e2e8f0;
        font-family: 'Outfit', sans-serif;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #07090f;
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    /* Header Gradient Text */
    .main-title {
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 800;
        background: linear-gradient(90deg, #38bdf8 0%, #a855f7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3rem;
        margin-bottom: 0.2rem;
    }
    
    .subtitle {
        color: #94a3b8;
        font-size: 1.1rem;
        margin-bottom: 2rem;
        font-weight: 300;
    }
    
    /* Glassmorphic SCM Cards */
    .scm-card {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 16px;
        padding: 24px;
        backdrop-filter: blur(12px);
        margin-bottom: 20px;
        transition: all 0.3s ease;
    }
    .scm-card:hover {
        border-color: rgba(56, 189, 248, 0.3);
        transform: translateY(-2px);
        box-shadow: 0 10px 20px rgba(0, 0, 0, 0.2);
    }
    
    /* Status Badge styling */
    .status-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        margin-bottom: 10px;
    }
    .status-completed { background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3); }
    .status-pending { background: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.3); }
    .status-running { background: rgba(59, 130, 246, 0.15); color: #3b82f6; border: 1px solid rgba(59, 130, 246, 0.3); }
    
    /* Timeline styling */
    .timeline-container {
        border-left: 2px solid rgba(255, 255, 255, 0.1);
        padding-left: 20px;
        margin-left: 10px;
        margin-bottom: 20px;
    }
    .timeline-item {
        position: relative;
        margin-bottom: 16px;
    }
    .timeline-dot {
        position: absolute;
        left: -27px;
        top: 4px;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        background: #a855f7;
        box-shadow: 0 0 8px #a855f7;
    }
    .timeline-dot.active {
        background: #38bdf8;
        box-shadow: 0 0 8px #38bdf8;
        animation: pulse 1.5s infinite;
    }
    
    @keyframes pulse {
        0% { transform: scale(1); opacity: 1; }
        50% { transform: scale(1.3); opacity: 0.7; }
        100% { transform: scale(1); opacity: 1; }
    }
    
    .timeline-title {
        font-weight: 600;
        font-size: 0.95rem;
        color: #f8fafc;
    }
    .timeline-desc {
        font-size: 0.85rem;
        color: #94a3b8;
    }
    
    /* Approval Card styles */
    .approval-box {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(245, 158, 11, 0.05) 100%);
        border: 2px solid rgba(245, 158, 11, 0.4);
        border-radius: 12px;
        padding: 20px;
        margin-top: 15px;
        margin-bottom: 15px;
        animation: slideIn 0.5s ease-out;
    }
    @keyframes slideIn {
        from { transform: translateY(10px); opacity: 0; }
        to { transform: translateY(0); opacity: 1; }
    }
</style>
""", unsafe_allow_html=True)

# Application Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/isometric/512/000000/factory.png", width=80)
    st.markdown("### HexaShop SCM Portal")
    st.write("Modular Single-Agent & Coordinated Multi-Agent system powered by CrewAI & LangGraph.")
    
    st.markdown("---")
    st.markdown("#### System Configuration")
    po_threshold = st.slider("PO Approval Threshold ($)", 100.0, 5000.0, PO_APPROVAL_THRESHOLD, step=100.0)
    st.info(f"POs above **${po_threshold:,.2f}** require manual manager override.")
    
    st.markdown("---")
    st.write("🟢 **Connected Agents**:")
    st.write("- 📦 `Inventory Monitoring Agent`")
    st.write("- 📈 `Demand Forecasting Agent`")
    st.write("- 🛒 `Procurement Specialist`")
    st.write("- 🚛 `Logistics Optimizer`")
    st.write("- ✉️ `Customer Communicator`")

# Header Section
st.markdown('<h1 class="main-title">HexaShop Supply Chain</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">AI Agentic Operations & Auto-Replenishment Command Center</p>', unsafe_allow_html=True)

# Initialize Session States
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "graph_state" not in st.session_state:
    st.session_state.graph_state = None
if "pending_approval" not in st.session_state:
    st.session_state.pending_approval = False
if "thread_id" not in st.session_state:
    st.session_state.thread_id = f"thread_{int(time.time())}"

config = {"configurable": {"thread_id": st.session_state.thread_id}}

# Display Chat History
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "log" in message:
            # Display step execution logs inside expander
            with st.expander("🔍 System Execution Logs", expanded=False):
                st.markdown('<div class="timeline-container">', unsafe_allow_html=True)
                for entry in message["log"]:
                    st.markdown(f"""
                    <div class="timeline-item">
                        <div class="timeline-dot"></div>
                        <div class="timeline-title">{entry['step']}</div>
                        <div class="timeline-desc">{entry['message']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

# Chat Input (Disabled if waiting for approval)
user_query = st.chat_input("Ask a question, request POs, optimize shipping...", disabled=st.session_state.pending_approval)

# Process New User Query
if user_query:
    # Append user message
    st.session_state.chat_history.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)
        
    with st.chat_message("assistant"):
        # Run orchestrator graph
        with st.spinner("SCM Supervisor routing request..."):
            initial_state = {
                "query": user_query,
                "route": "",
                "inventory_data": "",
                "forecasting_data": "",
                "procurement_draft": "",
                "po_value": 0.0,
                "po_approved": None,
                "logistics_plan": "",
                "customer_comms": "",
                "final_response": "",
                "status": "starting",
                "log": []
            }
            
            # Run graph until it ends or hits an interrupt
            result = orchestrator_graph.invoke(initial_state, config=config)
            
            # Fetch current state to see if it paused at the interrupt point
            graph_state = orchestrator_graph.get_state(config)
            
            # Log SCM Actions
            logs = graph_state.values.get("log", [])
            with st.expander("🔍 System Execution Logs", expanded=True):
                st.markdown('<div class="timeline-container">', unsafe_allow_html=True)
                for entry in logs:
                    st.markdown(f"""
                    <div class="timeline-item">
                        <div class="timeline-dot active"></div>
                        <div class="timeline-title">{entry['step']}</div>
                        <div class="timeline-desc">{entry['message']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

            # Check if we hit the interrupt before place_po
            if graph_state.next and "place_po" in graph_state.next[0]:
                st.session_state.pending_approval = True
                st.session_state.graph_state = graph_state.values
                # We do st.rerun() to show the live approval card
                st.rerun()
            else:
                # Finished without interrupt (UC-1, UC-3, UC-4 or low cost PO)
                final_res = graph_state.values.get("final_response", "Operation completed.")
                st.markdown(final_res)
                st.session_state.chat_history.append({
                    "role": "assistant", 
                    "content": final_res,
                    "log": logs
                })

# Display Human-in-the-Loop Approval Card if pending
if st.session_state.pending_approval and st.session_state.graph_state:
    state_values = st.session_state.graph_state
    po_draft = state_values.get("procurement_draft", "")
    po_val = state_values.get("po_value", 0.0)
    
    st.markdown("""
    <div class="approval-box">
        <h4 style="color: #f59e0b; margin-top: 0;">⚠️ Human Approval Required</h4>
        <p>A drafted Purchase Order has been created. The total SCM cost exceeds the approval threshold.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Renders the PO Draft so the manager can review
    st.info("📊 **Draft Purchase Orders Details**:")
    st.markdown(po_draft)
    
    # Action Buttons Side-by-Side
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Approve SCM Purchase Orders", use_container_width=True, type="primary"):
            # Update checkpointer state to approved
            orchestrator_graph.update_state(config, {"po_approved": True}, as_node="human_approval")
            
            with st.spinner("Finalizing purchase orders..."):
                # Resume execution
                orchestrator_graph.invoke(None, config=config)
                final_state = orchestrator_graph.get_state(config)
                
                final_res = final_state.values.get("final_response", "POs placed.")
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": final_res,
                    "log": final_state.values.get("log", [])
                })
                
            st.session_state.pending_approval = False
            st.session_state.graph_state = None
            st.rerun()
            
    with col2:
        if st.button("❌ Reject SCM Purchase Orders", use_container_width=True):
            # Update checkpointer state to rejected
            orchestrator_graph.update_state(config, {"po_approved": False}, as_node="human_approval")
            
            with st.spinner("Cancelling purchase orders..."):
                # Resume execution
                orchestrator_graph.invoke(None, config=config)
                final_state = orchestrator_graph.get_state(config)
                
                final_res = final_state.values.get("final_response", "POs rejected.")
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": final_res,
                    "log": final_state.values.get("log", [])
                })
                
            st.session_state.pending_approval = False
            st.session_state.graph_state = None
            st.rerun()
