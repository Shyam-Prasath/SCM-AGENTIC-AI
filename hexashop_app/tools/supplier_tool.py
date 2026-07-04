import json
from pathlib import Path
import pandas as pd
from crewai.tools import BaseTool

CATALOG_PATH = Path("data") / "supplier_catalog.json"
SUPPLIER_PATH = Path("data") / "suppliers.csv"


class SupplierTool(BaseTool):
    name: str = "Supplier Tool"
    description: str = (
        "Finds the best supplier for a SKU and required quantity based on cost, "
        "available quantity, reliability, on-time delivery, and lead time."
    )

    def _run(self, sku: str, quantity: int) -> dict:
        sku = str(sku).strip().upper()
        quantity = int(quantity)

        with open(CATALOG_PATH, "r", encoding="utf-8") as file:
            catalog = json.load(file)
        suppliers = pd.read_csv(SUPPLIER_PATH)

        matching_suppliers = [
            item for item in catalog
            if str(item.get("sku", "")).upper() == sku
            and int(item.get("available_qty", 0)) >= quantity
        ]

        if not matching_suppliers:
            return {
                "status": "FAILED",
                "message": "No supplier found with sufficient stock.",
                "sku": sku,
                "quantity": quantity,
            }

        catalog_df = pd.DataFrame(matching_suppliers)
        merged_df = catalog_df.merge(suppliers, on="supplier_id", how="inner")

        # Best business value: sufficient stock first, then low cost, then higher reliability,
        # better on-time rate, and shorter lead time.
        merged_df = merged_df.sort_values(
            by=["unit_cost", "reliability_score", "on_time_rate", "lead_time_days"],
            ascending=[True, False, False, True],
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
