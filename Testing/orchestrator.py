import os
import re
from typing import TypedDict, List, Dict, Any, Optional
from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from crewai import Task, Crew

from config import PO_APPROVAL_THRESHOLD

# Import specialist agents
from agents.inventory_agent import inventory_monitoring_agent, inventory_db as inv_tool
from agents.demand_agent import forecasting_agent
from agents.procurement_agent import get_procurement_agent
from agents.logistics_agent import run_logistics_agent
from agents.customer_agent import communicationAgent

load_dotenv()

# Central LLM for routing and summarization
routing_llm = AzureChatOpenAI(
    api_version="2024-12-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
    temperature=0.0
)

# State Definition
class SCMState(TypedDict):
    query: str
    route: str
    inventory_data: str
    forecasting_data: str
    procurement_draft: str
    po_value: float
    po_approved: Optional[bool]
    logistics_plan: str
    customer_comms: str
    final_response: str
    status: str
    log: List[Dict[str, str]]

def extract_po_value(text: str) -> float:
    """Helper to extract purchase order total value from text."""
    # Look for total_cost or total price patterns
    # e.g., "total_cost": 1250.00, or Total Cost: $1,250.00
    matches = re.findall(r'(?:total_cost|total cost|total value|total|cost|price)[\s":$]*([0-9,.]+)', text, re.IGNORECASE)
    for match in matches:
        clean_val = match.replace(",", "")
        try:
            val = float(clean_val)
            if val > 0:
                return val
        except ValueError:
            pass
    return 0.0

# ----------------------------------------------------
# LangGraph Nodes
# ----------------------------------------------------

def router_node(state: SCMState) -> Dict[str, Any]:
    """Classifies user queries into SCM routes."""
    query = state["query"]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "You are a routing supervisor for HexaShop SCM. "
            "Classify the manager's query into one of these routes:\n"
            "- 'inventory': Stock status, stock levels, low-stock lists, SKU lookup.\n"
            "- 'replenishment': Restocking, drafting/creating purchase orders, automatic replenishment.\n"
            "- 'logistics': Shipping planning, carrier rates, ship optimization, delivery carriers.\n"
            "- 'customer_comms': Customer notification, delay email generation, customer status lookup.\n\n"
            "Respond ONLY with one of these lowercase strings: 'inventory', 'replenishment', 'logistics', or 'customer_comms'."
        )),
        ("human", "{query}")
    ])
    
    response = routing_llm.invoke(prompt.format_messages(query=query))
    route = response.content.strip().lower()
    
    # Validation fallback
    if route not in ["inventory", "replenishment", "logistics", "customer_comms"]:
        route = "inventory"
        
    log_entry = {
        "step": "Routing Supervisor",
        "message": f"Classified query route as: {route.upper()}"
    }
    
    return {
        "route": route,
        "status": f"{route}_running",
        "log": state.get("log", []) + [log_entry]
    }

def inventory_node(state: SCMState) -> Dict[str, Any]:
    """Runs the Inventory Monitoring Agent."""
    query = state["query"]
    route = state["route"]
    
    log_entry = {
        "step": "Inventory Monitor",
        "message": "Analyzing warehouse stock databases..."
    }
    
    # If in replenishment flow, run low-stock list task
    if route == "replenishment":
        task_desc = "Search inventory database and list all products that are below their reorder levels."
    else:
        task_desc = query
        
    task = Task(
        description=task_desc,
        expected_output="Detailed inventory status for low-stock items.",
        agent=inventory_monitoring_agent
    )
    
    crew = Crew(
        agents=[inventory_monitoring_agent],
        tasks=[task],
        verbose=False
    )
    
    result = str(crew.kickoff())
    
    return {
        "inventory_data": result,
        "final_response": result if route == "inventory" else "",
        "status": "inventory_done" if route == "replenishment" else "completed",
        "log": state.get("log", []) + [log_entry]
    }

