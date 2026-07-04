import os
from pathlib import Path
from dotenv import load_dotenv

# Load env variables from .env
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# OpenAI Configurations
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "https://hexaware-genai-workshop-demo.openai.azure.com/")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.4-mini")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

# SCM Settings
PO_APPROVAL_THRESHOLD = float(os.getenv("PO_APPROVAL_THRESHOLD", 1000.0))

# Database configuration
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "data" / "scm.sqlite"))
CARRIERS_FILE = BASE_DIR / "data" / "carriers.json"
ORDERS_FILE = BASE_DIR / "data" / "orders.csv"
PRODUCTS_FILE = BASE_DIR / "data" / "products.csv"
CUSTOMERS_FILE = BASE_DIR / "data" / "customers.csv"
SALES_HISTORY_FILE = BASE_DIR / "data" / "sales_history.csv"
INVENTORY_FILE = BASE_DIR / "data" / "inventory.csv"
