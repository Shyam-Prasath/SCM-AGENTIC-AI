import os
import pandas as pd

from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool

# ---------------------------------------------------
# Load Environment Variables
# ---------------------------------------------------

load_dotenv()

gpt_llm = LLM(
    model=f"azure/{os.getenv('AZURE_OPENAI_DEPLOYMENT')}",
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION")
)

# ---------------------------------------------------
# Load CSV Files
# ---------------------------------------------------

customers_df = pd.read_csv("customers.csv")
orders_df = pd.read_csv("orders.csv")

print("=" * 60)
print("HexaShop AI Customer Communication Agent")
print("=" * 60)


# ---------------------------------------------------
# Tool 1 : Retrieve Customer Details
# ---------------------------------------------------

@tool("Get Customer Details")
def get_customer_details(order_id: str) -> str:
    """
    Retrieve customer and order details using Order ID.
    """

    order = orders_df[
        orders_df["order_id"] == order_id
    ]

    if order.empty:
        return "Invalid Order ID"

    customer = customers_df[
        customers_df["customer_id"] ==
        order.iloc[0]["customer_id"]
    ]

    if customer.empty:
        return "Customer Not Found"

    return f"""
Customer Name : {customer.iloc[0]['customer_name']}
Customer Email : {customer.iloc[0]['email']}
Customer Tier : {customer.iloc[0]['tier']}
Region : {customer.iloc[0]['region']}

Order ID : {order.iloc[0]['order_id']}
Product SKU : {order.iloc[0]['sku']}
Quantity : {order.iloc[0]['qty']}
Order Status : {order.iloc[0]['status']}
Order Date : {order.iloc[0]['order_date']}
Promised Date : {order.iloc[0]['promised_date']}
"""


# ---------------------------------------------------
# Business Logic
# ---------------------------------------------------

def calculate_priority(status: str, tier: str):

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


# ---------------------------------------------------
# Agent
# ---------------------------------------------------

communication_agent = Agent(

    role="Customer Communication Specialist",

    goal="Generate professional customer emails.",

    backstory="""
You are a professional customer communication expert.
Generate only the final response.
Do not use tools.
""",

    llm=gpt_llm,

    verbose=False,

    allow_delegation=False
)
# ---------------------------------------------------
# Main Program
# ---------------------------------------------------

while True:

    order_id = input("\nEnter Order ID (or exit): ").strip()

    if order_id.lower() in ["exit", "quit"]:
        print("\nThank you for using HexaShop AI Communication Agent.")
        break

    # ---------------------------------------------
    # Fetch Customer & Order Details
    # ---------------------------------------------

    order = orders_df[
        orders_df["order_id"] == order_id
    ]

    if order.empty:
        print("Invalid Order ID")
        continue

    customer = customers_df[
        customers_df["customer_id"] ==
        order.iloc[0]["customer_id"]
    ]

    if customer.empty:
        print("Customer Not Found")
        continue

    priority = calculate_priority(
        order.iloc[0]["status"],
        customer.iloc[0]["tier"]
    )

    print("\nCustomer Details")
    print("-" * 60)
    print("Customer Name :", customer.iloc[0]["customer_name"])
    print("Customer Email:", customer.iloc[0]["email"])
    print("Customer Tier :", customer.iloc[0]["tier"])
    print("Order ID      :", order.iloc[0]["order_id"])
    print("Product SKU   :", order.iloc[0]["sku"])
    print("Quantity      :", order.iloc[0]["qty"])
    print("Order Status  :", order.iloc[0]["status"])
    print("Priority      :", priority)

    prompt = f"""
You are HexaShop's AI Customer Communication Specialist.

Customer Name : {customer.iloc[0]["customer_name"]}
Customer Email : {customer.iloc[0]["email"]}
Customer Tier : {customer.iloc[0]["tier"]}

Order ID : {order.iloc[0]["order_id"]}
SKU : {order.iloc[0]["sku"]}
Quantity : {order.iloc[0]["qty"]}
Order Status : {order.iloc[0]["status"]}
Priority : {priority}

Generate a professional response.

Rules:

1. Write a meaningful email subject.
2. Write a professional customer email.
3. If Priority is HIGH generate a short Manager Summary.
4. Otherwise Manager Summary should be NA.
5. Do not invent customer information.
6. Keep the email concise and professional.

Return ONLY in this format.

Subject:
Email:
Manager Summary:
"""

    communication_task = Task(

    description=prompt,

    expected_output="""
Return ONLY this format.

Subject:
Email:
Manager Summary:
""",

    agent=communication_agent
)

    crew = Crew(

        agents=[communication_agent],

        tasks=[communication_task],

        verbose=False
    )

    print("\nGenerating AI Communication...\n")

    result = crew.kickoff()

    output = str(result)

    subject = ""
email = ""
manager = ""

current = None

for line in output.splitlines():

    line = line.strip()

    if line.lower().startswith("subject:"):
        current = "subject"
        subject = line.split(":", 1)[1].strip()
        continue

    elif line.lower().startswith("email:"):
        current = "email"
        email = line.split(":", 1)[1].strip()
        continue

    elif line.lower().startswith("manager summary:"):
        current = "manager"
        manager = line.split(":", 1)[1].strip()
        continue

    if current == "subject":
        subject += "\n" + line

    elif current == "email":
        email += "\n" + line

    elif current == "manager":
        manager += "\n" + line


    print("\n" + "=" * 60)
    print("Email")
    print("=" * 60)

    print("\nSubject",subject.strip())
    print("-" * 60)
    print(email.strip())

    print("\nManager Summary")
    print("-" * 60)

    if manager.strip() == "":
        print("NA")
    else:
        print(manager.strip())

    print("\n" + "=" * 60)
    print("Communication Generated Successfully")
    print("=" * 60)

    print("\nReady to send notification.")
