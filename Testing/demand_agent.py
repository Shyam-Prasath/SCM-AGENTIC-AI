import os
import pandas as pd
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool
from config import SALES_HISTORY_FILE, INVENTORY_FILE

load_dotenv()

gpt_llm = LLM(
    model=f"azure/{os.getenv('AZURE_OPENAI_DEPLOYMENT')}",
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    temperature=0.3
)

# Load dataframes using paths from config
sales_df = pd.read_csv(SALES_HISTORY_FILE)
inventory_df = pd.read_csv(INVENTORY_FILE)

@tool
def forecast_model(sku: str, days: int) -> dict:
    """
    Predict near-term demand for a SKU using the last 7 days of sales history.

    Args:
        sku (str): The Stock Keeping Unit (SKU) of the product.
        days (int): Number of future days for which demand should be predicted.

    Returns:
        dict: A dictionary containing:
            - sku (str): Product SKU.
            - forecast_days (int): Number of forecast days.
            - predicted_demand (int): Estimated demand for the given period.
    """
    sku_sales = sales_df[sales_df["sku"] == sku]
    if sku_sales.empty:
        return {"error": "SKU not found"}

    last_7_days = sku_sales.tail(7)
    avg_daily_sales = last_7_days["units_sold"].mean()
    predicted_demand = round(avg_daily_sales * days)

    return {
        "sku": sku,
        "forecast_days": days,
        "predicted_demand": predicted_demand
    }

@tool
def inventory_db(sku: str) -> dict:
    """
    Retrieve inventory information for a given SKU and identify inventory risk.

    Args:
        sku (str): The Stock Keeping Unit (SKU) of the product.

    Returns:
        dict: A dictionary containing:
            - sku (str): Product SKU.
            - warehouse (str): Warehouse location.
            - on_hand (int): Current available stock.
            - reorder_point (int): Reorder threshold.
            - reorder_qty (int): Recommended reorder quantity.
            - risk (str): Stock-Out Risk, Overstock Risk, or Normal.
    """
    item = inventory_df[
        (inventory_df["sku"] == sku) &
        (inventory_df["warehouse"] == "North DC")
    ]
    if item.empty:
        return {"error": "SKU not found"}

    row = item.iloc[0]
    if row["on_hand"] < row["reorder_point"]:
        risk = "Stock-Out Risk"
    elif row["on_hand"] > row["reorder_qty"]:
        risk = "Overstock Risk"
    else:
        risk = "Normal"

    return {
        "sku": row["sku"],
        "warehouse": row["warehouse"],
        "on_hand": int(row["on_hand"]),
        "reorder_point": int(row["reorder_point"]),
        "reorder_qty": int(row["reorder_qty"]),
        "risk": risk
    }
    
forecasting_agent = Agent(
    role="Demand Forecasting Analyst",
    goal="""
Predict near-term demand per SKU from sales history
and identify stock-out or overstock risk.
""",
    backstory="""
You are a senior demand forecasting analyst at HexaShop.

You analyze historical sales,
forecast demand,
compare it with inventory,
and recommend replenishment actions.

You always use forecast_model and inventory_db.
Never fabricate values.
""",
    tools=[
        forecast_model,
        inventory_db
    ],
    llm=gpt_llm,
    verbose=True,
    allow_delegation=False,
)

# Protected testing block to prevent blocking on import
if __name__ == "__main__":
    while True:
        user_query = input("Ask the Demand Forecasting Agent: ")
        if user_query.lower() in ["exit", "quit"]:
            break

        forecast_task = Task(
            description=user_query,
            expected_output="""
Forecast demand, compare inventory,
identify inventory risk and provide recommendation.
""",
            agent=forecasting_agent
        )

        crew = Crew(
            agents=[forecasting_agent],
            tasks=[forecast_task],
            verbose=True
        )

        result = crew.kickoff()
        print(result)
