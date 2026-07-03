"""
HexaShop SCM Multi-Agent System — LangGraph Integration
=========================================================
Combines: Demand Forecasting, Inventory Monitoring, Procurement,
Logistics & Routing, and Customer Communication agents (all CrewAI)
into one LangGraph supervisor-routed graph.

Requirements:
    pip install langgraph crewai crewai-tools pandas python-dotenv

Expected project layout (unchanged from your existing setup):
    tools/supplier_tool.py, tools/calculator_tool.py, tools/approval_tool.py
    prompts/prompt.py               (PROCUREMENT_PROMPT)
    agent.py                        (get_procurement_agent)
    inventory data/inventory.json
    data/scm.sqlite                 (used by inventory_db tool below)
    sales_history.csv, inventory.csv, customers.csv, orders.csv
"""

import os
import json
import sqlite3
from typing import TypedDict, Optional

import pandas as pd
from dotenv import load_dotenv

from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool

from langgraph.graph import StateGraph, START, END

# Procurement agent reuses your existing agent.py / prompts / tools
from agent import get_procurement_agent
from prompts.prompt import PROCUREMENT_PROMPT

# Logistics agent reuses your existing standalone module as-is
from logistics_routing_agent import run_logistics_agent

load_dotenv()

# =====================================================
# SHARED LLM
# =====================================================

llm = LLM(
    model=f"azure/{os.getenv('AZURE_OPENAI_DEPLOYMENT')}",
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
)

router_llm = LLM(
    model=f"azure/{os.getenv('AZURE_OPENAI_DEPLOYMENT')}",
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    temperature=0,
)

DB_PATH = "data/scm.sqlite"


# =====================================================
# STATE
# =====================================================

class SCMState(TypedDict, total=False):
    query: str
    route: str
    order_id: Optional[str]
    limit: Optional[int]
    mode: Optional[str]

    forecast_result: Optional[str]
    inventory_result: Optional[str]
    procurement_result: Optional[str]
    logistics_result: Optional[str]
    communication_result: Optional[str]

    final_response: Optional[str]


# =====================================================
# 1. DEMAND FORECASTING AGENT
# =====================================================

sales_df = pd.read_csv("sales_history.csv")
forecast_inventory_df = pd.read_csv("inventory.csv")


@tool
def forecast_model(sku: str, days: int) -> dict:
    """Predict near-term demand for a SKU using the last 7 days of sales history."""
    sku_sales = sales_df[sales_df["sku"] == sku]
    if sku_sales.empty:
        return {"error": "SKU not found"}
    last_7_days = sku_sales.tail(7)
    avg_daily_sales = last_7_days["units_sold"].mean()
    predicted_demand = round(avg_daily_sales * days)
    return {"sku": sku, "forecast_days": days, "predicted_demand": predicted_demand}


@tool
def inventory_db_lookup(sku: str) -> dict:
    """Retrieve inventory information for a given SKU and identify inventory risk."""
    item = forecast_inventory_df[
        (forecast_inventory_df["sku"] == sku)
        & (forecast_inventory_df["warehouse"] == "North DC")
    ]
    if item.empty:
        return {"error": "SKU not found"}
    row = item.iloc[0]
    if row["on_hand"] < row["reorder_point"]:
        risk = "Stock-Out Risk"
    elif row["on_hand"] > row["reorder_qty"]:
        risk = "Overstock Risk"
    else:
        risk = "Normal"
    return {
        "sku": row["sku"], "warehouse": row["warehouse"],
        "on_hand": int(row["on_hand"]), "reorder_point": int(row["reorder_point"]),
        "reorder_qty": int(row["reorder_qty"]), "risk": risk,
    }


forecasting_agent = Agent(
    role="Demand Forecasting Analyst",
    goal="Predict near-term demand per SKU from sales history and identify stock-out or overstock risk.",
    backstory="""You are a senior demand forecasting analyst at HexaShop.
You analyze historical sales, forecast demand, compare it with inventory,
and recommend replenishment actions. You always use forecast_model and
inventory_db_lookup. Never fabricate values.""",
    tools=[forecast_model, inventory_db_lookup],
    llm=llm,
    verbose=True,
    allow_delegation=False,
)


def run_forecast_agent(query: str) -> str:
    task = Task(
        description=query,
        expected_output="Forecast demand, compare inventory, identify inventory risk and provide recommendation.",
        agent=forecasting_agent,
    )
    crew = Crew(agents=[forecasting_agent], tasks=[task], verbose=True)
    return str(crew.kickoff())


# =====================================================
# 2. INVENTORY MONITORING AGENT
# =====================================================