def demand_node(state: SCMState) -> Dict[str, Any]:
    """Runs the Demand Forecasting Agent."""
    inventory_data = state["inventory_data"]
    
    log_entry = {
        "step": "Demand Forecaster",
        "message": "Predicting demand per SKU based on sales history..."
    }
    
    task_desc = (
        f"Forecast demand for the following low-stock products over the next 30 days: \n{inventory_data}\n"
        "Identify high risk stock-outs."
    )
    
    task = Task(
        description=task_desc,
        expected_output="Forecasted demand and stock risks.",
        agent=forecasting_agent
    )
    
    crew = Crew(
        agents=[forecasting_agent],
        tasks=[task],
        verbose=False
    )
    
    result = str(crew.kickoff())
    
    return {
        "forecasting_data": result,
        "status": "forecasting_done",
        "log": state.get("log", []) + [log_entry]
    }

def procurement_node(state: SCMState) -> Dict[str, Any]:
    """Runs the Procurement Agent to choose suppliers and draft POs."""
    forecasting_data = state["forecasting_data"]
    
    log_entry = {
        "step": "Procurement Specialist",
        "message": "Selecting suppliers and drafting purchase orders..."
    }
    
    procurement_agent = get_procurement_agent()
    
    task_desc = (
        f"Based on the forecasted demand: \n{forecasting_data}\n"
        "1. Identify the matching items needing replenishment.\n"
        "2. Query the supplier catalog for each item to select the best supplier.\n"
        "3. Draft a purchase order (PO) for each. Include: SKU, Quantity, Supplier, Unit Cost, and Total Cost.\n"
        "4. Calculate the grand total SCM PO cost."
    )
    
    task = Task(
        description=task_desc,
        expected_output="Drafted purchase orders with supplier, unit cost, quantities and grand total.",
        agent=procurement_agent
    )
    
    crew = Crew(
        agents=[procurement_agent],
        tasks=[task],
        verbose=False
    )
    
    result = str(crew.kickoff())
    po_value = extract_po_value(result)
    
    status = "pending_approval" if po_value > PO_APPROVAL_THRESHOLD else "procurement_done"
    
    approval_log = {
        "step": "Human-in-the-Loop Check",
        "message": f"PO value ${po_value:.2f} threshold check. Status: {status.upper()}"
    }
    
    return {
        "procurement_draft": result,
        "po_value": po_value,
        "status": status,
        "log": state.get("log", []) + [log_entry, approval_log]
    }

def human_approval_node(state: SCMState) -> Dict[str, Any]:
    """Human-in-the-loop gate node. Handled as a graph interrupt."""
    # This node is hit only if po_value > threshold.
    # The graph will be interrupted BEFORE entering the next node (place_po).
    # Streamlit sets the po_approved flag in State before resuming.
    return {}

def place_po_node(state: SCMState) -> Dict[str, Any]:
    """Finalizes and registers the purchase orders."""
    po_approved = state.get("po_approved")
    procurement_draft = state["procurement_draft"]
    po_value = state["po_value"]
    
    log_entry = {
        "step": "PO Finalizer",
        "message": f"POs approved by manager? {po_approved}"
    }
    
    if po_approved is False:
        final_response = (
            "### Purchase Order Status: REJECTED\n\n"
            f"The SCM Manager has rejected the drafted purchase orders totaling **${po_value:.2f}**.\n"
            "Replenishment has been cancelled."
        )
    else:
        final_response = (
            "### Purchase Order Status: PLACED\n\n"
            f"The purchase orders totaling **${po_value:.2f}** have been successfully finalized and sent to suppliers!\n\n"
            f"{procurement_draft}"
        )
        
    return {
        "final_response": final_response,
        "status": "completed",
        "log": state.get("log", []) + [log_entry]
    }

def logistics_node(state: SCMState) -> Dict[str, Any]:
    """Runs the Logistics Routing Agent."""
    query = state["query"]
    
    log_entry = {
        "step": "Logistics Planner",
        "message": "Calculating shipping paths and optimizing freight carriers..."
    }
    
    # Parse query defaults
    limit = 5
    mode = "balanced"
    
    limit_match = re.search(r'limit=(\d+)', query)
    if limit_match:
        limit = int(limit_match.group(1))
        
    mode_match = re.search(r'mode=(cheapest|fastest|balanced)', query, re.IGNORECASE)
    if mode_match:
        mode = mode_match.group(1).lower()
        
    result = run_logistics_agent(question=query, limit=limit, mode=mode)
    result_str = str(result)
    
    return {
        "logistics_plan": result_str,
        "final_response": result_str,
        "status": "completed",
        "log": state.get("log", []) + [log_entry]
    }

