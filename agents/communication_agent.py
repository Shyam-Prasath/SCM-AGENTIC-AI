import os
import pandas as pd
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool

load_dotenv()

gpt_llm = LLM(
    model=f"azure/{os.getenv('AZURE_OPENAI_DEPLOYMENT')}",
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    temperature=0.3
)

customers_df = pd.read_csv("customers.csv")
orders_df = pd.read_csv("orders.csv")

@tool
def get_customer_details(order_id: str) -> dict:
    """Retrieve customer and order details using Order ID."""
    order = orders_df[orders_df["order_id"] == order_id]
    if order.empty:
        return {"error": "Invalid Order ID"}

    customer = customers_df[
        customers_df["customer_id"] == order.iloc[0]["customer_id"]
    ]
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
        "region": customer.iloc[0]["region"]
    }

@tool
def get_priority(status: str, tier: str) -> str:
    """Determine communication priority."""
    status = status.upper()
    tier = tier.upper()

    if status == "CANCELLED":
        return "HIGH"
    if status == "DELAYED":
        return "HIGH" if tier == "PREMIUM" else "MEDIUM"
    if status == "PENDING":
        return "MEDIUM"
    return "LOW"

communication_agent = Agent(
    role="Customer Communication Specialist",
    goal="Generate professional customer communications.",
    backstory="""
You are a senior Customer Communication Specialist at HexaShop.
Always use tools to retrieve customer details and determine priority.
Never fabricate information.
""",
    tools=[get_customer_details, get_priority],
    llm=gpt_llm,
    verbose=True,
    allow_delegation=False,
)

print("=" * 60)
print("HexaShop AI Customer Communication Agent")
print("=" * 60)

while True:
    order_id = input("\nEnter Order ID (or exit): ").strip()

    if order_id.lower() in ["exit", "quit"]:
        break

    task = Task(
        description=f"""
Generate customer communication for Order ID {order_id}.

Use get_customer_details.
Use get_priority.

Generate:
1. Subject
2. Customer Email
3. Manager Summary (NA if priority is not HIGH)
""",
        expected_output="""
Subject
Customer Email
Manager Summary
""",
        agent=communication_agent,
    )

    crew = Crew(
        agents=[communication_agent],
        tasks=[task],
        verbose=True,
    )

    result = crew.kickoff()

    print("\n" + "=" * 60)
    print("AI GENERATED COMMUNICATION")
    print("=" * 60)
    print(result)
