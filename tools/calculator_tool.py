from crewai.tools import BaseTool

class CalculatorTool(BaseTool):
    name: str = "Calculator Tool"
    description: str = (
        "Calculates the total procurement cost based on unit cost and quantity."
    )

    def _run(self, unit_cost: float, quantity: int) -> dict:
        """
        Calculates the total procurement cost.

        Args:
            unit_cost (float): Cost per unit.
            quantity (int): Quantity to procure.

        Returns:
            dict: Procurement cost details.
        """

        total_cost = unit_cost * quantity

        return {
            "unit_cost": unit_cost,
            "quantity": quantity,
            "total_cost": round(unit_cost * quantity, 2)
        }