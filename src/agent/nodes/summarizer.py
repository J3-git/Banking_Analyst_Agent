# import json
# from openai import OpenAI
# from langgraph.runtime import Runtime
# from agent.agent_state import AgentState
# from agent.runtime_context import AppContext
# from agent.utils import _call_llm
# from langchain_core.messages import AIMessage

# SYSTEM_PROMPT = """
# You are a senior banking analyst.

# Convert structured loan system outputs into clear business insights.

# Rules:
# - No reasoning tags or hidden thoughts
# - Start with key insight
# - Use ₹ formatting (lakh/crore)
# - Be concise and action-oriented
# - Highlight risks clearly
# - Do not hallucinate
# - If data is missing, explicitly say so
# """

# INTENT_PROMPTS = {
#     "get_customer_profile": """
# Summarise customer profile for credit review.

# Include:
# 1. Customer overview
# 2. Loan exposure summary
# 3. Risk level interpretation
# 4. Recommended action
# """,
#     "get_overdue_loans": """
# Summarise overdue loan portfolio for collections team.

# Include:
# 1. Total overdue exposure
# 2. DPD bucket distribution (early/moderate/serious/critical)
# 3. Top critical cases (most important borrowers)
# 4. Action priority list
# """,
#     "get_repayment_summary": """
# Summarise repayment behaviour of the customer.

# Include:
# 1. Payment behaviour breakdown
# 2. Average DPD and delinquency pattern
# 3. Trend (improving / stable / deteriorating)
# 4. Recommended follow-up action
# """,
#     "get_loan_portfolio_stats": """
# Summarise portfolio-wide performance.

# Include:
# 1. Overall portfolio health
# 2. Worst performing segment
# 3. Risk concentration
# 4. Management recommendation
# """,
#     "get_collection_efficiency": """
# Summarise collection efficiency.

# Include:
# 1. Recovery performance
# 2. Collection gaps
# 3. Trend analysis
# 4. Operational recommendation
# """,
#     "get_help": """
# Explain system capabilities in simple language with examples.
# """,
#     "unknown": """
# Explain that request is not understood and suggest using help.
# """,
# }


# def _safe_intent(intent):
#     if hasattr(intent, "value"):
#         return intent.value
#     return intent or "unknown"


# def _extract_data(intent: str, tool_result: dict) -> str:
#     if not tool_result:
#         return "No data available."

#     if intent == "get_overdue_loans":
#         return json.dumps(
#             {
#                 "total_overdue": tool_result.get("overall", {}).get("total_overdue"),
#                 "dpd_buckets": tool_result.get("dpd_buckets"),
#                 "top_critical": tool_result.get("top_critical", []),
#                 "export_path": tool_result.get("export_path"),
#             },
#             indent=2,
#             default=str,
#         )

#     if intent == "get_repayment_summary":
#         return json.dumps(
#             {
#                 "customer_name": tool_result.get("customer_name"),
#                 "summary": tool_result.get("summary"),
#                 "total_records": tool_result.get("total_repayment_records"),
#             },
#             indent=2,
#             default=str,
#         )

#     return json.dumps(tool_result, indent=2, default=str)


# # -------------------------
# # MAIN NODE
# # -------------------------


# def summarize_node(state: AgentState, runtime: Runtime[AppContext]) -> dict:
#     client = runtime.context.client
#     model_name = runtime.context.model_name

#     intent = _safe_intent(state.get("intent"))
#     tool_result = state.get("tool_result")
#     user_query = state.get("user_query", "")

#     intent_instruction = INTENT_PROMPTS.get(intent, INTENT_PROMPTS["unknown"])
#     structured_data = _extract_data(intent, tool_result)

#     user_prompt = f"""
# User Query:
# "{user_query}"

# Instruction:
# {intent_instruction}

# Data:
# {structured_data}

# Generate a clear banking analyst summary.
# """

#     try:
#         response = _call_llm(
#             system_prompt=SYSTEM_PROMPT,
#             user_prompt=user_prompt,
#             client=client,
#             model_name=model_name,
#             max_tokens=2000,
#         )

