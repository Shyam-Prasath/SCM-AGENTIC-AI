
# Logistics & Routing Agent


import os
import json
from pathlib import Path
from uuid import uuid4

import pandas as pd
from dotenv import load_dotenv

from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool


# =====================================================
# LOAD ENVIRONMENT VARIABLES
# =====================================================

load_dotenv()


CURRENT_FILE = Path(__file__).resolve()

POSSIBLE_DATA_DIRS = [
    CURRENT_FILE.parent / "data",
    CURRENT_FILE.parent.parent / "data",
    Path.cwd() / "data",
    Path.cwd().parent / "data",
]

DATA_DIR = None

for path in POSSIBLE_DATA_DIRS:
    if path.exists():
        DATA_DIR = path
        break

if DATA_DIR is None:
    raise FileNotFoundError(
        "Data folder not found. Keep the data folder in your project root."
    )

CARRIERS_FILE = DATA_DIR / "carriers.json"
ORDERS_FILE = DATA_DIR / "orders.csv"
PRODUCTS_FILE = DATA_DIR / "products.csv"


# =====================================================
# SHORT-TERM BUFFER MEMORY
# =====================================================

class LogisticBufferMemory:
    """
    Simple short-term memory for the Logistics Agent.
    It stores only the latest few user questions and agent responses.
    """

    def __init__(self, max_messages=5):
        self.max_messages = max_messages
        self.messages = []

    def add_message(self, role, content):
        self.messages.append(
            {
                "role": role,
                "content": content
            }
        )

        if len(self.messages) > self.max_messages:
            self.messages.pop(0)

    def get_memory(self):
        if not self.messages:
            return "No previous logistics memory."

        memory_text = []

        for message in self.messages:
            memory_text.append(
                f"{message['role'].upper()}: {message['content']}"
            )

        return "\n".join(memory_text)

    def clear(self):
        self.messages = []


# Create memory object
logistic_memory = LogisticBufferMemory(max_messages=5)


# =====================================================
# PROMPT TEMPLATES
# =====================================================

CREWAI_ROLE = "Logistics and Routing Specialist"

CREWAI_GOAL = """
Compare carriers on cost, ETA, region coverage, and reliability.
Produce an optimized fulfilment plan for pending customer orders.
"""

CREWAI_BACKSTORY = """
You are a senior logistics optimizer at HexaShop E-Commerce Pvt. Ltd.

You have 10 years of experience in e-commerce fulfilment,
carrier selection, cost optimization, shipment planning,
and route decision-making.

You are cost-aware, ETA-focused, reliability-obsessed,
and careful about region coverage.

You never invent carrier names, shipping costs, ETA values,
tracking IDs, product weights, or order details.

You always use the Shipping API Tool for shipment planning.
"""

LOGISTICS_TASK_TEMPLATE = """
You are planning fulfilment for HexaShop pending orders.

Manager Question:
{question}

Recent Short-Term Memory:
{memory}

Use the Shipping API Tool with this input:
limit={limit}, mode={mode}

Rules:
1. Use ONLY the Shipping API Tool output for carrier, cost, ETA, and tracking details.
2. Do not invent shipping values.
3. Compare carriers based on cost, ETA, coverage, and reliability.
4. Mention exceptions clearly if any order cannot be planned.
5. Return the final answer in a clear manager-friendly format.

Final response should include:
- Summary
- Order-wise fulfilment plan
- Total shipping cost
- Average ETA
- Key reason for selected carriers
"""


# =====================================================
# DATA LOADING FUNCTIONS
# =====================================================

