# from agent.agent_state import (
#     AgentState,
# )

# """
# Error Handler Node
# ====================================================
# Runs when any node sets state["error"] OR when intent = "unknown".
# Converts technical error messages into clean, helpful responses for the loan officer.

# Error sources:
#   classify_intent_node  -> "Intent classification failed: ..."
#   get_customer_profile  -> "Customer ID X not found"
#                         -> "get_customer_profile tool failed: ..."
#   get_overdue_loans     -> "get_overdue_loans tool failed: ..."
#   get_repayment_summary -> "Customer ID X not found"
#                         -> "get_repayment_summary tool failed: ..."
#   get_loan_portfolio    -> "get_loan_portfolio_stats tool failed: ..."
#   get_collection_eff    -> "No repayment data found ..."
#                         -> "get_collection_efficiency tool failed: ..."
#   summarize_node        -> "Summarization failed: ..."
#   route_to_tool         -> intent = "unknown", error = None
# """

# # ERROR HANDLER NODE

# def handle_error_node(state: AgentState) -> dict:
#     """
#     Converts error state into a clean user-facing message.

#     Two entry paths:
#       1. error is set -> node failed, convert error to friendly message
#       2. intent = unknown -> classifier ran fine but could not match intent
#     """
#     error = state.get("error")       # may be None if unknown intent
#     intent = state.get("intent")
#     user_query = state.get("user_query", "")

#     # Unknown intent, no error
#     # The classifier ran successfully but the query didn't match any tool
#     if error is None and intent == "unknown":
#         message = (
#             f"I didn't understand your query: '{user_query}'. "
#             "Try rephrasing it or type 'help' to see all supported queries "
#             "with examples."
#         )
#         return {
#             "final_response": message,
#             "error": None
#         }

#     # Error is None but we still landed here
#     if error is None:
#         message = (
#             "Something unexpected happened. "
#             "Please try your query again or type 'help'."
#         )
#         return {
#             "final_response": message,
#             "error": None
#         }

#     # Error is set — match to friendly message
#     error_lower = error.lower()

#     #  Customer / record not found
#     # Source: get_customer_profile_node, get_repayment_summary_node
#     # e.g. "Customer ID 999 not found"
#     if error_lower == "please provide a customer id.":
#         message = (
#             f"{error}."
#             "\nExample: 'show me customer 42' or "
#             "'get profile of customer ID 15'"
#         )

#     elif "not found" in error_lower:
#         message = (
#             f"I could not find the requested record. "
#             f"{error}. "
#             f"Please check the ID and try again."
#         )

#     # Intent classifier LLM call failed
#     # Source: classify_intent_node
#     # e.g. "Intent classification failed: Connection timeout"
#     elif "intent classification failed" in error_lower:
#         message = (
#             "I had trouble understanding your query — the classification "
#             "service is not responding. Please try again in a moment. "
#             "If the problem persists check that vLLM is running."
#         )

#     # Summarizer LLM call failed
#     # Source: summarize_node
#     # e.g. "Summarization failed: Connection timeout"
#     elif "summarization failed" in error_lower:
#         message = (
#             "I retrieved your data but had trouble generating a summary — "
#             "the language model is not responding. Please try again in a moment."
#         )

#     # Database connection issues
#     # Source: any tool node — psycopg2 raises OperationalError
#     # e.g. "could not connect to server: Connection refused"
#     # e.g. "SSL connection has been closed unexpectedly"
#     elif "connection" in error_lower or "operational" in error_lower:
#         message = (
#             "I'm having trouble connecting to the database. "
#             "Please try again in a moment. "
#             "If the problem persists check that PostgreSQL is running."
#         )

#     # Generic tool failure
#     # Source: any tool node except block
#     # e.g. "get_overdue_loans failed: ..."
#     # e.g. "get_customer_profile failed: ..."
#     elif "tool failed:" in error_lower:
#         # Extract tool name from error string for slightly better message
#         tool_name = error_lower.split("tool failed:")[0].replace("_", " ")
#         message = (
#             f"Something went wrong while running the {tool_name} query. "
#             f"Please try again or rephrase your question. "
#             f"Type 'help' to see supported query formats."
#         )

#     # Fallback — unrecognised error
#     else:
#         message = (
#             f"Something went wrong while processing your query: '{user_query}'. "
#             "Please try again or rephrase your question. "
#             "Type 'help' to see supported query formats."
#         )

#     return {
#         "final_response": message,
#         "error": error    # for logging
#     }


# from agent.agent_state import AgentState


# def handle_error_node(state: AgentState) -> dict:

#     error = state.get("error")
#     intent = state.get("intent")
#     user_query = state.get("user_query", "")

#     # CASE 1: UNKNOWN INTENT (no error)
#     if not error and intent in (None, "unknown"):

#         return {
#             "final_response": (
#                 "I couldn't understand your request.\n\n"
#                 "Try examples like:\n"
#                 "- Show overdue loans in Mumbai\n"
#                 "- Get customer profile for ID 101\n"
#                 "- Loan portfolio stats by city"
#             ),
#             "error": None,
#         }

#     # CASE 2: NO Error but we still landed here
#     if not error:

#         return {
#             "final_response": (
#                 "Something unexpected happened. "
#                 "Please try again or rephrase your query."
#             ),
#             "error": None,
#         }

#     # Error is set — match to friendly message
#     error_lower = error.lower()


from agent.agent_state import AgentState, Intent


def handle_error_node(state: AgentState) -> dict:
    """
    Handles:
    - unknown intent
    - extraction failures
    - tool/runtime failures
    """

    error = state.get("error")
    intent = state.get("intent")

    # UNKNOWN / UNSUPPORTED QUERY
    if not error and intent in (None, Intent.UNKNOWN):

        return {
            "final_response": (
                "I couldn't understand your request.\n\n"
                "Try queries like:\n"
                "- Show overdue loans in Mumbai\n"
                "- Get customer profile for ID 101\n"
                "- Show repayment summary for customer 42\n"
                "- Loan portfolio stats by city\n"
                "- Collection efficiency this quarter"
            ),
            "tool_result": None,
            "retrieved_data": state.get("retrieved_data", {}),
            "execution_context": {
                **state.get("execution_context", {}),
                "last_tool": "handle_error",
                "error_type": "unknown_intent",
            },
            "export_path": None,
            "error": None,
        }

    # TOOL / SYSTEM ERROR
    if error:
        print("==========================================================")
        print(f"DEBUG:in error handler node:")
        print(f"DEBUG:error: {error}")
        print("==========================================================")
        return {
            "final_response": (
                f"Request failed.\n\n"
                f"Reason: {error}\n\n"
                f"Please retry or rephrase your request."
            ),
            "tool_result": None,
            "retrieved_data": state.get("retrieved_data", {}),
            "execution_context": {
                **state.get("execution_context", {}),
                "last_tool": "handle_error",
                "error_type": "execution_error",
            },
            "export_path": None,
            "error": error,
        }

    # FALLBACK SAFETY CASE
    return {
        "final_response": ("Something unexpected happened. " "Please try again."),
        "tool_result": None,
        "retrieved_data": state.get("retrieved_data", {}),
        "execution_context": {
            **state.get("execution_context", {}),
            "last_tool": "handle_error",
            "error_type": "unknown_error",
        },
        "export_path": None,
        "error": "Unknown routing failure",
    }
