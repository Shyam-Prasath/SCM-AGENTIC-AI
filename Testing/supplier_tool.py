import sqlite3
from crewai.tools import BaseTool
from config import DB_PATH

class SupplierTool(BaseTool):
    name: str = "Supplier Quote Lookup Tool"
    description: str = (
        "Lookup suppliers, unit cost, MOQ, lead time, and reliability for a given SKU."
    )

    def _run(self, sku: str) -> str:
        sku = sku.strip().upper()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            query = """
            SELECT 
                sc.supplier_id,
                s.supplier_name,
                sc.unit_cost,
                sc.moq,
                sc.lead_time_days,
                sc.available_qty,
                s.reliability_score,
                s.on_time_rate
            FROM supplier_catalog sc
            JOIN suppliers s ON sc.supplier_id = s.supplier_id
            WHERE sc.sku = ?
            """
            cursor.execute(query, (sku,))
            rows = cursor.fetchall()
            if not rows:
                return f"No suppliers found for SKU {sku}"
            
            output = []
            for row in rows:
                output.append(
                    f"Supplier ID: {row[0]}\n"
                    f"Name: {row[1]}\n"
                    f"Unit Cost: ${row[2]:.2f}\n"
                    f"MOQ: {row[3]}\n"
                    f"Lead Time: {row[4]} days\n"
                    f"Available Qty: {row[5]}\n"
                    f"Reliability: {row[6]}\n"
                    f"On-time Rate: {row[7]}\n"
                )
            return "\n---\n".join(output)
        except Exception as e:
            return f"Error querying suppliers: {str(e)}"
        finally:
            conn.close()