def load_carriers():
    """
    Load carrier data from carriers.json.
    Carrier data includes cost, ETA, region coverage, and reliability.
    """

    with open(CARRIERS_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def load_orders():
    """
    Load customer orders from orders.csv.
    """

    return pd.read_csv(ORDERS_FILE)


def load_products():
    """
    Load product data from products.csv.
    Product weight is needed for shipping cost calculation.
    """

    return pd.read_csv(PRODUCTS_FILE)


# =====================================================
# SHIPPING BUSINESS LOGIC
# =====================================================

def get_pending_orders(limit=10):
    """
    Select only pending orders because shipped/delivered orders
    do not need fulfilment planning.
    """

    orders = load_orders()

    pending_orders = orders[
        orders["status"].str.lower() == "pending"
    ].copy()

    # Orders with earlier promised dates are planned first
    pending_orders = pending_orders.sort_values("promised_date")

    return pending_orders.head(limit)


def region_is_covered(carrier_regions, order_region):
    """
    Check whether the carrier can deliver to the order region.
    Example:
    carrier_regions = "North,South,West"
    order_region = "South"
    """

    regions = [
        region.strip().lower()
        for region in str(carrier_regions).split(",")
    ]

    return order_region.strip().lower() in regions


def calculate_shipping_cost(base_cost, cost_per_kg, weight_kg, qty):
    """
    Formula:
    Total Weight = Product Weight × Quantity
    Shipping Cost = Base Cost + Cost Per KG × Total Weight
    """

    total_weight = weight_kg * qty
    cost = base_cost + (cost_per_kg * total_weight)

    return round(cost, 2), round(total_weight, 2)


def get_carrier_rates(ship_to_region, weight_kg, qty):
    """
    Get all valid carrier options for a given order.
    It filters carriers by region and calculates cost.
    """

    carriers = load_carriers()
    available_rates = []

    for carrier in carriers:

        # Skip carrier if it does not serve the region
        if not region_is_covered(
            carrier["regions_covered"],
            ship_to_region
        ):
            continue

        cost, total_weight = calculate_shipping_cost(
            base_cost=carrier["base_cost"],
            cost_per_kg=carrier["cost_per_kg"],
            weight_kg=weight_kg,
            qty=qty
        )

        available_rates.append(
            {
                "carrier_id": carrier["carrier_id"],
                "carrier_name": carrier["carrier_name"],
                "service_level": carrier["service_level"],
                "cost": cost,
                "eta_days": carrier["eta_days"],
                "reliability": carrier["reliability"],
                "total_weight_kg": total_weight,
                "regions_covered": carrier["regions_covered"]
            }
        )

    return available_rates


def choose_best_carrier(rates, optimization_mode="balanced"):
    """
    Choose the best carrier based on optimization mode.

    Modes:
    1. cheapest  -> lowest cost
    2. fastest   -> lowest ETA
    3. balanced  -> cost + ETA + reliability
    """

    if not rates:
        return None

    optimization_mode = optimization_mode.lower().strip()

    # Cheapest mode
    if optimization_mode == "cheapest":
        return sorted(
            rates,
            key=lambda rate: (
                rate["cost"],
                rate["eta_days"],
                -rate["reliability"]
            )
        )[0]

    # Fastest mode
    if optimization_mode == "fastest":
        return sorted(
            rates,
            key=lambda rate: (
                rate["eta_days"],
                rate["cost"],
                -rate["reliability"]
            )
        )[0]

    # Balanced mode
    # Lower cost is better
    # Lower ETA is better
    # Higher reliability is better

    costs = [rate["cost"] for rate in rates]
    etas = [rate["eta_days"] for rate in rates]

    min_cost, max_cost = min(costs), max(costs)
    min_eta, max_eta = min(etas), max(etas)

    def normalize(value, minimum, maximum):
        if maximum == minimum:
            return 0
        return (value - minimum) / (maximum - minimum)

    scored_rates = []

    for rate in rates:
        cost_score = normalize(rate["cost"], min_cost, max_cost)
        eta_score = normalize(rate["eta_days"], min_eta, max_eta)
        reliability_score = 1 - rate["reliability"]

        # Balanced weightage:
        # Cost = 40%
        # ETA = 40%
        # Reliability = 20%
        final_score = (
            0.40 * cost_score +
            0.40 * eta_score +
            0.20 * reliability_score
        )

        rate_with_score = rate.copy()
        rate_with_score["optimization_score"] = round(final_score, 4)
        scored_rates.append(rate_with_score)

    return sorted(
        scored_rates,
        key=lambda rate: rate["optimization_score"]
    )[0]


def create_mock_shipment(order_id, carrier_id):
    """
    Create a fake/mock shipment.
    No real shipment is created.
    This is only for capstone demo.
    """

    tracking_id = f"TRK-{order_id}-{carrier_id}-{str(uuid4())[:8].upper()}"

    return {
        "shipment_status": "CREATED",
        "tracking_id": tracking_id,
        "message": "Mock shipment created successfully."
    }


def build_shipping_plan(limit=10, optimization_mode="balanced"):
    """
    Main business function.

    It:
    1. Reads pending orders
    2. Gets product weight
    3. Finds valid carriers
    4. Calculates carrier cost
    5. Chooses best carrier
    6. Creates mock shipment
    7. Returns complete shipping plan
    """

    orders = get_pending_orders(limit)
    products = load_products()

    shipping_plan = []
    exceptions = []

    for _, order in orders.iterrows():

        # Find product details using SKU
        product_row = products[products["sku"] == order["sku"]]

        if product_row.empty:
            exceptions.append(
                {
                    "order_id": order["order_id"],
                    "issue": f"Product not found for SKU {order['sku']}"
                }
            )
            continue

        product = product_row.iloc[0]

        # Get carrier rates for the order region and product weight
        rates = get_carrier_rates(
            ship_to_region=order["ship_to_region"],
            weight_kg=float(product["weight_kg"]),
            qty=int(order["qty"])
        )

        if not rates:
            exceptions.append(
                {
                    "order_id": order["order_id"],
                    "issue": f"No carrier available for region {order['ship_to_region']}"
                }
            )
            continue

        # Choose carrier based on selected optimization mode
        chosen_carrier = choose_best_carrier(
            rates=rates,
            optimization_mode=optimization_mode
        )

        # Create mock shipment
        shipment = create_mock_shipment(
            order_id=order["order_id"],
            carrier_id=chosen_carrier["carrier_id"]
        )

        shipping_plan.append(
            {
                "order_id": order["order_id"],
                "customer_id": order["customer_id"],
                "sku": order["sku"],
                "product_name": product["product_name"],
                "qty": int(order["qty"]),
                "ship_to_region": order["ship_to_region"],
                "promised_date": order["promised_date"],
                "total_weight_kg": chosen_carrier["total_weight_kg"],
                "chosen_carrier": chosen_carrier["carrier_name"],
                "carrier_id": chosen_carrier["carrier_id"],
                "service_level": chosen_carrier["service_level"],
                "shipping_cost": chosen_carrier["cost"],
                "eta_days": chosen_carrier["eta_days"],
                "reliability": chosen_carrier["reliability"],
                "tracking_id": shipment["tracking_id"],
                "optimization_mode": optimization_mode
            }
        )

    total_cost = round(
        sum(item["shipping_cost"] for item in shipping_plan),
        2
    )

    average_eta = round(
        sum(item["eta_days"] for item in shipping_plan) / len(shipping_plan),
        2
    ) if shipping_plan else 0

    return {
        "optimization_mode": optimization_mode,
        "total_orders_planned": len(shipping_plan),
        "total_shipping_cost": total_cost,
        "average_eta_days": average_eta,
        "shipping_plan": shipping_plan,
        "exceptions": exceptions
    }


# =====================================================
# CREWAI TOOL
# =====================================================

@tool("Shipping API Tool")
def shipping_api_tool(request: str) -> str:
    """
    CrewAI tool used by the Logistics & Routing Agent.

    Input examples:
    - limit=5, mode=balanced
    - limit=10, mode=cheapest
    - limit=3, mode=fastest
    """

    limit = 5
    mode = "balanced"

    request = request.lower().replace(" ", "")

    try:
        parts = request.split(",")

        for part in parts:
            if part.startswith("limit="):
                limit = int(part.replace("limit=", ""))

            elif part.startswith("mode="):
                mode = part.replace("mode=", "")

        result = build_shipping_plan(
            limit=limit,
            optimization_mode=mode
        )

        output = []

        output.append("LOGISTICS SHIPPING PLAN")
        output.append(f"Optimization Mode: {result['optimization_mode']}")
        output.append(f"Orders Planned: {result['total_orders_planned']}")
        output.append(f"Total Shipping Cost: {result['total_shipping_cost']}")
        output.append(f"Average ETA Days: {result['average_eta_days']}")
        output.append("\nORDER WISE PLAN:")

        for item in result["shipping_plan"]:
            output.append(
                f"""
Order ID: {item['order_id']}
Customer ID: {item['customer_id']}
SKU: {item['sku']}
Product: {item['product_name']}
Quantity: {item['qty']}
Region: {item['ship_to_region']}
Chosen Carrier: {item['chosen_carrier']}
Service Level: {item['service_level']}
Shipping Cost: {item['shipping_cost']}
ETA Days: {item['eta_days']}
Reliability: {item['reliability']}
Tracking ID: {item['tracking_id']}
"""
            )

        if result["exceptions"]:
            output.append("\nEXCEPTIONS:")

            for exception in result["exceptions"]:
                output.append(str(exception))

        return "\n".join(output)

    except Exception as e:
        return f"Shipping API Error: {str(e)}"


# =====================================================
# LLM SETUP
# =====================================================

llm = LLM(
    model=f"azure/{os.getenv('AZURE_OPENAI_DEPLOYMENT')}",
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_KEY")
)


# =====================================================
# CREWAI LOGISTICS AGENT
# =====================================================

logistics_routing_agent = Agent(
    role=CREWAI_ROLE,

    goal=CREWAI_GOAL,

    backstory=CREWAI_BACKSTORY,

    tools=[
        shipping_api_tool
    ],

    llm=llm,

    verbose=False,

    allow_delegation=False
)


def run_logistics_agent(question, limit=5, mode="balanced"):
    """
    Runs the complete CrewAI Logistics & Routing Agent.
    """

    memory_text = logistic_memory.get_memory()

    task_description = LOGISTICS_TASK_TEMPLATE.format(
        question=question,
        memory=memory_text,
        limit=limit,
        mode=mode
    )

    logistics_task = Task(
        description=task_description,

        expected_output="""
A manager-friendly optimized fulfilment plan containing:
summary, order-wise carrier choice, shipping cost, ETA,
tracking ID, total cost, average ETA, and exceptions if any.
""",

        agent=logistics_routing_agent
    )

    logistics_crew = Crew(
        agents=[
            logistics_routing_agent
        ],

        tasks=[
            logistics_task
        ],

        process=Process.sequential,

        verbose=False
    )

    result = logistics_crew.kickoff()

    logistic_memory.add_message("user", question)
    logistic_memory.add_message("assistant", str(result))

    return result


# =====================================================
# CONSOLE RUNNER
# =====================================================

def main():
    """
    Console entry point.
    Run this file directly to test the Logistics & Routing Agent.
    """

    print("=" * 70)
    print("HEXA SHOP - LOGISTICS & ROUTING AGENT")
    print("=" * 70)

    question = input("Manager Question: ")
    limit = input("How many pending orders do you want to plan? ")
    mode = input("Choose mode (balanced / cheapest / fastest): ")

    if not question.strip():
        question = "Create an optimized fulfilment plan for pending orders."

    if not limit.strip():
        limit = 5

    if not mode.strip():
        mode = "balanced"

    result = run_logistics_agent(
        question=question,
        limit=int(limit),
        mode=mode
    )

    print("\n" + "=" * 70)
    print("FINAL LOGISTICS AGENT RESPONSE")
    print("=" * 70)
    print(result)


if __name__ == "__main__":
    main()