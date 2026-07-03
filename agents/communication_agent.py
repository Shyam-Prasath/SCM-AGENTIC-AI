import os
import pandas as pd

from dotenv import load_dotenv
from crewai import Agent
from crewai import Task, Crew, LLM
from crewai.tools import tool

load_dotenv()


gpt_llm = LLM(
    model=f"azure/{os.getenv('AZURE_OPENAI_DEPLOYMENT')}",
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION")
)

customers_df = pd.read_csv("customers.csv")
orders_df = pd.read_csv("orders.csv")

print("=" * 60)
print("HexaShop AI Customer Communication Agent")
print("=" * 60)

# -------------------------------------------------------
# Tool 1
# Retrieve Customer & Order Details
# -------------------------------------------------------
def get_customer_details(order_id: str) -> dict:
    """
    Retrieve customer and order information using Order ID.

    Args:
        order_id (str): Customer Order ID

    Returns:
        dict:
            order_id
            customer_name
            customer_email
            customer_tier
            sku
            quantity
            status
            order_date
            promised_date
            region
    """

    order = orders_df[
        orders_df["order_id"] == order_id
    ]

    if order.empty:
        return {
            "error": "Invalid Order ID"
        }

    customer = customers_df[
        customers_df["customer_id"] ==
        order.iloc[0]["customer_id"]
    ]

    if customer.empty:
        return {
            "error": "Customer Not Found"
        }

    return {

        "order_id": order.iloc[0]["order_id"],

        "customer_name":
        customer.iloc[0]["customer_name"],

        "customer_email":
        customer.iloc[0]["email"],

        "customer_tier":
        customer.iloc[0]["tier"],

        "sku":
        order.iloc[0]["sku"],

        "quantity":
        int(order.iloc[0]["qty"]),

        "status":
        order.iloc[0]["status"],

        "order_date":
        order.iloc[0]["order_date"],

        "promised_date":
        order.iloc[0]["promised_date"],

        "region":
        customer.iloc[0]["region"]

    }


# -------------------------------------------------------
# Tool 2
# Calculate Communication Priority
# -------------------------------------------------------

def calculate_priority(
    status: str,
    tier: str
) -> str:
    """
    Determine communication priority.

    Args:
        status (str): Order Status
        tier (str): Customer Tier

    Returns:
        HIGH
        MEDIUM
        LOW
    """

    status = status.upper()
    tier = tier.upper()

    if status == "CANCELLED":
        return "HIGH"

    elif status == "DELAYED":

        if tier == "PREMIUM":
            return "HIGH"

        return "MEDIUM"

    elif status == "PENDING":
        return "MEDIUM"

    elif status == "ALLOCATED":
        return "MEDIUM"

    elif status == "SHIPPED":
        return "LOW"

    elif status == "DELIVERED":
        return "LOW"

    return "LOW"


# -------------------------------------------------------
# Customer Communication Agent
# -------------------------------------------------------

communication_agent = Agent(

    role="Customer Communication Specialist",

    goal="""
Generate professional customer
communication based on customer,
order status and business priority.
""",

    backstory="""
You are a Senior Customer
Communication Specialist
working at HexaShop.

You always retrieve customer
information using tools.

You determine the communication
priority before generating
professional customer emails.

Never fabricate customer
information.

Always use the available tools.
""",

    tools=[
        get_customer_details,
        calculate_priority
    ],

    llm=gpt_llm,

    verbose=True,

    allow_delegation=False,
)
# -------------------------------------------------------
# Main Program
# -------------------------------------------------------

while True:

    order_id = input("\nEnter Order ID (or exit): ").strip()

    if order_id.lower() in ["exit", "quit"]:
        print("\nExiting Customer Communication Agent...")
        break

    # ---------------------------------------------
    # Explicit Tool Execution (Hybrid Approach)
    # ---------------------------------------------

    customer = get_customer_details(order_id)

    if "error" in customer:
        print(customer["error"])
        continue

    priority = calculate_priority(
        customer["status"],
        customer["customer_tier"]
    )

    print("\nCustomer Details")
    print("-" * 50)
    print("Customer Name :", customer["customer_name"])
    print("Customer Email:", customer["customer_email"])
    print("Customer Tier :", customer["customer_tier"])
    print("Order ID      :", customer["order_id"])
    print("Product SKU   :", customer["sku"])
    print("Quantity      :", customer["quantity"])
    print("Order Status  :", customer["status"])
    print("Priority      :", priority)

    # ---------------------------------------------
    # Prompt
    # ---------------------------------------------

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

Rules

- Keep the email polite and professional.
- If Priority is HIGH provide Manager Summary.
- Otherwise return NA.

Return exactly in this format.

Subject:
Email:
Manager Summary:
"""

    communication_task = Task(
        description=prompt,
        expected_output="""
Generate

1. Subject
2. Customer Email
3. Manager Summary
""",

        agent=communication_agent

    )
    crew = Crew(

        agents=[communication_agent],

        tasks=[communication_task],

        verbose=True

    )

    print("\nGenerating AI Communication...\n")

    result = crew.kickoff()

    output = str(result)

    subject = ""
    email = ""
    manager = ""

    current = ""

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

    # ---------------------------------------------
    # Display Output
    # ---------------------------------------------

    print("\n" + "=" * 60)
    print("AI GENERATED CUSTOMER COMMUNICATION")
    print("=" * 60)

    print("\nSubject")
    print("-" * 60)
    print(subject)

    print("\nCustomer Email")
    print("-" * 60)
    print(email)

    print("\nManager Summary")
    print("-" * 60)

    if manager.strip() == "":
        print("NA")
    else:
        print(manager)

    print("\n" + "=" * 60)
    print("Communication Generated Successfully")
    print("=" * 60)

    print("\nCustomer Details")
    print("-" * 60)
    print("Customer Name :", customer["customer_name"])
    print("Customer Email:", customer["customer_email"])
    print("Order ID      :", customer["order_id"])
    print("Order Status  :", customer["status"])
    print("Priority      :", priority)

    print("\nReady to send to Notification Service.")
    print("=" * 60)
