import os
import sys
import json
import contextlib
from datetime import datetime

# =====================================================
# DISABLE CREWAI TRACING / EXTRA PROMPTS
# Keep this BEFORE importing langgraph_workflow
# =====================================================

os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("LITELLM_LOG", "ERROR")


from langgraph_workflow import build_graph


# =====================================================
# LOG FOLDER SETUP
# =====================================================

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

CREW_OUTPUT_LOG = os.path.join(LOG_DIR, "crew_output.log")


# =====================================================
# HELPER: CLEAN INVOKE
# =====================================================

def invoke_graph_safely(app, state):
    """
    Runs the LangGraph app while hiding long CrewAI verbose output
    from the terminal.

    The final result is still returned normally.
    CrewAI internal output is stored in logs/crew_output.log.
    """

    try:
        with open(CREW_OUTPUT_LOG, "a", encoding="utf-8") as log_file:
            log_file.write("\n\n" + "=" * 80 + "\n")
            log_file.write(f"RUN STARTED: {datetime.now()}\n")
            log_file.write(f"QUERY: {state.get('query')}\n")
            log_file.write("=" * 80 + "\n")

            with contextlib.redirect_stdout(log_file), contextlib.redirect_stderr(log_file):
                result = app.invoke(state)

        return result

    except Exception as e:
        return {
            "route": "error",
            "final_response": f"Application Error: {str(e)}",
            "hil_required": False
        }


# =====================================================
# HELPER: DISPLAY RESULT
# =====================================================

def display_result(result):
    route = result.get("route", "unknown")
    final_response = result.get("final_response", "No result generated.")
    hil_required = result.get("hil_required", False)
    hil_reason = result.get("hil_reason", "")

    print("\n" + "=" * 70)
    print(f"ROUTE: {route}")
    print("=" * 70)
    print(final_response)
    print("=" * 70)

    if hil_required:
        print("\nHUMAN-IN-THE-LOOP REQUIRED")
        print("-" * 70)
        print(f"Reason: {hil_reason if hil_reason else 'Manager approval required.'}")
        print(
            "\nFor final demo, approve/reject/hold this action from the "
            "Streamlit approval panel instead of CLI."
        )
        print("-" * 70)


# =====================================================
# MAIN CLI
# =====================================================

def main():
    app = build_graph()

    print("=" * 70)
    print("HexaShop SCM Multi-Agent System - LangGraph CLI")
    print("Type 'exit' to quit.")
    print("=" * 70)

    while True:
        query = input("\nManager Query: ").strip()

        if query.lower() in ("exit", "quit"):
            print("\nExiting HexaShop SCM CLI.")
            break

        if not query:
            print("Please enter a valid manager query.")
            continue

        # Only send manager query.
        # Do not ask every optional field here.
        # Follow-up questions will be handled by LangGraph/guardrails.
        state = {
            "query": query,

            # Optional values.
            # They are kept None/default so guardrails can decide what is needed.
            "order_id": None,
            "sku": None,
            "forecast_days": None,
            "mode": "balanced",
            "limit": 5,

            # HIL fields.
            "hil_required": False,
            "hil_reason": None,
            "hil_decision": None,
        }

        result = invoke_graph_safely(app, state)
        display_result(result)


if __name__ == "__main__":
    main()