# HexaShop SCM Multi-Agent Streamlit Application

This project connects HexaShop Supply Chain Management agents using **LangGraph** and presents them through a **Streamlit UI**.

## Features

- LangGraph supervisor routing
- Demand Forecasting Agent
- Inventory Monitoring Agent
- Procurement Agent
- Logistics & Routing Agent
- Customer Communication Agent
- Guardrails and follow-up questions
- Human-in-the-Loop approval flow
- Full project logger
- Streamlit dashboard

## Folder Structure

```text
project_root/
│
├── app.py
├── main.py
├── langgraph_workflow.py
├── state.py
├── guardrails.py
├── hil.py
├── logger_config.py
│
├── agents/
│   ├── agent.py
│   ├── demand_forecast_agent.py
│   ├── inventory_monitoring_agent.py
│   ├── logistics_routing_agent.py
│   └── communication_agent.py
│
├── agent_wrappers/
│   ├── demand_wrapper.py
│   ├── inventory_wrapper.py
│   ├── procurement_wrapper.py
│   ├── logistics_wrapper.py
│   └── communication_wrapper.py
│
├── tools/
│   ├── supplier_tool.py
│   ├── calculator_tool.py
│   └── approval_tool.py
│
├── prompts/
│   └── prompt.py
│
├── data/
│   ├── scm.sqlite
│   ├── sales_history.csv
│   ├── inventory.csv
│   ├── inventory.json
│   ├── orders.csv
│   ├── customers.csv
│   ├── products.csv
│   ├── carriers.json
│   ├── supplier_catalog.json
│   └── suppliers.csv
│
├── logs/
├── requirements.txt
└── .env.example
```

## Setup

1. Create virtual environment:

```bash
python -m venv venv
```

2. Activate virtual environment:

Windows PowerShell:

```bash
venv\Scripts\activate
```

Git Bash:

```bash
source venv/Scripts/activate
```

3. Install requirements:

```bash
pip install -r requirements.txt
```

4. Create `.env` from `.env.example`:

```bash
cp .env.example .env
```

Fill your Azure OpenAI values:

```env
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_KEY=
AZURE_OPENAI_DEPLOYMENT=
AZURE_OPENAI_API_VERSION=2024-12-01-preview
```

5. Run Streamlit app:

```bash
streamlit run app.py
```

CLI option:

```bash
python main.py
```

## Human-in-the-Loop Rules

| Agent | HIL Trigger |
|---|---|
| Demand Forecasting | Predicted demand exceeds available stock or unusually high forecast |
| Inventory Monitoring | Critical shortage exceeds threshold |
| Procurement | Purchase order cost exceeds approval limit |
| Logistics & Routing | Delay risk, high shipment weight, or high shipping cost |
| Customer Communication | High-priority customer message |

## Logs

Logs are saved in:

```text
logs/scm_agent.log
logs/scm_runs.jsonl
```

The Streamlit app has a Logs tab to view recent runs.

## Sample Questions

### Demand Forecasting

```text
Forecast demand for ELC-1001 for 7 days
Check stock-out risk for FSH-2001 for 10 days
```

### Inventory Monitoring

```text
Show all low stock products below reorder level
Which SKUs are below reorder level in the North warehouse?
Show SKU profile for ELC-1001
```

### Procurement

```text
Create procurement plan for low stock items
Find best supplier for ELC-1001 quantity 120
Generate purchase order for HOM-3001 quantity 200
```

### Logistics

```text
Create balanced logistics plan for 10 pending orders
Choose fastest carrier for 5 pending orders
Check delay risk for all pending orders using cheapest mode
Find shipments that need manager approval
```

### Communication

```text
Generate customer communication for order ORD-90017
Draft customer email for delayed order ORD-90018
```

### Full Pipeline

```text
Run full end-to-end SCM workflow for ELC-1001 for 7 days
Run complete HexaShop supply chain analysis
```
