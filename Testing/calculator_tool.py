from crewai.tools import BaseTool

class CalculatorTool(BaseTool):
    name: str = "SCM Calculation Tool"
    description: str = (
        "Perform arithmetic operations (multiplication, division, addition, subtraction). "
        "Useful for calculating total procurement costs or comparing cost differences."
    )

    def _run(self, operation: str) -> str:
        import re
        operation = operation.strip()
        # Allow only numbers, operators, dots, parenthesises, and whitespace
        if not re.match(r'^[0-9+\-*/().\s]+$', operation):
            return "Error: Invalid characters in arithmetic expression."
        try:
            # Safe eval
            val = eval(operation, {"__builtins__": None}, {})
            return f"Result of '{operation}' is {val:.2f}"
        except Exception as e:
            return f"Error executing calculation: {str(e)}"
