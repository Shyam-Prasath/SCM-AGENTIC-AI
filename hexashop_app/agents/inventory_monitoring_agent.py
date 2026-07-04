from __future__ import annotations

import os
import sqlite3
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "scm.sqlite")
CRITICAL_SHORTAGE_LIMIT = int(os.getenv("CRITICAL_SHORTAGE_LIMIT", "50"))

gpt_llm = LLM(
    model=f"azure/{os.getenv('AZURE_OPENAI_DEPLOYMENT')}",
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
    temperature=0.2,
)


def _run_sql(query: str, params: tuple = ()):
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()
    finally:
        conn.close()


@tool
def inventory_db(question: str) -> str:
    """Query inventory database and answer low-stock/reorder questions."""
    question = str(question).lower()
    if "north" in question:
        query = """
            SELECT i.sku, p.product_name, i.warehouse, i.region, i.on_hand, i.reorder_point,
                   i.reorder_qty, (i.reorder_point - i.on_hand) AS shortage
            FROM inventory i JOIN products p ON p.sku = i.sku
            WHERE i.region = 'North' AND i.on_hand < i.reorder_point
            ORDER BY shortage DESC
        """
    elif (
    "below reorder" in question
    or "low stock" in question
    or "replenishment" in question
    or "critical shortage" in question
    or "severe shortage" in question
    or "shortage" in question
    or "stock shortage" in question
):
        query = """
            SELECT i.sku, p.product_name, i.warehouse, i.region, i.on_hand, i.reorder_point,
                   i.reorder_qty, (i.reorder_point - i.on_hand) AS shortage
            FROM inventory i JOIN products p ON p.sku = i.sku
            WHERE i.on_hand < i.reorder_point
            ORDER BY shortage DESC
        """
    else:
        return "Unsupported inventory question. Ask about low stock, reorder levels, replenishment, or SKU profile."

    rows = _run_sql(query)
    if not rows:
        return "No matching inventory records found."
    return "\n".join(
        f"SKU: {r[0]} | Product: {r[1]} | Warehouse: {r[2]} | Region: {r[3]} | "
        f"On Hand: {r[4]} | Reorder Point: {r[5]} | Reorder Qty: {r[6]} | Shortage: {r[7]}"
        for r in rows
    )


@tool
def low_stock_scanner(dummy_input: str = "") -> str:
    """Returns all SKUs below reorder level."""
    query = """
        SELECT i.sku, p.product_name, i.warehouse, i.region, i.on_hand, i.reorder_point,
               i.reorder_qty, (i.reorder_point - i.on_hand) AS shortage
        FROM inventory i JOIN products p ON p.sku = i.sku
        WHERE i.on_hand < i.reorder_point
        ORDER BY shortage DESC
    """
    rows = _run_sql(query)
    if not rows:
        return "No low stock items found."
    return "\n".join(
        f"SKU: {r[0]} | Product: {r[1]} | Warehouse: {r[2]} | Region: {r[3]} | "
        f"On Hand: {r[4]} | Reorder Point: {r[5]} | Reorder Qty: {r[6]} | Shortage: {r[7]}"
        for r in rows
    )


@tool
def sku_profile(sku: str) -> str:
    """Retrieve product information for a SKU."""
    query = """
        SELECT sku, product_name, category, subcategory, brand, unit_price, weight_kg
        FROM products WHERE sku = ?
    """
    rows = _run_sql(query, (str(sku).strip().upper(),))
    if not rows:
        return f"No SKU found: {sku}"
    r = rows[0]
    return (
        f"SKU: {r[0]}\nProduct: {r[1]}\nCategory: {r[2]}\nSubcategory: {r[3]}\n"
        f"Brand: {r[4]}\nUnit Price: ${r[5]}\nWeight: {r[6]} kg"
    )


inventory_monitoring_agent = Agent(
    role="Inventory Monitoring Agent",
    goal="Monitor inventory levels, identify low-stock items, answer inventory questions, and provide replenishment insights.",
    backstory=(
        "You are the Inventory Monitoring Agent for HexaShop. Use only inventory tools for stock numbers. "
        "Never invent values. If information is unavailable, clearly say so."
    ),
    tools=[inventory_db, low_stock_scanner, sku_profile],
    llm=gpt_llm,
    verbose=True,
    allow_delegation=False,
)


def run_inventory_agent(query: str) -> str:
    task = Task(
        description=f"""
        Answer this inventory question:
        {query}

        Rules:
        - Use inventory tools.
        - Never invent stock values.
        - Mention critical shortages if any.
        """,
        expected_output="Grounded inventory answer using actual inventory data.",
        agent=inventory_monitoring_agent,
    )
    crew = Crew(agents=[inventory_monitoring_agent], tasks=[task], verbose=True)
    return str(crew.kickoff())


def inventory_risk_metadata(query: str) -> dict:
    rows = _run_sql("""
        SELECT i.sku, p.product_name, i.warehouse, i.region, i.on_hand, i.reorder_point,
               (i.reorder_point - i.on_hand) AS shortage
        FROM inventory i JOIN products p ON p.sku = i.sku
        WHERE i.on_hand < i.reorder_point
        ORDER BY shortage DESC
    """)
    critical = [r for r in rows if int(r[6]) >= CRITICAL_SHORTAGE_LIMIT]
    return {
        "hil_required": bool(critical),
        "reason": f"{len(critical)} critical shortage item(s) need manager review." if critical else "No critical shortage beyond threshold.",
        "critical_count": len(critical),
        "critical_items": critical[:10],
    }
