import os
import pandas as pd
from dotenv import load_dotenv
from typing import TypedDict

from langgraph.graph import StateGraph, START, END
from langchain_openai import AzureChatOpenAI


load_dotenv()

llm = AzureChatOpenAI(
    api_version="2024-12-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT")
)

class CommunicationState(TypedDict):
    order_id: str
    customer_name: str
    customer_email: str
    customer_tier: str
    sku: str
    quantity: int
    order_status: str
    priority: str
    email_subject: str
    email_body: str
    manager_summary: str

customers_df = pd.read_csv("customers.csv")
orders_df = pd.read_csv("orders.csv")

print("="*60)
print("HexaShop AI Customer Communication Agent")
print("="*60)
# print("Customers Loaded :", len(customers_df))
# print("Orders Loaded    :", len(orders_df))

def get_customer(order_id: str):

    order = orders_df[orders_df["order_id"] == order_id]

    if order.empty:
        print("Invalid Order ID")
        return None

    customer = customers_df[
        customers_df["customer_id"] == order.iloc[0]["customer_id"]
    ]

    if customer.empty:
        print("Customer Not Found")
        return None

    return {
        "order_id": order.iloc[0]["order_id"],
        "customer_name": customer.iloc[0]["customer_name"],
        "customer_email": customer.iloc[0]["email"],
        "customer_tier": customer.iloc[0]["tier"],
        "sku": order.iloc[0]["sku"],
        "quantity": order.iloc[0]["qty"],
        "order_status": order.iloc[0]["status"],
        "order_date": order.iloc[0]["order_date"],
        "promised_date": order.iloc[0]["promised_date"],
        "region": customer.iloc[0]["region"]
    }

def get_priority(status, tier):

    status = str(status).upper()
    tier = str(tier).upper()

    if status == "CANCELLED":
        return "HIGH"

    elif status == "DELAYED":
        if tier == "PREMIUM":
            return "HIGH"
        return "MEDIUM"

    elif status == "PENDING":
        return "MEDIUM"

    elif status == "SHIPPED":
        return "LOW"

    elif status == "DELIVERED":
        return "LOW"

    return "LOW"


def communication_agent(state: CommunicationState):
    customer = get_customer(state["order_id"])

    if customer is None:
        return {}

    priority = get_priority(
        customer["order_status"],
        customer["customer_tier"]
    )

    print("Customer Name :", customer["customer_name"])
    print("Customer Tier :", customer["customer_tier"])
    print("Customer Email:", customer["customer_email"])
    print("Order ID      :", customer["order_id"])
    print("Product SKU   :", customer["sku"])
    print("Quantity      :", customer["quantity"])
    print("Order Status  :", customer["order_status"])
    print("Priority      :", priority)

    print("\nGenerating AI Communication...\n")

    prompt = f"""
You are a customer communication agent.

Customer:
Name: {customer["customer_name"]}
Tier: {customer["customer_tier"]}
Order ID: {customer["order_id"]}
SKU: {customer["sku"]}
Qty: {customer["quantity"]}
Status: {customer["order_status"]}
Priority: {priority}

Use the order status to decide the message.

Format:
Subject:
Email:
Manager Summary:
"""

    response = llm.invoke(prompt)

    output = response.content

    subject = ""
    email = ""
    manager = ""

    current = ""

    for line in output.splitlines():

        line = line.strip()

        if line.startswith("Subject"):
            current = "subject"
            continue

        elif line.startswith("Email"):
            current = "email"
            continue

        elif line.startswith("Manager Summary"):
            current = "manager"
            continue

        if current == "subject":
            subject += line + "\n"

        elif current == "email":
            email += line + "\n"

        elif current == "manager":
            manager += line + "\n"

   

    print("\nEmail")
    print("--------------------------------------")
    print("Subject: ", subject)
    print("--------------------------------------")
    print(email)

    print("\nManager Summary")
    print("--------------------------------------")
    print(manager)

    return {

        "customer_name": customer["customer_name"],

        "customer_email": customer["customer_email"],

        "customer_tier": customer["customer_tier"],

        "sku": customer["sku"],

        "quantity": customer["quantity"],

        "order_status": customer["order_status"],

        "priority": priority,

        "email_subject": subject,

        "email_body": email,

        "manager_summary": manager

    }

communication_graph = StateGraph(CommunicationState)

communication_graph.add_node(
    "Communication Agent",
    communication_agent
)

communication_graph.add_edge(
    START,
    "Communication Agent"
)

communication_graph.add_edge(
    "Communication Agent",
    END
)

communicationAgent = communication_graph.compile()

if __name__ == "__main__":

    order_number = input(
        "\nEnter Order ID : "
    ).strip()

    try:

        response = communicationAgent.invoke(

            {

                "order_id": order_number,

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
    except Exception as ex:

        print("\nApplication Error")

        print(ex)
