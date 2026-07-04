# Logistics & Routing Agent

import re
import os
import json
from pathlib import Path
from uuid import uuid4
from datetime import timedelta

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
# LOGISTICS RISK THRESHOLDS
# =====================================================

# These values can also be changed from .env if needed.
MAX_SHIPMENT_WEIGHT_KG = float(os.getenv("MAX_SHIPMENT_WEIGHT_KG", "100"))
HIGH_SHIPPING_COST_LIMIT = float(os.getenv("HIGH_SHIPPING_COST_LIMIT", "5000"))


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
1. Use ONLY the Shipping API Tool output for carrier, cost, ETA, tracking, delivery risk, and approval details.
2. Do not invent shipping values.
3. Compare carriers based on cost, ETA, coverage, and reliability.
4. Mention exceptions clearly if any order cannot be planned.
5. If Approval Required is True, clearly mention that manager approval is needed before confirming shipment.
6. Return the final answer in a clear manager-friendly format.

Final response should include:
- Summary
- Order-wise fulfilment plan
- Total shipping cost
- Average ETA
- Delivery risk status
- Approval required status
- Key reason for selected carriers
"""


# =====================================================
# INPUT UNDERSTANDING HELPERS
# =====================================================

def validate_mode(mode):
    valid_modes = ["balanced", "cheapest", "fastest"]

    if not mode:
        return "balanced"

    mode = str(mode).lower().strip()

    if mode not in valid_modes:
        return "balanced"

    return mode


def detect_mode_from_question(question):
    question = str(question).lower()

    if "fastest" in question or "quickest" in question or "speed" in question:
        return "fastest"

    if "cheapest" in question or "lowest cost" in question or "low cost" in question:
        return "cheapest"

    if "balanced" in question or "optimize" in question or "optimized" in question or "best" in question:
        return "balanced"

    return None


def detect_limit_from_question(question):
    question = str(question).lower()

    if "all" in question:
        return None

    numbers = re.findall(r"\d+", question)

    if numbers:
        limit = int(numbers[0])

        if limit <= 0:
            return 5

        return limit

    return None


def parse_positive_int(value, default=5):
    try:
        number = int(value)
        return number if number > 0 else default
    except Exception:
        return default


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
    Orders with earlier promised dates are planned first.
    """

    orders = load_orders()

    pending_orders = orders[
        orders["status"].fillna("").str.lower() == "pending"
    ].copy()

    # Convert promised_date to datetime for correct date sorting.
    pending_orders["promised_date_sort"] = pd.to_datetime(
        pending_orders["promised_date"],
        errors="coerce"
    )

    pending_orders = pending_orders.sort_values(
        by="promised_date_sort",
        na_position="last"
    )

    pending_orders = pending_orders.drop(columns=["promised_date_sort"])

    if limit is None:
        return pending_orders

    return pending_orders.head(limit)


def region_is_covered(carrier_regions, order_region):
    """
    Check whether the carrier can deliver to the order region.
    Example:
    carrier_regions = "North,South,West"
    order_region = "South"
    """

    if pd.isna(order_region):
        return False

    regions = [
        region.strip().lower()
        for region in str(carrier_regions).split(",")
    ]

    return str(order_region).strip().lower() in regions


def calculate_shipping_cost(base_cost, cost_per_kg, weight_kg, qty):
    """
    Formula:
    Total Weight = Product Weight × Quantity
    Shipping Cost = Base Cost + Cost Per KG × Total Weight
    """

    total_weight = weight_kg * qty
    cost = base_cost + (cost_per_kg * total_weight)

    return round(cost, 2), round(total_weight, 2)


