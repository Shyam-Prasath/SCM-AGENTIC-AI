import sqlite3

from crewai import Agent
from crewai.tools import tool

DB_PATH = "data/scm.sqlite"


# =====================================================
# TOOL 1
# Inventory Q&A Tool (UC-1)
# =====================================================

@tool("Inventory Database Tool")
def inventory_db_tool(question: str) -> str:
    """
    Answer inventory-related questions using SCM database.
    """

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    question = question.lower()

    try:

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
                "Ask about low stock items or reorder levels."
            )

        cursor.execute(query)

        rows = cursor.fetchall()

        if not rows:
            return "No matching inventory records found."

        result = []

        for row in rows:

            result.append(
                f"""
SKU: {row[0]}
Product: {row[1]}
Warehouse: {row[2]}
On Hand: {row[3]}
Reorder Point: {row[4]}
Reorder Quantity: {row[5]}
"""
            )

        return "\n".join(result)

    except Exception as e:

        return f"Database Error: {str(e)}"

    finally:
        conn.close()


# =====================================================
# TOOL 2
# Low Stock Scanner
# Used by Procurement Agent later
# =====================================================

@tool("Low Stock Scanner")
def get_low_stock_items(dummy_input: str = "") -> str:
    """
    Return all SKUs below reorder point,
    prioritized by shortage severity.
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

        output = []

        rank = 1

        for row in rows:

            output.append(
                f"""
Priority: {rank}
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

            rank += 1

        return "\n".join(output)

    except Exception as e:

        return f"Database Error: {str(e)}"

    finally:

        conn.close()


# =====================================================
# TOOL 3
# SKU Profile Lookup
# Useful for inventory investigations
# =====================================================

@tool("SKU Profile Lookup")
def sku_profile_tool(sku: str) -> str:
    """
    Return complete SKU information.
    """

    conn = sqlite3.connect(DB_PATH)

    cursor = conn.cursor()

    try:

        query = """
        SELECT
            p.sku,
            p.product_name,
            p.category,
            p.subcategory,
            p.brand,
            p.unit_price,
            p.weight_kg
        FROM products p
        WHERE p.sku = ?
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

    except Exception as e:

        return f"Database Error: {str(e)}"

    finally:

        conn.close()


# =====================================================
# CREWAI AGENT
# =====================================================

inventory_monitoring_agent = Agent(
    role="Inventory Monitoring Specialist",

    goal="""
Monitor inventory levels across warehouses,
identify products below reorder thresholds,
prioritize replenishment requirements,
answer inventory-related business questions,
and provide accurate inventory insights
using the Inventory Database.
""",

    backstory="""
You are a senior inventory analyst at HexaShop.

Your responsibility is to continuously monitor
stock levels across all warehouses and identify
potential inventory risks before they impact customers.

You specialize in:

- Inventory monitoring
- Reorder analysis
- SKU investigations
- Stock shortage prioritization
- Inventory reporting

You always use data from the Inventory Database Tool.
You never assume inventory values or fabricate numbers.

All answers must be grounded in actual inventory records.
""",

    tools=[
        inventory_db_tool,
        get_low_stock_items,
        sku_profile_tool
    ],

    verbose=True,

    allow_delegation=False,
)