def customer_comms_node(state: SCMState) -> Dict[str, Any]:
    """Runs Customer Communication Agent (LangGraph graph)."""
    query = state["query"]
    
    log_entry = {
        "step": "Customer Communicator",
        "message": "Generating professional notifications for customer deliveries..."
    }
    
    # Extract order_id if present in prompt
    order_id_match = re.search(r'order[-_]?id\s*[:=]?\s*([a-zA-Z0-9\-]+)', query, re.IGNORECASE)
    order_id = ""
    if order_id_match:
        order_id = order_id_match.group(1).strip()
    else:
        # Fallback regex for orders matching hexashop format (e.g. ORD-1001)
        ord_match = re.search(r'(ord-[0-9]+)', query, re.IGNORECASE)
        if ord_match:
            order_id = ord_match.group(1).strip().upper()
            
    if not order_id:
        result_str = "Error: Please provide a valid Customer Order ID (e.g. ORD-1001) to draft delay notifications."
    else:
        # Invoke customer agent graph
        response = communicationAgent.invoke(
            {
                "order_id": order_id,
                "customer_name": "",
                "customer_email": "",
                "customer_tier": "",
                "sku": "",
                "quantity": 0,
                "order_status": "",
                "priority": "",
                "email_subject": "",
                "email_body": "",
                "manager_summary": ""
            }
        )
        
        result_str = (
            f"**Subject:** {response.get('email_subject', '')}\n\n"
            f"**Email Body:**\n{response.get('email_body', '')}\n\n"
            f"**Manager Summary:** {response.get('manager_summary', '')}"
        )
        
    return {
        "customer_comms": result_str,
        "final_response": result_str,
        "status": "completed",
        "log": state.get("log", []) + [log_entry]
    }

# ----------------------------------------------------
# Build the State Graph
# ----------------------------------------------------

workflow = StateGraph(SCMState)

# Add Nodes
workflow.add_node("router", router_node)
workflow.add_node("inventory", inventory_node)
workflow.add_node("demand", demand_node)
workflow.add_node("procurement", procurement_node)
workflow.add_node("human_approval", human_approval_node)
workflow.add_node("place_po", place_po_node)
workflow.add_node("logistics", logistics_node)
workflow.add_node("customer_comms", customer_comms_node)

# Add Edges
workflow.add_edge(START, "router")

# Routing Logic
def routing_condition(state: SCMState) -> str:
    return state["route"]

workflow.add_conditional_edges(
    "router",
    routing_condition,
    {
        "inventory": "inventory",
        "replenishment": "inventory",
        "logistics": "logistics",
        "customer_comms": "customer_comms"
    }
)

# UC-1, UC-3, UC-4 end immediately
workflow.add_edge("inventory", END)
workflow.add_edge("logistics", END)
workflow.add_edge("customer_comms", END)

# UC-2 (Replenishment) chain
workflow.add_edge("inventory", "demand")
workflow.add_edge("demand", "procurement")

# Replenishment Routing: checks if PO exceeds threshold
def po_approval_condition(state: SCMState) -> str:
    if state["po_value"] > PO_APPROVAL_THRESHOLD:
        return "human_approval"
    return "place_po"

workflow.add_conditional_edges(
    "procurement",
    po_approval_condition,
    {
        "human_approval": "human_approval",
        "place_po": "place_po"
    }
)

workflow.add_edge("human_approval", "place_po")
workflow.add_edge("place_po", END)

# Setup memory saver checkpointer and compile
memory_saver = MemorySaver()
orchestrator_graph = workflow.compile(
    checkpointer=memory_saver,
    interrupt_before=["place_po"]
)