@tool
def inventory_db(question: str) -> str:
    """
    Query inventory database and answer inventory questions.
    Example: "Which SKUs are below reorder level in the North warehouse?"
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        question = question.lower()

        if "below reorder" in question and "north" in question:
            query = """
                SELECT i.sku, p.product_name, i.warehouse, i.on_hand, i.reorder_point, i.reorder_qty
                FROM inventory i JOIN products p ON p.sku = i.sku
                WHERE i.region = 'North' AND i.on_hand < i.reorder_point
                ORDER BY (i.reorder_point - i.on_hand) DESC
            """
        elif "below reorder" in question or "low stock" in question:
            query = """
                SELECT i.sku, p.product_name, i.warehouse, i.on_hand, i.reorder_point, i.reorder_qty
                FROM inventory i JOIN products p ON p.sku = i.sku
                WHERE i.on_hand < i.reorder_point
                ORDER BY (i.reorder_point - i.on_hand) DESC
            """
        else:
            return "Unsupported inventory question. Ask about low stock or reorder levels."

        cursor.execute(query)
        rows = cursor.fetchall()
        if not rows:
            return "No matching inventory records found."

        output = []
        for row in rows:
            output.append(
                f"\nSKU: {row[0]}\nProduct: {row[1]}\nWarehouse: {row[2]}\n"
                f"On Hand: {row[3]}\nReorder Point: {row[4]}\nReorder Quantity: {row[5]}\n"
            )
        return "\n".join(output)
    except Exception as ex:
        return f"Database Error: {str(ex)}"
    finally:
        conn.close()


@tool
def low_stock_scanner(dummy_input: str = "") -> str:
    """Returns all SKUs below reorder level."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        query = """
            SELECT i.sku, p.product_name, i.warehouse, i.region, i.on_hand,
                   i.reorder_point, i.reorder_qty, (i.reorder_point - i.on_hand) AS shortage
            FROM inventory i JOIN products p ON p.sku = i.sku
            WHERE i.on_hand < i.reorder_point
            ORDER BY shortage DESC
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        if not rows:
            return "No low stock items found."

        result = []
        for row in rows:
            result.append(
                f"\nSKU: {row[0]}\nProduct: {row[1]}\nWarehouse: {row[2]}\nRegion: {row[3]}\n"
                f"On Hand: {row[4]}\nReorder Point: {row[5]}\nReorder Qty: {row[6]}\nShortage: {row[7]}\n"
            )
        return "\n".join(result)
    except Exception as ex:
        return f"Database Error: {str(ex)}"
    finally:
        conn.close()


@tool
def sku_profile(sku: str) -> str:
    """Retrieve product information for a SKU."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        query = """
            SELECT sku, product_name, category, subcategory, brand, unit_price, weight_kg
            FROM products WHERE sku = ?
        """
        cursor.execute(query, (sku,))
        row = cursor.fetchone()
        if not row:
            return f"No SKU found: {sku}"
        return (
            f"\nSKU: {row[0]}\nProduct: {row[1]}\nCategory: {row[2]}\nSubcategory: {row[3]}\n"
            f"Brand: {row[4]}\nUnit Price: ${row[5]}\nWeight: {row[6]} kg\n"
        )
    except Exception as ex:
        return f"Database Error: {str(ex)}"
    finally:
        conn.close()


inventory_monitoring_agent = Agent(
    role="Inventory Monitoring Agent",
    goal="Monitor inventory levels, identify low-stock items, answer inventory-related questions, and provide replenishment insights.",
    backstory="""You are the Inventory Monitoring Agent for HexaShop.
Use ONLY the inventory_db tool for stock numbers. Never invent values.
If inventory information is unavailable, clearly say so. All responses
must be grounded in database results.""",
    tools=[inventory_db, low_stock_scanner, sku_profile],
    llm=llm,
    verbose=True,
    allow_delegation=False,
)


def run_inventory_agent(query: str) -> str:
    task = Task(
        description=f"""
        Answer the following inventory question.

        Question:
        {query}

        Rules:
        - Use Inventory Database Tool.
        - Never invent stock values.
        - Use actual database values.
        """,
        expected_output="Grounded inventory answer using actual inventory data.",
        agent=inventory_monitoring_agent,
    )
    crew = Crew(agents=[inventory_monitoring_agent], tasks=[task], verbose=True)
    return str(crew.kickoff())


# =====================================================
# 3. PROCUREMENT AGENT (reuses your agent.py / tools / prompts)
# =====================================================

procurement_agent = get_procurement_agent()


def run_procurement_agent(inventory_path: str = "inventory data/inventory.json",
                           extra_instruction: str = "") -> str:
    with open(inventory_path, "r") as file:
        inventory_data = json.load(file)

    description = f"""
{PROCUREMENT_PROMPT}

