import json
import pandas as pd
from langchain.tools import tool

cat="data/supplier_catalog.json"
sup="data/suppliers.csv"

@tool
def supplier_tool(sku: str, quantity: int) -> dict:
    """
    Finds the best supplier for the given SKU and qunatity.
    Args:
        sku(str): Product SKU 
        qunatity(int): Quantity of the product
    Returns:
        str: Supplier name and price for the given SKU and quantity.
    """

    with open(cat, "r") as f:
        catalog = json.load(f)
    suppliers = pd.read_csv(sup)

    match=[
        item for item in catalog if item["sku"] == sku and item["available_qty"] >= quantity
    ]

    if not match:
        return {"error": "No supplier found for the given SKU and quantity."}

    catalog1=pd.DataFrame(match)

    merge=catalog1.merge(suppliers, on="supplier_id", how="inner")

    merge=merge.sort_values(
        by=[
            "unit_cost",
            "reliability_score",
            "on_time_rate"
        ],
        ascending=[
            True,
            False,
            False
        ]
    )

    top=merge.iloc[0]

    return {
        "Supplier ID": top["supplier_id"],
        "supplier_name": top["supplier_name"],
        "unit_cost": top["unit_cost"],
        "total_cost": top["unit_cost"] * quantity,
        "reliability_score": top["reliability_score"],
        "on_time_rate": top["on_time_rate"],
        "available_qty": top["available_qty"],
        "payment_terms": top["payment_terms"],
        "country": top["country"],
        "lead_time": top["lead_time"],
        "sku": top["sku"],
        "country": top["country"],
        "status": "SUCCESS",
    }

