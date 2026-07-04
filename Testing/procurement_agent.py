import os
from dotenv import load_dotenv
from crewai import Agent, LLM
from tools.supplier_tool import SupplierTool
from tools.calculator_tool import CalculatorTool
from tools.approval_tool import ApprovalTool

# Load environment variables
load_dotenv()

# Azure OpenAI LLM
llm = LLM(
    model=f"azure/{os.getenv('AZURE_OPENAI_DEPLOYMENT')}",
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION")
)

def get_procurement_agent():
    """
    Creates and returns the Procurement & Supplier Management Agent.
    """
    procurement_agent = Agent(
        role="Senior Procurement & Supplier Management Specialist",
        goal=(
            "Select the most suitable supplier, optimize procurement cost,generate accurate purchase orders, and ensure that high-value,purchase orders follow the Human-in-the-Loop approval process."
        ),
        backstory=(
            "You are an experienced Procurement Specialist working for "
            "HexaShop's Supply Chain Management System. You have extensive "
            "experience in supplier evaluation, procurement planning, cost "
            "optimization, inventory replenishment, and purchase order "
            "management. You always make procurement decisions based on "
            "supplier performance, cost efficiency, availability, and "
            "delivery reliability. You never fabricate information and "
            "always rely on the available tools."
        ),
        llm=llm,
        tools=[
            SupplierTool(),
            CalculatorTool(),
            ApprovalTool(),
        ],
        allow_delegation=False,
        verbose=True,
    )

    return procurement_agent
