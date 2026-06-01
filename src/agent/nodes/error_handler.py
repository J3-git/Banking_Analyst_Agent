# from agent.agent_state import AgentState, Intent

# def handle_error_node(state: AgentState) -> dict:
#     """
#     Handles:
#     - unknown intent
#     - extraction failures
#     - tool/runtime failures
#     """

#     error = state.get("error")
#     intent = state.get("intent")

#     # UNKNOWN / UNSUPPORTED QUERY
#     if not error and intent in (None, Intent.UNKNOWN):

#         return {
#             "final_response": (
#                 "I couldn't understand your request.\n\n"
#                 "Try queries like:\n"
#                 "- Show overdue loans in Mumbai\n"
#                 "- Get customer profile for ID 101\n"
#                 "- Show repayment summary for customer 42\n"
#                 "- Loan portfolio stats by city\n"
#                 "- Collection efficiency this quarter"
#             ),
#             "tool_result": None,
#             "retrieved_data": state.get("retrieved_data", {}),
#             "execution_context": {
#                 **state.get("execution_context", {}),
#                 "last_tool": "handle_error",
#                 "error_type": "unknown_intent",
#             },
#             "export_path": None,
#             "error": None,
#         }

#     # TOOL / SYSTEM ERROR
#     if error:
#         print("==========================================================")
#         print(f"DEBUG:in error handler node:")
#         print(f"DEBUG:error: {error}")
#         print("==========================================================")
#         return {
#             "final_response": (
#                 f"Request failed.\n\n"
#                 f"Reason: {error}\n\n"
#                 f"Please retry or rephrase your request."
#             ),
#             "tool_result": None,
#             "retrieved_data": state.get("retrieved_data", {}),
#             "execution_context": {
#                 **state.get("execution_context", {}),
#                 "last_tool": "handle_error",
#                 "error_type": "execution_error",
#             },
#             "export_path": None,
#             "error": error,
#         }

#     # FALLBACK SAFETY CASE
#     return {
#         "final_response": ("Something unexpected happened. " "Please try again."),
#         "tool_result": None,
#         "retrieved_data": state.get("retrieved_data", {}),
#         "execution_context": {
#             **state.get("execution_context", {}),
#             "last_tool": "handle_error",
#             "error_type": "unknown_error",
#         },
#         "export_path": None,
#         "error": "Unknown routing failure",
#     }


from agent.agent_state import AgentState, Intent


def handle_error_node(state: AgentState) -> dict:
    """
    Handles:
    - unknown intent
    - extraction failures
    - tool/runtime failures

    Ownership rules:
    - This node writes ONLY to: final_response, error
    """

    error = state.get("error")
    intent = state.get("intent")

    # unknown / unsupported query
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
            "error": None,
        }

    # tool / system error
    if error:
        print("==========================================================")
        print("DEBUG: in handle_error_node:")
        print(f"DEBUG: error: {error}")
        print("==========================================================")

        return {
            "final_response": (
                f"Request failed.\n\n"
                f"Reason: {error}\n\n"
                f"Please retry or rephrase your request."
            ),
            "error": error,
        }

    # fallback safety case
    return {
        "final_response": "Something unexpected happened. Please try again.",
        "error": "Unknown routing failure",
    }