Inventory Data:
{json.dumps(inventory_data, indent=4)}

{extra_instruction}

Using the available tools:
1. Identify the best supplier.
2. Calculate procurement cost.
3. Generate Purchase Order.
4. Perform Human-in-the-Loop approval check.
5. Return the final Purchase Order.
"""
    task = Task(
        description=description,
        expected_output="""
Return a structured Purchase Order containing:
- Purchase Order ID
- SKU
- Supplier ID
- Supplier Name
- Quantity
- Unit Cost
- Total Cost
- Lead Time
- Approval Status
""",
        agent=procurement_agent,
    )
    crew = Crew(agents=[procurement_agent], tasks=[task], process=Process.sequential, verbose=True)
    return str(crew.kickoff())


# =====================================================
# 4. LOGISTICS & ROUTING AGENT
#    -> reused directly via run_logistics_agent() imported above
#       from your existing logistics_routing_agent.py
# =====================================================


# =====================================================
# 5. CUSTOMER COMMUNICATION AGENT
# =====================================================

customers_df = pd.read_csv("customers.csv")
orders_df = pd.read_csv("orders.csv")


def get_customer_details(order_id: str) -> dict:
    order = orders_df[orders_df["order_id"] == order_id]
    if order.empty:
        return {"error": "Invalid Order ID"}
    customer = customers_df[customers_df["customer_id"] == order.iloc[0]["customer_id"]]
    if customer.empty:
        return {"error": "Customer Not Found"}
    return {
        "order_id": order.iloc[0]["order_id"],
        "customer_name": customer.iloc[0]["customer_name"],
        "customer_email": customer.iloc[0]["email"],
        "customer_tier": customer.iloc[0]["tier"],
        "sku": order.iloc[0]["sku"],
        "quantity": int(order.iloc[0]["qty"]),
        "status": order.iloc[0]["status"],
        "order_date": order.iloc[0]["order_date"],
        "promised_date": order.iloc[0]["promised_date"],
        "region": customer.iloc[0]["region"],
    }


def calculate_priority(status: str, tier: str) -> str:
    status, tier = status.upper(), tier.upper()
    if status == "CANCELLED":
        return "HIGH"
    if status == "DELAYED":
        return "HIGH" if tier == "PREMIUM" else "MEDIUM"
    if status in ("PENDING", "ALLOCATED"):
        return "MEDIUM"
    return "LOW"


communication_agent = Agent(
    role="Customer Communication Specialist",
    goal="Generate professional customer communication based on customer, order status and business priority.",
    backstory="""You are a Senior Customer Communication Specialist at HexaShop.
You always retrieve customer information using tools, determine priority before
generating emails, never fabricate customer information.""",
    tools=[get_customer_details, calculate_priority],
    llm=llm,
    verbose=True,
    allow_delegation=False,
)


def _parse_communication_output(output: str):
    subject, email, manager, current = "", "", "", ""
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("Subject:"):
            subject = line.replace("Subject:", "").strip()
            continue
        elif line.startswith("Email"):
            current = "email"
            continue
        elif line.startswith("Manager Summary"):
            current = "manager"
            continue
        if current == "email":
            email += line + "\n"
        elif current == "manager":
            manager += line + "\n"
    return subject, email.strip(), manager.strip()


def run_communication_agent(order_id: str) -> str:
    customer = get_customer_details(order_id)
    if "error" in customer:
        return customer["error"]

    priority = calculate_priority(customer["status"], customer["customer_tier"])

    prompt = f"""
You are HexaShop's Customer Communication Specialist.

Customer Name : {customer["customer_name"]}
Customer Email : {customer["customer_email"]}
Customer Tier : {customer["customer_tier"]}
Order ID : {customer["order_id"]}
Product SKU : {customer["sku"]}
Quantity : {customer["quantity"]}
Order Status : {customer["status"]}
Priority : {priority}

Generate
1. Subject
2. Professional Customer Email
3. Manager Summary

Rules:
- Keep the email polite and professional.
- If Priority is HIGH provide Manager Summary.
- Otherwise return NA.

Return exactly in this format.
Subject:
Email:
Manager Summary:
"""
    task = Task(
        description=prompt,
        expected_output="Subject, Customer Email, Manager Summary",
        agent=communication_agent,
    )
    crew = Crew(agents=[communication_agent], tasks=[task], verbose=True)
    result = crew.kickoff()

    subject, email, manager = _parse_communication_output(str(result))
    return (
        f"Subject: {subject}\n\n"
        f"Email:\n{email}\n\n"
        f"Manager Summary:\n{manager if manager else 'NA'}"
    )


# =====================================================
# LANGGRAPH SUPERVISOR + NODES
# =====================================================

ROUTES = ["demand_forecast", "inventory_monitoring", "procurement",
          "logistics", "communication", "full_pipeline"]

ROUTER_PROMPT = """You are a routing controller for HexaShop's Supply Chain
Multi-Agent System. Read the user's message and decide which single agent
should handle it.

