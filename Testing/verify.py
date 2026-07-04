try:
    print("Testing config.py...")
    import config
    print("config.py OK. DB_PATH:", config.DB_PATH)

    print("Testing tools package...")
    from tools import SupplierTool, CalculatorTool, ApprovalTool
    print("tools OK.")

    print("Testing agents package...")
    from agents.inventory_agent import inventory_monitoring_agent
    from agents.demand_agent import forecasting_agent
    from agents.procurement_agent import get_procurement_agent
    from agents.logistics_agent import logistics_routing_agent
    from agents.customer_agent import communicationAgent
    print("agents OK.")

    print("Testing orchestrator.py...")
    from orchestrator import orchestrator_graph
    print("orchestrator OK.")
    print("\n[SUCCESS] All SCM integration imports are working perfectly!")
except Exception as e:
    import traceback
    print("\n[FAILURE] Verification failed:")
    traceback.print_exc()
