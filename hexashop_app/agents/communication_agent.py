from __future__ import annotations

import os
import pandas as pd
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM

load_dotenv()

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CUSTOMERS_PATH = os.path.join(DATA_DIR, "customers.csv")
ORDERS_PATH = os.path.join(DATA_DIR, "orders.csv")

customers_df = pd.read_csv(CUSTOMERS_PATH)
orders_df = pd.read_csv(ORDERS_PATH)

gpt_llm = LLM(
    model=f"azure/{os.getenv('AZURE_OPENAI_DEPLOYMENT')}",
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
    temperature=0.2,
)


def get_customer_details(order_id: str) -> dict:
    order_id = str(order_id).strip().upper()
    order = orders_df[orders_df["order_id"].astype(str).str.upper() == order_id]
    if order.empty:
        return {"error": "Invalid Order ID", "order_id": order_id}
    order_row = order.iloc[0]
    customer = customers_df[customers_df["customer_id"] == order_row["customer_id"]]
    if customer.empty:
        return {"error": "Customer Not Found", "order_id": order_id}
    customer_row = customer.iloc[0]
    return {
        "order_id": order_row["order_id"],
        "customer_id": order_row["customer_id"],
        "customer_name": customer_row["customer_name"],
        "customer_email": customer_row["email"],
        "customer_tier": customer_row["tier"],
        "sku": order_row["sku"],
        "quantity": int(order_row["qty"]),
        "status": order_row["status"],
        "order_date": order_row["order_date"],
        "promised_date": order_row["promised_date"],
        "region": customer_row["region"],
    }


def calculate_priority(status: str, tier: str) -> str:
    status, tier = str(status).upper(), str(tier).upper()
    if status == "CANCELLED":
        return "HIGH"
    if status == "DELAYED":
        return "HIGH" if tier == "PREMIUM" else "MEDIUM"
    if status in ("PENDING", "ALLOCATED"):
        return "MEDIUM"
    return "LOW"


communication_agent = Agent(
    role="Customer Communication Specialist",
    goal="Generate professional customer emails and manager summaries based on order status and priority.",
    backstory=(
        "You are a Senior Customer Communication Specialist at HexaShop. You generate professional, polite, "
        "concise customer updates using only the customer and order details provided. Never fabricate information."
    ),
    llm=gpt_llm,
    verbose=False,
    allow_delegation=False,
)


def _parse_communication_output(output: str):
    subject, email, manager, current = "", "", "", ""
    for line in output.splitlines():
        clean = line.strip()
        if clean.lower().startswith("subject:"):
            current = "subject"
            subject = clean.split(":", 1)[1].strip()
            continue
        if clean.lower().startswith("email:"):
            current = "email"
            remainder = clean.split(":", 1)[1].strip() if ":" in clean else ""
            if remainder:
                email += remainder + "\n"
            continue
        if clean.lower().startswith("manager summary:"):
            current = "manager"
            remainder = clean.split(":", 1)[1].strip() if ":" in clean else ""
            if remainder:
                manager += remainder + "\n"
            continue
        if current == "subject":
            subject += (" " + clean) if clean else ""
        elif current == "email":
            email += clean + "\n"
        elif current == "manager":
            manager += clean + "\n"
    return subject.strip(), email.strip(), manager.strip()


def run_communication_agent(order_id: str, query: str = "") -> dict:
    customer = get_customer_details(order_id)
    if "error" in customer:
        return {
            "text": customer["error"],
            "priority": "UNKNOWN",
            "hil_required": False,
            "reason": customer["error"],
            "customer": customer,
        }

    priority = calculate_priority(customer["status"], customer["customer_tier"])
    prompt = f"""
You are HexaShop's Customer Communication Specialist.

Manager request:
{query}

Customer Name: {customer['customer_name']}
Customer Email: {customer['customer_email']}
Customer Tier: {customer['customer_tier']}
Order ID: {customer['order_id']}
Product SKU: {customer['sku']}
Quantity: {customer['quantity']}
Order Status: {customer['status']}
Order Date: {customer['order_date']}
Promised Date: {customer['promised_date']}
Priority: {priority}

Generate:
1. Subject
2. Professional Customer Email
3. Manager Summary

Rules:
- Keep the email polite and professional.
- If Priority is HIGH, provide Manager Summary.
- Otherwise Manager Summary should be NA.
- Do not invent customer information.
- This is a draft only; do not claim that email was sent.

Return exactly in this format:
Subject:
Email:
Manager Summary:
"""
    task = Task(
        description=prompt,
        expected_output="Subject, customer email draft, and manager summary.",
        agent=communication_agent,
    )
    crew = Crew(agents=[communication_agent], tasks=[task], verbose=False)
    result = str(crew.kickoff())
    subject, email, manager = _parse_communication_output(result)

    text = f"Subject: {subject}\n\nEmail Draft:\n{email}\n\nManager Summary:\n{manager if manager else 'NA'}"
    hil_required = priority == "HIGH"
    return {
        "text": text,
        "priority": priority,
        "hil_required": hil_required,
        "reason": "High priority customer communication requires manager review before sending." if hil_required else "No manager review required.",
        "customer": customer,
    }
