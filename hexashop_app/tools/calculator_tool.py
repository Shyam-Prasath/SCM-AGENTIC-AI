from crewai.tools import BaseTool


class CalculatorTool(BaseTool):
    name: str = "Calculator Tool"
    description: str = "Calculates total procurement cost from unit cost and quantity."

    def _run(self, unit_cost: float, quantity: int) -> dict:
        total_cost = float(unit_cost) * int(quantity)
        return {
            "unit_cost": float(unit_cost),
            "quantity": int(quantity),
            "total_cost": round(total_cost, 2),
        }