#         execution_context = state.get("execution_context", {})
#         export_path = execution_context.get("export_path")

#         if export_path:
#             response += f"\n\nExport file available at: {export_path}"

#         # OPTIONAL TRICK: If tool_result explicitly returns a customer_id, lock it into execution context
#         # so next multi-turn loops remember it safely even if LLM fails param extraction.
#         if tool_result and isinstance(tool_result, dict):
#             for key in ["customer_id", "id", "customer_name"]:
#                 if key in tool_result and tool_result[key]:
#                     execution_context["current_customer_id"] = tool_result[key]

#         print("==========================================================")
#         print(f"DEBUG:in summarizer node:")
#         print(f"DEBUG:execution_context: {execution_context}")
#         print("==========================================================")

#         return {
#             "final_response": response,
#             "execution_context": execution_context,
#             "error": None,
#         }

#     except Exception as e:
#         print("==========================================================")
#         print(f"DEBUG:in summarizer node exception occurred:")
#         print(f"DEBUG:error: {e}")
#         print("==========================================================")

#         return {
#             "final_response": None,
#             "error": f"Summarization failed: {str(e)}",
#         }


import json
from langgraph.runtime import Runtime
from agent.agent_state import AgentState, ExecutionContext
from agent.runtime_context import AppContext
from agent.utils import _call_llm

SYSTEM_PROMPT = """
You are a senior banking analyst.

Convert structured loan system outputs into clear business insights.

Rules:
- No reasoning tags or hidden thoughts
- Start with key insight
- Use ₹ formatting (lakh/crore)
- Be concise and action-oriented
- Highlight risks clearly
- Do not hallucinate
- If data is missing, explicitly say so
- If providing details be specific. e.g. Clearly mention 'Load ID' / 'Customer ID' and not just 'ID'
"""

INTENT_PROMPTS = {
    "get_customer_profile": """
Summarise customer profile for credit review.

Include:
1. Customer overview
2. Loan exposure summary
3. Risk level interpretation
4. Recommended action
""",
    "get_overdue_loans": """
Summarise overdue loan portfolio for collections team.

Include:
1. Total overdue exposure
2. DPD bucket distribution (early/moderate/serious/critical)
3. Top critical cases (most important borrowers)
4. Action priority list
""",
    "get_repayment_summary": """
Summarise repayment behaviour of the customer.

Include:
1. Payment behaviour breakdown
2. Average DPD and delinquency pattern
3. Trend (improving / stable / deteriorating)
4. Recommended follow-up action
""",
    "get_loan_portfolio_stats": """
Summarise portfolio-wide performance.

Include:
1. Overall portfolio health
2. Worst performing segment
3. Risk concentration
4. Management recommendation
""",
    "get_collection_efficiency": """
Summarise collection efficiency.

Include:
1. Recovery performance
2. Collection gaps
3. Trend analysis
4. Operational recommendation
""",
    "get_help": """
Explain system capabilities in simple language with examples.
""",
    "unknown": """
Explain that request is not understood and suggest using help.
""",
    "compare": """
Generate a side-by-side comparison for the banking analyst.

Include:
1. Key metric differences between the two entities
2. Which is performing better and why
3. Risk implications
4. Recommended action
""",
}


# for debugging
import inspect

# HELPERS


def _safe_intent(intent) -> str:
    if hasattr(intent, "value"):
        return intent.value
    return intent or "unknown"


