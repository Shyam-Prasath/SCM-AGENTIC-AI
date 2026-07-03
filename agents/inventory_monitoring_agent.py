import os
import sqlite3

from dotenv import load_dotenv

from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool

# =====================================================
# Load Environment Variables
# =====================================================

load_dotenv()

# =====================================================
# Azure OpenAI LLM
# =====================================================

gpt_llm = LLM(
    model=f"azure/{os.getenv('AZURE_OPENAI_DEPLOYMENT')}",
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    temperature=0.2
)

# =====================================================
# Database Configuration
# =====================================================

DB_PATH = "data/scm.sqlite"

# =====================================================
# TOOL 1
# Inventory Database Tool
# =====================================================

@tool
def inventory_db(question: str) -> str:
    """
    Query inventory database and answer inventory questions.

    Example:
    - Which SKUs are below reorder level in the North warehouse?
    - Show all low stock products.
    """

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:

        question = question.lower()

        # UC-1

        if (
            "below reorder" in question
            and "north" in question
        ):

            query = """
            SELECT
                i.sku,
                p.product_name,
                i.warehouse,
                i.on_hand,
                i.reorder_point,
                i.reorder_qty
            FROM inventory i
            JOIN products p
                ON p.sku = i.sku
            WHERE i.region = 'North'
            AND i.on_hand < i.reorder_point
            ORDER BY
                (i.reorder_point - i.on_hand) DESC
            """

        elif (
            "below reorder" in question
            or "low stock" in question
        ):

            query = """
            SELECT
                i.sku,
                p.product_name,
                i.warehouse,
                i.on_hand,
                i.reorder_point,
                i.reorder_qty
            FROM inventory i
            JOIN products p
                ON p.sku = i.sku
            WHERE i.on_hand < i.reorder_point
            ORDER BY
                (i.reorder_point - i.on_hand) DESC
            """

        else:

            return (
                "Unsupported inventory question. "
                "Ask about low stock or reorder levels."
            )

        cursor.execute(query)

        rows = cursor.fetchall()

        if not rows:
            return "No matching inventory records found."

        output = []

        for row in rows:

            output.append(
                f"""
SKU: {row[0]}
Product: {row[1]}
Warehouse: {row[2]}
On Hand: {row[3]}
Reorder Point: {row[4]}
Reorder Quantity: {row[5]}
"""
            )

        return "\n".join(output)

    except Exception as ex:

        return f"Database Error: {str(ex)}"

    finally:

        conn.close()


# =====================================================
# TOOL 2
# Low Stock Scanner
# =====================================================

@tool
def low_stock_scanner(dummy_input: str = "") -> str:
    """
    Returns all SKUs below reorder level.
    """

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:

        query = """
        SELECT
            i.sku,
            p.product_name,
            i.warehouse,
            i.region,
            i.on_hand,
            i.reorder_point,
            i.reorder_qty,
            (i.reorder_point - i.on_hand) AS shortage
        FROM inventory i
        JOIN products p
            ON p.sku = i.sku
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
                f"""
SKU: {row[0]}
Product: {row[1]}
Warehouse: {row[2]}
Region: {row[3]}
On Hand: {row[4]}
Reorder Point: {row[5]}
Reorder Qty: {row[6]}
Shortage: {row[7]}
"""
            )

        return "\n".join(result)

    except Exception as ex:

        return f"Database Error: {str(ex)}"

    finally:

        conn.close()


# =====================================================
# TOOL 3
# SKU Lookup
# =====================================================

@tool
def sku_profile(sku: str) -> str:
    """
    Retrieve product information for a SKU.
    """

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:

        query = """
        SELECT
            sku,
            product_name,
            category,
            subcategory,
            brand,
            unit_price,
            weight_kg
        FROM products
        WHERE sku = ?
        """

        cursor.execute(query, (sku,))

        row = cursor.fetchone()

        if not row:
            return f"No SKU found: {sku}"

        return f"""
SKU: {row[0]}
Product: {row[1]}
Category: {row[2]}
Subcategory: {row[3]}
Brand: {row[4]}
Unit Price: ${row[5]}
Weight: {row[6]} kg
"""

    except Exception as ex:

        return f"Database Error: {str(ex)}"

    finally:

        conn.close()


# =====================================================
# INVENTORY AGENT
# =====================================================

inventory_monitoring_agent = Agent(

    role="Inventory Monitoring Agent",

    goal="""
Monitor inventory levels,
identify low-stock items,
answer inventory-related questions,
and provide replenishment insights.
""",

    backstory="""
You are the Inventory Monitoring Agent for HexaShop.

Use ONLY the inventory_db tool for stock numbers.

Never invent values.

If inventory information is unavailable,
clearly say so.

All responses must be grounded in database results.
""",

    tools=[
        inventory_db,
        low_stock_scanner,
        sku_profile
    ],

    llm=gpt_llm,

    verbose=True,

    allow_delegation=False
)

# =====================================================
# LOCAL TEST
# =====================================================

if __name__ == "__main__":

    while True:

        user_query = input(
            "\nAsk Inventory Agent: "
        )

        if user_query.lower() in [
            "exit",
            "quit"
        ]:
            break

        inventory_task = Task(

            description=f"""
            Answer the following inventory question.

            Question:
            {user_query}

            Rules:
            - Use Inventory Database Tool.
            - Never invent stock values.
            - Use actual database values.
            """,

            expected_output="""
            Grounded inventory answer
            using actual inventory data.
            """,

            agent=inventory_monitoring_agent
        )

        crew = Crew(
            agents=[inventory_monitoring_agent],
            tasks=[inventory_task],
            verbose=True
        )

        result = crew.kickoff()

        print("\n")
        print("=" * 60)
        print("FINAL ANSWER")
        print("=" * 60)
        print(result)