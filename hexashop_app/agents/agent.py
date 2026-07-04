import os
from dotenv import load_dotenv
from crewai import Agent, LLM
from tools.supplier_tool import SupplierTool
from tools.calculator_tool import CalculatorTool
from tools.approval_tool import ApprovalTool

load_dotenv()

llm = LLM(
    model=f"azure/{os.getenv('AZURE_OPENAI_DEPLOYMENT')}",
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
)


def get_procurement_agent():
    return Agent(
        role="Senior Procurement & Supplier Management Specialist",
        goal=(
            "Select the most suitable supplier, optimize procurement cost, generate accurate "
            "purchase orders, and ensure high-value purchase orders follow Human-in-the-Loop approval."
        ),
        backstory=(
            "You are an experienced Procurement Specialist for HexaShop. You make decisions using supplier "
            "performance, cost efficiency, stock availability, and delivery reliability. You never fabricate "
            "information and always rely on tools."
        ),
        llm=llm,
        tools=[SupplierTool(), CalculatorTool(), ApprovalTool()],
        allow_delegation=False,
        verbose=True,
    )
