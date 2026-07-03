import json
from crewai import Crew, Task, Process
from agent.agent import get_procurement_agent
from prompt_structure.prompt import PROCUREMENT_PROMPT

with open("inventory data/inventory.json", "r") as file:
    inventory_data = json.load(file)

procurement_agent = get_procurement_agent()

procurement_task = Task(

    description=f"""
{PROCUREMENT_PROMPT}

Inventory Data:

{json.dumps(inventory_data, indent=4)}
Using the available tools:
1. Identify the best supplier.
2. Calculate procurement cost.
3. Generate Purchase Order.
4. Perform Human-in-the-Loop approval check.
5. Return the final Purchase Order.
""",
    expected_output="""
Return a structured Purchase Order containing:

- Purchase Order ID
- SKU
- Supplier ID
- Supplier Name
- Quantity
- Unit Cost
- Total Cost
- Lead Time
- Approval Status
""",

    agent=procurement_agent,
)
crew = Crew(
    agents=[
        procurement_agent
    ],
    tasks=[
        procurement_task
    ],
    process=Process.sequential,
    verbose=True
)

result = crew.kickoff()
print("\n")
print("FINAL PROCUREMENT RESULT")
print(result)