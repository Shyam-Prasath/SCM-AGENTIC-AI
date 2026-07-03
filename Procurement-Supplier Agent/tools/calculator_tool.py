from langchain.tools import tool
@tool
def calculator_tool(unit_Cost: float, quantity: int) -> dict:
    """
    A tool to calculate the total procurement cost based on unit cost and quantity.
    Args:
        unit_Cost (float): The cost per unit of the item.
        quantity (int): The number of units to be procured.
    Returns:
        dict: A dictionary containing the total cost, unit cost, and quantity.
    """
    total_cost = unit_Cost * quantity
    return {"total_cost": round(total_cost, 2),
            "unit_cost": unit_Cost,
            "quantity": quantity}