def check_delay_risk(order_date, promised_date, eta_days):
    """
    Check whether expected delivery date may cross promised date.

    Important:
    This uses order_date + ETA instead of today's date.
    That is safer for demo datasets that may contain older dates.
    """

    try:
        order_dt = pd.to_datetime(order_date, errors="coerce")
        promised_dt = pd.to_datetime(promised_date, errors="coerce")

        if pd.isna(order_dt) or pd.isna(promised_dt):
            return {
                "delivery_risk": "DATE_CHECK_FAILED",
                "expected_delivery_date": "UNKNOWN"
            }

        expected_delivery = order_dt + timedelta(days=int(eta_days))

        if expected_delivery > promised_dt:
            return {
                "delivery_risk": "DELAY_RISK",
                "expected_delivery_date": expected_delivery.date().isoformat()
            }

        return {
            "delivery_risk": "ON_TIME",
            "expected_delivery_date": expected_delivery.date().isoformat()
        }

    except Exception:
        return {
            "delivery_risk": "DATE_CHECK_FAILED",
            "expected_delivery_date": "UNKNOWN"
        }


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
            base_cost=float(carrier["base_cost"]),
            cost_per_kg=float(carrier["cost_per_kg"]),
            weight_kg=weight_kg,
            qty=qty
        )

        available_rates.append(
            {
                "carrier_id": carrier["carrier_id"],
                "carrier_name": carrier["carrier_name"],
                "service_level": carrier["service_level"],
                "cost": cost,
                "eta_days": int(carrier["eta_days"]),
                "reliability": float(carrier["reliability"]),
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

    optimization_mode = validate_mode(optimization_mode)

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


def create_pending_approval_shipment():
    """
    Used when the shipment requires manager approval.
    This avoids confirming shipment before approval.
    """

    return {
        "shipment_status": "PENDING_MANAGER_APPROVAL",
        "tracking_id": "PENDING_MANAGER_APPROVAL",
        "message": "Shipment requires manager approval before confirmation."
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
    6. Checks delivery risk and approval requirement
    7. Creates mock shipment only if no manager approval is needed
    8. Returns complete shipping plan
    """

    optimization_mode = validate_mode(optimization_mode)
    orders = get_pending_orders(limit)
    products = load_products()

    shipping_plan = []
    exceptions = []
    approval_required_count = 0

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

        try:
            qty = int(order["qty"])
            weight_kg = float(product["weight_kg"])
        except Exception:
            exceptions.append(
                {
                    "order_id": order["order_id"],
                    "issue": "Invalid quantity or product weight."
                }
            )
            continue

        if qty <= 0:
            exceptions.append(
                {
                    "order_id": order["order_id"],
                    "issue": "Invalid order quantity. Quantity must be greater than zero."
                }
            )
            continue

        if weight_kg <= 0:
            exceptions.append(
                {
                    "order_id": order["order_id"],
                    "issue": "Invalid product weight. Weight must be greater than zero."
                }
            )
            continue

        # Get carrier rates for the order region and product weight
        rates = get_carrier_rates(
            ship_to_region=order["ship_to_region"],
            weight_kg=weight_kg,
            qty=qty
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

        risk_info = check_delay_risk(
            order_date=order.get("order_date", None),
            promised_date=order["promised_date"],
            eta_days=chosen_carrier["eta_days"]
        )

        delivery_risk = risk_info["delivery_risk"]
        expected_delivery_date = risk_info["expected_delivery_date"]

        approval_required = False
        approval_reasons = []

        if delivery_risk == "DELAY_RISK":
            approval_required = True
            approval_reasons.append(
                "Carrier ETA may exceed promised delivery date."
            )

        if chosen_carrier["total_weight_kg"] > MAX_SHIPMENT_WEIGHT_KG:
            approval_required = True
            approval_reasons.append(
                "High shipment weight / overorder detected."
            )

        if chosen_carrier["cost"] > HIGH_SHIPPING_COST_LIMIT:
            approval_required = True
            approval_reasons.append(
                "High shipping cost detected."
            )

        if approval_required:
            approval_required_count += 1
            shipment = create_pending_approval_shipment()
        else:
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
                "qty": qty,
                "ship_to_region": order["ship_to_region"],
                "order_date": order.get("order_date", "UNKNOWN"),
                "promised_date": order["promised_date"],
                "expected_delivery_date": expected_delivery_date,
                "total_weight_kg": chosen_carrier["total_weight_kg"],
                "chosen_carrier": chosen_carrier["carrier_name"],
                "carrier_id": chosen_carrier["carrier_id"],
                "service_level": chosen_carrier["service_level"],
                "shipping_cost": chosen_carrier["cost"],
                "eta_days": chosen_carrier["eta_days"],
                "reliability": chosen_carrier["reliability"],
                "tracking_id": shipment["tracking_id"],
                "shipment_status": shipment["shipment_status"],
                "delivery_risk": delivery_risk,
                "approval_required": approval_required,
                "approval_reasons": approval_reasons,
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
        "approval_required_count": approval_required_count,
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

    request = str(request).lower().replace(" ", "")

    try:
        parts = request.split(",")

        for part in parts:
            if part.startswith("limit="):
                raw_limit = part.replace("limit=", "")
                limit = None if raw_limit == "all" else parse_positive_int(raw_limit, default=5)

            elif part.startswith("mode="):
                mode = validate_mode(part.replace("mode=", ""))

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
        output.append(f"Approval Required Count: {result['approval_required_count']}")
        output.append("\nORDER WISE PLAN:")

        for item in result["shipping_plan"]:
            approval_reasons = item["approval_reasons"]
            approval_reason_text = "NA" if not approval_reasons else "; ".join(approval_reasons)

            output.append(
                f"""
Order ID: {item['order_id']}
Customer ID: {item['customer_id']}
SKU: {item['sku']}
Product: {item['product_name']}
Quantity: {item['qty']}
Region: {item['ship_to_region']}
Order Date: {item['order_date']}
Promised Date: {item['promised_date']}
Expected Delivery Date: {item['expected_delivery_date']}
Chosen Carrier: {item['chosen_carrier']}
Service Level: {item['service_level']}
Shipping Cost: {item['shipping_cost']}
ETA Days: {item['eta_days']}
Reliability: {item['reliability']}
Total Weight KG: {item['total_weight_kg']}
Delivery Risk: {item['delivery_risk']}
Approval Required: {item['approval_required']}
Approval Reasons: {approval_reason_text}
Shipment Status: {item['shipment_status']}
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

    mode = validate_mode(mode)
    limit = parse_positive_int(limit, default=5) if limit is not None else None

    memory_text = logistic_memory.get_memory()

    task_description = LOGISTICS_TASK_TEMPLATE.format(
        question=question,
        memory=memory_text,
        limit="all" if limit is None else limit,
        mode=mode
    )

    logistics_task = Task(
        description=task_description,

        expected_output="""
A manager-friendly optimized fulfilment plan containing:
summary, order-wise carrier choice, shipping cost, ETA,
tracking ID, total cost, average ETA, delivery risk,
approval required status, approval reasons, and exceptions if any.
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
    print("=" * 70)
    print("HEXA SHOP - LOGISTICS & ROUTING AGENT")
    print("=" * 70)

    question = input("Manager Question: ").strip()

    if not question:
        question = "Create an optimized fulfilment plan for pending orders."

    detected_mode = detect_mode_from_question(question)
    detected_limit = detect_limit_from_question(question)

    if detected_mode:
        print(f"Detected logistics mode from question: {detected_mode}")
        mode = detected_mode
    else:
        mode = input("Choose mode, optional default balanced (balanced / cheapest / fastest): ").strip()
        mode = validate_mode(mode)

    if detected_limit:
        print(f"Detected pending order limit from question: {detected_limit}")
        limit = detected_limit
    elif "all" in question.lower():
        print("Detected pending order limit from question: all")
        limit = None
    else:
        limit_input = input("Pending order limit, optional default 5: ").strip()
        limit = parse_positive_int(limit_input, default=5) if limit_input else 5

    result = run_logistics_agent(
        question=question,
        limit=limit,
        mode=mode
    )

    print("\n" + "=" * 70)
    print("FINAL LOGISTICS AGENT RESPONSE")
    print("=" * 70)
    print(result)


if __name__ == "__main__":
    main()
