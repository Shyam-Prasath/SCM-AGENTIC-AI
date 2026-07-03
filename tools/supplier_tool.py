import json
import pandas as pd

from crewai.tools import BaseTool


CATALOG_PATH = "data/supplier_catalog.json"
SUPPLIER_PATH = "data/suppliers.csv"


class SupplierTool(BaseTool):
    name: str = "Supplier Tool"
    description: str = (
        "Finds the best supplier for a given SKU and required quantity based on "
        "cost, reliability, on-time delivery, and stock availability."
    )

    def _run(self, sku: str, quantity: int) -> dict:
        """
        Finds the best supplier for the given SKU and quantity.

        Args:
            sku (str): Product SKU
            quantity (int): Required quantity

        Returns:
            dict: Best supplier details
        """

        # Load Supplier Catalog
        with open(CATALOG_PATH, "r") as file:
            catalog = json.load(file)

        # Load Supplier Details
        suppliers = pd.read_csv(SUPPLIER_PATH)

        # Filter suppliers who can supply the SKU
        matching_suppliers = [
            item
            for item in catalog
            if item["sku"] == sku
        ]

        if not matching_suppliers:
            return {
                "status": "FAILED",
                "message": "No supplier found with sufficient stock."
            }

        # Convert to DataFrame
        catalog_df = pd.DataFrame(matching_suppliers)

        # Merge supplier catalog with supplier details
        merged_df = catalog_df.merge(
            suppliers,
            on="supplier_id",
            how="inner"
        )

        # Rank suppliers
        merged_df = merged_df.sort_values(
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

        best = merged_df.iloc[0]

        return {
    "status": "SUCCESS",
    "supplier_id": best["supplier_id"],
    "supplier_name": best["supplier_name"],
    "sku": best["sku"],
    "unit_cost": float(best["unit_cost"]),
    "quantity": quantity,
    "total_cost": round(float(best["unit_cost"]) * quantity, 2),
    "available_qty": int(best["available_qty"]),
    "reliability_score": float(best["reliability_score"]),
    "on_time_rate": float(best["on_time_rate"]),
    "payment_terms": best["payment_terms"],
    "country": best["country"],
    "lead_time_days": int(best["lead_time_days"]),
}