Valid routes:
- demand_forecast      -> demand prediction, stock-out/overstock risk questions
- inventory_monitoring -> "what's low on stock", reorder level questions
- procurement          -> generate/approve purchase orders, pick suppliers
- logistics            -> shipping plans, carrier selection, fulfilment
- communication        -> draft a customer email/update for an order id
- full_pipeline        -> "run the full process", "daily SCM run", end-to-end

User message:
{query}

Respond with ONLY one word: the route name. Nothing else.
"""


def supervisor(state: SCMState) -> SCMState:
    resp = router_llm.call(ROUTER_PROMPT.format(query=state["query"]))
    route = str(resp).strip().lower()
    state["route"] = route if route in ROUTES else "inventory_monitoring"
    return state


def route_decider(state: SCMState) -> str:
    return state["route"]


def forecast_node(state: SCMState) -> SCMState:
    state["forecast_result"] = run_forecast_agent(state["query"])
    return state


def inventory_node(state: SCMState) -> SCMState:
    state["inventory_result"] = run_inventory_agent(state["query"])
    return state


def procurement_node(state: SCMState) -> SCMState:
    state["procurement_result"] = run_procurement_agent()
    return state


def logistics_node(state: SCMState) -> SCMState:
    state["logistics_result"] = run_logistics_agent(
        question=state["query"],
        limit=state.get("limit", 5),
        mode=state.get("mode", "balanced"),
    )
    return state


def communication_node(state: SCMState) -> SCMState:
    order_id = state.get("order_id")
    state["communication_result"] = (
        run_communication_agent(order_id) if order_id
        else "No order_id provided for communication agent."
    )
    return state


def full_pipeline_node(state: SCMState) -> SCMState:
    state["forecast_result"] = run_forecast_agent(state["query"])
    state["inventory_result"] = run_inventory_agent(state["query"])
    state["procurement_result"] = run_procurement_agent(
        extra_instruction=f"Forecast context:\n{state['forecast_result']}"
    )
    state["logistics_result"] = run_logistics_agent(
        question="Create an optimized fulfilment plan for pending orders.",
        limit=state.get("limit", 5),
        mode=state.get("mode", "balanced"),
    )
    if state.get("order_id"):
        state["communication_result"] = run_communication_agent(state["order_id"])
    return state


def finalize(state: SCMState) -> SCMState:
    parts = []
    for key, label in [
        ("forecast_result", "DEMAND FORECAST"),
        ("inventory_result", "INVENTORY STATUS"),
        ("procurement_result", "PROCUREMENT / PURCHASE ORDER"),
        ("logistics_result", "LOGISTICS PLAN"),
        ("communication_result", "CUSTOMER COMMUNICATION"),
    ]:
        if state.get(key):
            parts.append(f"=== {label} ===\n{state[key]}")
    state["final_response"] = "\n\n".join(parts)
    return state


def build_graph():
    graph = StateGraph(SCMState)

    graph.add_node("supervisor", supervisor)
    graph.add_node("demand_forecast", forecast_node)
    graph.add_node("inventory_monitoring", inventory_node)
    graph.add_node("procurement", procurement_node)
    graph.add_node("logistics", logistics_node)
    graph.add_node("communication", communication_node)
    graph.add_node("full_pipeline", full_pipeline_node)
    graph.add_node("finalize", finalize)

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        route_decider,
        {r: r for r in ROUTES},
    )

    for node in ROUTES:
        graph.add_edge(node, "finalize")

    graph.add_edge("finalize", END)

    return graph.compile()


# =====================================================
# CLI RUNNER
# =====================================================

if __name__ == "__main__":
    app = build_graph()

    print("=" * 70)
    print("HexaShop SCM Multi-Agent System (LangGraph)")
    print("Type 'exit' to quit.")
    print("=" * 70)

    while True:
        query = input("\nYou: ").strip()
        if query.lower() in ("exit", "quit"):
            break

        order_id = input("Order ID (optional, press enter to skip): ").strip() or None

        result = app.invoke({
            "query": query,
            "order_id": order_id,
            "limit": 5,
            "mode": "balanced",
        })

        print("\n" + "=" * 70)
        print(f"ROUTE: {result.get('route')}")
        print("=" * 70)
        print(result.get("final_response", "No result generated."))
        print("=" * 70)