def _extract_data(intent: str, tool_result: dict) -> str:
    """Normalize tool output into LLM-friendly JSON."""

    # Debug start
    frame = inspect.currentframe()
    print("---------------------------------------------------------------")
    print(f"DEBUG: Entered function: {frame.f_code.co_name}")

    caller_frame = frame.f_back
    caller_function = caller_frame.f_code.co_name if caller_frame else "<module>"
    print(f"DEBUG _extract_data: Called from: {caller_function}")
    # Debug end

    if not tool_result:
        print(f"DEBUG _extract_data: tool result unavailable.")
        print(f"DEBUG _extract_data: returning default string")
        print("---------------------------------------------------------------")
        return "No data available."

    if intent == "get_overdue_loans":
        extract_data_overdue_loans = json.dumps(
            {
                "total_overdue": tool_result.get("overall", {}).get("total_overdue"),
                "dpd_buckets": tool_result.get("dpd_buckets"),
                "top_critical": tool_result.get("top_critical", []),
                "csv_path": tool_result.get("csv_path"),
            },
            indent=2,
            default=str,
        )
        print(f"DEBUG _extract_data: intent is get_overdue_loans")
        print(f"DEBUG _extract_data: return : {extract_data_overdue_loans}")
        print("---------------------------------------------------------------")
        return extract_data_overdue_loans

    if intent == "get_repayment_summary":
        extract_data_repayment_summary = json.dumps(
            {
                "customer_name": tool_result.get("customer_name"),
                "summary": tool_result.get("summary"),
                "total_records": tool_result.get("total_repayment_records"),
            },
            indent=2,
            default=str,
        )

        print(f"DEBUG _extract_data: intent is repayment_summary")
        print(f"DEBUG _extract_data: return : {extract_data_repayment_summary}")
        print("---------------------------------------------------------------")
        return extract_data_repayment_summary

    print(
        f"DEBUG _extract_data: return : {json.dumps(tool_result, indent=2, default=str)}"
    )
    print("---------------------------------------------------------------")
    return json.dumps(tool_result, indent=2, default=str)


def _build_execution_context(
    state: AgentState,
    intent: str,
    tool_result: dict,
    response: str,
    is_compare_turn: bool,
) -> ExecutionContext:
    """
    Builds a fresh ExecutionContext from the current turn.
    Carries forward persistent entity references from the previous context.
    Sole responsibility: summarize_node.
    """

    # Debug start
    frame = inspect.currentframe()
    print("---------------------------------------------------------------")
    print(f"DEBUG: Entered function: {frame.f_code.co_name}")

    caller_frame = frame.f_back
    caller_function = caller_frame.f_code.co_name if caller_frame else "<module>"
    print(f"DEBUG _build_execution_context: Called from: {caller_function}")
    # Debug end

    # carry forward persistent references from previous turn
    prev_context: ExecutionContext = state.get("execution_context")
    follow_up_type = state.get("follow_up_type")

    # only carry compare slots forward if this turn is itself a compare
    is_compare_turn = (
        hasattr(follow_up_type, "value") and follow_up_type.value == "compare"
    ) or follow_up_type == "compare"

    # extract entity references from tool_result
    customer_id = None
    customer_name = None
    active_loan_id = None
    active_city = None
    active_loan_type = None
    active_period = None

    if tool_result and isinstance(tool_result, dict):

        # customer profile
        profile = tool_result.get("customer_profile")
        if profile and isinstance(profile, dict):
            customer_id = profile.get("customer_id")
            customer_name = profile.get("full_name")

        # repayment summary
        if not customer_name:
            customer_name = tool_result.get("customer_name")

    # tool_params carries the filters used this turn
    tool_params = state.get("tool_params")
    if tool_params:
        active_city = getattr(tool_params, "city", None)
        active_loan_type = getattr(tool_params, "loan_type", None)
        active_period = getattr(tool_params, "period", None)
        active_loan_id = getattr(tool_params, "loan_id", None)
        if not customer_id:
            customer_id = getattr(tool_params, "customer_id", None)

    # fall back to previous context for entity references not present this turn
    if prev_context:
        customer_id = customer_id or prev_context.current_customer_id
        customer_name = customer_name or prev_context.current_customer_name
        active_loan_id = active_loan_id or prev_context.active_loan_id
        active_city = active_city or prev_context.active_city
        active_loan_type = active_loan_type or prev_context.active_loan_type
        active_period = active_period or prev_context.active_period

    current_context = ExecutionContext(
        last_intent=intent,
        last_params=tool_params.model_dump(exclude_none=True) if tool_params else {},
        last_tool_result=tool_result,
        last_response=response,
        current_customer_id=customer_id,
        current_customer_name=customer_name,
        active_loan_id=active_loan_id,
        active_city=str(active_city) if active_city else None,
        active_loan_type=str(active_loan_type) if active_loan_type else None,
        active_period=str(active_period) if active_period else None,
        # compare slots carried forward -- merge_node owns them
        compare_slot_a=(
            prev_context.compare_slot_a if (prev_context and is_compare_turn) else None
        ),
        compare_slot_b=(
            prev_context.compare_slot_b if (prev_context and is_compare_turn) else None
        ),
    )

    print(
        f"DEBUG: _build_execution_context: built execution context: {current_context}"
    )
    print("---------------------------------------------------------------")

    return current_context


# MAIN NODE


def summarize_node(state: AgentState, runtime: Runtime[AppContext]) -> dict:
    """
    Generates LLM summary from tool result and builds ExecutionContext.

    Ownership rules:
    - This node writes ONLY to: final_response, execution_context, csv_paths, error
    - retrieved_data is NOT touched here -- owned by tool nodes
    """

    # Debug start
    frame = inspect.currentframe()
    print("==============================================================")
    print(f"DEBUG: Entered function: {frame.f_code.co_name}")
    # Debug end

    intent = _safe_intent(state.get("intent"))
    tool_result = state.get("tool_result")
    user_query = state["enriched_query"]

    # compare flow -- build prompt from compare slots
    execution_context_prev = state.get("execution_context")
    follow_up_type = state.get("follow_up_type")

    is_compare = (
        follow_up_type == "compare"  # or your enum check
        and execution_context_prev
        and execution_context_prev.compare_slot_a
        and execution_context_prev.compare_slot_b
    )

    chart_paths = list(state.get("chart_paths") or []) if is_compare else []

    if is_compare:
        slot_a = execution_context_prev.compare_slot_a
        slot_b = execution_context_prev.compare_slot_b
        intent_instruction = INTENT_PROMPTS["compare"]
        structured_data = json.dumps(
            {
                slot_a.label: slot_a.result,
                slot_b.label: slot_b.result,
            },
            indent=2,
            default=str,
        )
    else:
        intent_instruction = INTENT_PROMPTS.get(intent, INTENT_PROMPTS["unknown"])
        print(f"DEBUG summarize_node: calling _extract_data")
        structured_data = _extract_data(intent, tool_result)
        print(f"DEBUG summarize_node: returned back from _extract_data")

    user_prompt = f"""
User Query:
"{user_query}"

Instruction:
{intent_instruction}

Data:
{structured_data}

Generate a clear banking analyst summary.
"""

    try:
        print(f"DEBUG summarize_node: calling _call_llm")

        response = _call_llm(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            client=runtime.context.client,
            model_name=runtime.context.model_name,
            max_tokens=5000,
        )

        print(f"DEBUG summarize_node: returned back from _call_llm")
        print(f"DEBUG summarize_node: calling _build_execution_context")

        # build ExecutionContext -- sole responsibility of this node
        execution_context = _build_execution_context(
            state=state,
            intent=intent,
            tool_result=tool_result,
            response=response,
            is_compare_turn=is_compare,
        )

        print(f"DEBUG summarize_node: returned back from _build_execution_context")

        # accumulate export paths across turns
        csv_paths = []
        tool_result_export = (
            tool_result.get("csv_path")
            if tool_result and isinstance(tool_result, dict)
            else None
        )
        if tool_result_export:
            csv_paths.append(tool_result_export)
            response += f"\n\nExport file available at: {tool_result_export}"

        print(f"DEBUG summarize_node: intent: {intent}")
        print(f"DEBUG summarize_node: final_response: {response}")
        print(f"DEBUG summarize_node: execution_context: {execution_context.to_dict()}")
        print(f"DEBUG summarize_node: csv_paths: {csv_paths}")
        print("==========================================================")

        return {
            "final_response": response,
            "execution_context": execution_context,
            "csv_paths": csv_paths,
            "chart_paths": chart_paths,
            "error": None,
        }

    except Exception as e:
        print("DEBUG summarize_node: in summarize_node exception occurred:")
        print(f"DEBUG summarize_node: error: {e}")
        print(f"DEBUG summarize_node: returning default values")
        print("==========================================================")

        return {
            "final_response": None,
            "error": f"Summarization failed: {str(e)}",
        }
