# import json
# from langgraph.types import Send
# from langgraph.runtime import Runtime
# from pydantic import BaseModel
# from agent.agent_state import (
#     AgentState,
#     ExecutionContext,
#     Intent,
#     OverdueLoansParams,
#     LoanPortfolioStatsParams,
#     CollectionEfficiencyParams,
# )
# from agent.runtime_context import AppContext
# from agent.utils import _call_llm

# # for debug
# import inspect

# # PARAM EXTRACTION FOR COMPARE

# COMPARE_PARAM_MODELS = {
#     Intent.GET_OVERDUE_LOANS: OverdueLoansParams,
#     Intent.GET_LOAN_PORTFOLIO_STATS: LoanPortfolioStatsParams,
#     Intent.GET_COLLECTION_EFFICIENCY: CollectionEfficiencyParams,
# }

# INTENT_TO_NODE = {
#     Intent.GET_OVERDUE_LOANS: "get_overdue_loans",
#     Intent.GET_LOAN_PORTFOLIO_STATS: "get_loan_portfolio_stats",
#     Intent.GET_COLLECTION_EFFICIENCY: "get_collection_efficiency",
# }


# class CompareParamsOutput(BaseModel):
#     param_a: dict
#     param_b: dict
#     label_a: str
#     label_b: str


# def _extract_compare_params(
#     enriched_query: str,
#     intent: str,
#     params_schema: dict,
#     execution_context_dict: dict,
#     model_name: str,
#     client,
# ) -> CompareParamsOutput:
#     """
#     Extracts two sets of params from a compare query.
#     e.g. "compare Mumbai vs Delhi" -> param_a: {city: Mumbai}, param_b: {city: Delhi}
#     """
#     # Debug start
#     frame = inspect.currentframe()
#     print("---------------------------------------------------------------")
#     print(f"DEBUG: Entered function: {frame.f_code.co_name}")

#     caller_frame = frame.f_back
#     caller_function = caller_frame.f_code.co_name if caller_frame else "<module>"
#     print(f"DEBUG _extract_compare_params: Called from: {caller_function}")
#     # Debug end

#     prompt = f"""
# You are a STRICT comparison parameter extraction engine for a banking system.

# Your job is to extract structured parameters for TWO scenarios being compared.


# STEP 1: DETECT COMPARISON AXIS


# Identify the SINGLE most important comparison axis:

# Possible axes:
# - city (Mumbai vs Delhi)
# - loan_type (Home vs Personal)
# - period (This Month vs Last Month)
# - group_by (city vs loan_type vs status)
# - min_days_overdue (numeric thresholds)

# You MUST choose exactly ONE axis.


# STEP 2: MAP TO SCHEMA


# Once axis is identified:

# - Fill param_a and param_b using ONLY that axis field
# - Do NOT leave param objects empty if axis exists


# STRICT RULES


# - NEVER return empty param_a or param_b if comparison exists
# - ALWAYS fill the detected axis field
# - Labels alone are NOT sufficient
# - You may set non-relevant fields to null, but NOT all fields


# EXECUTION CONTEXT

# {json.dumps(execution_context_dict, indent=2)}


# PARAMETER SCHEMA

# {json.dumps(params_schema, indent=2)}


# USER QUERY

# {enriched_query}


# OUTPUT FORMAT (STRICT JSON)

# {{
#   "param_a": {{
#     "detected_axis_field": "value"
#   }},
#   "param_b": {{
#     "detected_axis_field": "value"
#   }},
#   "label_a": "short label",
#   "label_b": "short label"
# }}

# REMEMBER:
# - axis MUST be inferred
# - axis field MUST be populated
# - empty objects are INVALID if comparison exists
# """

#     print(f"DEBUG _extract_compare_params: Calling _call_llm")
#     print("---------------------------------------------------------------")

#     return _call_llm(
#         user_prompt=prompt,
#         model_class=CompareParamsOutput,
#         model_name=model_name,
#         client=client,
#         max_tokens=400,
#     )


# def _build_cache_key(intent: str, params: dict) -> str:
#     """Build cache key matching tool node pattern."""
#     # Debug start
#     frame = inspect.currentframe()
#     print("---------------------------------------------------------------")
#     print(f"DEBUG: Entered function: {frame.f_code.co_name}")

#     caller_frame = frame.f_back
#     caller_function = caller_frame.f_code.co_name if caller_frame else "<module>"
#     print(f"DEBUG _build_cache_key: Called from: {caller_function}")
#     print("---------------------------------------------------------------")
#     # Debug end

#     if intent == "get_overdue_loans":
#         return (
#             f"overdue_loans:"
#             f"{params.get('city') or 'all'}:"
#             f"{params.get('loan_type') or 'all'}:"
#             f"{params.get('min_days_overdue') or 1}"
#         )
#     if intent == "get_loan_portfolio_stats":
#         return (
#             f"portfolio_stats:"
#             f"{params.get('group_by') or 'loan_type'}:"
#             f"{params.get('city') or 'all'}:"
#             f"{params.get('loan_type') or 'all'}"
#         )
#     if intent == "get_collection_efficiency":
#         return (
#             f"collection_efficiency:"
#             f"{params.get('city') or 'all'}:"
#             f"{params.get('loan_type') or 'all'}:"
#             f"{params.get('period') or 'full'}"
#         )
#     return f"{intent}:{json.dumps(params, sort_keys=True)}"


# # MAIN NODE -- prepares compare state (LLM call, writes compare_keys etc.)


# def compare_node(
#     state: AgentState,
#     runtime: Runtime[AppContext],
# ) -> dict:
#     """
#     Calls LLM to extract two param sets from the compare query.
#     Writes compare_keys, _compare_labels, tool_params into state.
#     Returns a dict -- route_compare (conditional edge) handles Send dispatch.

#     Ownership rules:
#     - Writes ONLY to: compare_keys, _compare_labels, tool_params, error
#     - Does NOT touch execution_context
#     """
#     # Debug start
#     frame = inspect.currentframe()
#     print("==============================================================")
#     print(f"DEBUG: Entered function: {frame.f_code.co_name}")
#     # Debug end

#     intent: Intent = state.get("intent")
#     enriched_query = state["enriched_query"]
#     execution_context: ExecutionContext = state.get("execution_context")
#     execution_context_dict = execution_context.to_dict() if execution_context else {}

#     params_model = COMPARE_PARAM_MODELS.get(intent)
#     target_node = INTENT_TO_NODE.get(intent)

#     print(f"DEBUG compare_node: params_mode schema: {params_model.model_json_schema()}")
#     print(f"DEBUG compare_node: target_node: {target_node}")

#     if not params_model or not target_node:
#         print(
#             f"DEBUG compare_node: either params_model is falsy or target_node is falsy"
#         )
#         print(f"DEBUG compare_node: returning error")
#         print("==============================================================")
#         return {"error": f"Compare not supported for intent: {intent}"}

#     try:
#         print(f"DEBUG compare_node: execution_context_dict : {execution_context_dict}")
#         print(f"DEBUG compare_node: calling _extract_compare_params")

#         compare_params = _extract_compare_params(
#             enriched_query=enriched_query,
#             intent=intent.value if hasattr(intent, "value") else intent,
#             params_schema=params_model.model_json_schema(),
#             execution_context_dict=execution_context_dict,
#             model_name=runtime.context.model_name,
#             client=runtime.context.client,
#         )
#         print(f"DEBUG compare_node: returned back from _extract_compare_params")

#         param_a = compare_params.param_a
#         param_b = compare_params.param_b
#         label_a = compare_params.label_a
#         label_b = compare_params.label_b

#         print(f"DEBUG compare_node: calling _build_cache_key")
#         key_a = _build_cache_key(
#             intent.value if hasattr(intent, "value") else intent,
#             param_a,
#         )
#         print(f"DEBUG compare_node: returned back from _build_cache_key")

#         print(f"DEBUG compare_node: calling _build_cache_key")
#         key_b = _build_cache_key(
#             intent.value if hasattr(intent, "value") else intent,
#             param_b,
#         )
#         print(f"DEBUG compare_node: returned back from _build_cache_key")

#         retrieved_data = state.get("retrieved_data", {})

#         print(f"DEBUG compare_node: intent: {intent}")
#         print(f"DEBUG compare_node: param_a: {param_a} label_a: {label_a}")
#         print(f"DEBUG compare_node: param_b: {param_b} label_b: {label_b}")
#         print(f"DEBUG compare_node: key_a: {key_a}")
#         print(f"DEBUG compare_node: key_a: {key_a in retrieved_data}")
#         print(f"DEBUG compare_node: key_b: {key_b}")
#         print(f"DEBUG compare_node: key_b in cache: {key_b in retrieved_data}")

#         # scenario: one param from history -- only need slot_b
#         is_single = (
#             execution_context
#             and execution_context.last_tool_result
#             and execution_context.last_intent
#             == (intent.value if hasattr(intent, "value") else intent)
#             and key_a in retrieved_data
#         )

#         if is_single:
#             print(
#                 f"DEBUG compare_node: We already have data for side A. We only need to fetch side B"
#             )
#             print("======================================================")
#             validated_b = params_model(**param_b)
#             return {
#                 "tool_params": validated_b,
#                 "tool_result": None,
#                 "compare_keys": [key_a, key_b],
#                 "_compare_labels": {key_a: label_a, key_b: label_b},
#                 "error": None,
#             }
#         print(f"DEBUG compare_node: both sides A and B must be fetched.")

#         # scenario: both params explicit -- need two tool calls
#         # store both param sets; route_compare will Send them
#         validated_a = params_model(**param_a)
#         validated_b = params_model(**param_b)

#         print("==========================================================")

#         return {
#             "tool_params": validated_a,  # used by first Send
#             "tool_result": None,
#             "compare_keys": [key_a, key_b],
#             "_compare_labels": {key_a: label_a, key_b: label_b},
#             "_compare_param_b": param_b,  # stored for route_compare to build second Send
#             "error": None,
#         }

#     except Exception as e:
#         print("DEBUG compare_node: exception occurred:")
#         print(f"DEBUG compare_node: error: {e}")
#         print("DEBUG compare_node: returning error")
#         print("==========================================================")

#         return {"error": f"Compare node failed: {str(e)}"}


# # CONDITIONAL EDGE -- dispatches Send objects after compare_node


# def route_compare(state: AgentState) -> list[Send] | str:
#     """
#     Conditional edge function after compare_node.
#     Reads prepared compare state and dispatches Send objects.
#     Returns list[Send] for parallel execution or str for error routing.
#     """
#     # Debug start
#     frame = inspect.currentframe()
#     print("==============================================================")
#     print(f"DEBUG: Entered function: {frame.f_code.co_name}")
#     # Debug end

#     if state.get("error"):
#         return "handle_error"

#     intent: Intent = state.get("intent")
#     target_node = INTENT_TO_NODE.get(intent)

#     if not target_node:
#         return "handle_error"

#     compare_keys = state.get("compare_keys", [])
#     compare_labels = state.get("_compare_labels", {})
#     tool_params = state.get("tool_params")
#     param_b_raw = state.get("_compare_param_b")

#     params_model = COMPARE_PARAM_MODELS.get(intent)

#     # single Send -- one param from history
#     if param_b_raw is None:
#         print(f"DEBUG route_compare: single Send")
#         print("=====================================================")
#         return [
#             Send(
#                 target_node,
#                 {
#                     **state,
#                     "tool_result": None,
#                     "compare_keys": compare_keys,
#                     "_compare_labels": compare_labels,
#                 },
#             )
#         ]

#     # dual Send -- both params explicit
#     print(f"DEBUG route_compare: dual Send")
#     print("=====================================================")
#     validated_b = params_model(**param_b_raw)
#     return [
#         Send(
#             target_node,
#             {
#                 **state,
#                 "tool_result": None,
#                 "compare_keys": compare_keys,
#                 "_compare_labels": compare_labels,
#             },
#         ),
#         Send(
#             target_node,
#             {
#                 **state,
#                 "tool_params": validated_b,
#                 "tool_result": None,
#                 "compare_keys": compare_keys,
#                 "_compare_labels": compare_labels,
#             },
#         ),
#     ]


import json
import inspect
from pydantic import BaseModel
from langgraph.types import Send
from langgraph.runtime import Runtime

from agent.agent_state import (
    AgentState,
    ExecutionContext,
    Intent,
    OverdueLoansParams,
    LoanPortfolioStatsParams,
    CollectionEfficiencyParams,
    City,
    LoanType,
    PortfolioGroupBy,
    Period,
)
from agent.runtime_context import AppContext
from agent.utils import _call_llm

# INTENT MAPPING


COMPARE_PARAM_MODELS = {
    Intent.GET_OVERDUE_LOANS: OverdueLoansParams,
    Intent.GET_LOAN_PORTFOLIO_STATS: LoanPortfolioStatsParams,
    Intent.GET_COLLECTION_EFFICIENCY: CollectionEfficiencyParams,
}

INTENT_TO_NODE = {
    Intent.GET_OVERDUE_LOANS: "get_overdue_loans",
    Intent.GET_LOAN_PORTFOLIO_STATS: "get_loan_portfolio_stats",
    Intent.GET_COLLECTION_EFFICIENCY: "get_collection_efficiency",
}


# LLM OUTPUT MODEL (ONLY ENTITY + AXIS)


class CompareEntityOutput(BaseModel):
    entity_a: str
    entity_b: str
    axis: str
    label_a: str
    label_b: str


# 1. LLM EXTRACTION (NO SCHEMA RESPONSIBILITY)


def _extract_compare_entities(
    enriched_query: str,
    # intent: str,
    execution_context_dict: dict,
    model_name: str,
    client,
) -> CompareEntityOutput:

    # Debug start
    frame = inspect.currentframe()
    print("---------------------------------------------------------------")
    print(f"DEBUG: Entered function: {frame.f_code.co_name}")
    caller_frame = frame.f_back
    caller_function = caller_frame.f_code.co_name if caller_frame else "<module>"
    print(f"DEBUG _extract_compare_entities: Called from: {caller_function}")
    # Debug end

    prompt = f"""
You are a banking comparison extractor.

RULES:
- Extract ONLY raw entities
- DO NOT construct structured parameters
- DO NOT use schemas
- DO NOT return tool-ready JSON

IMPORTANT CONSTRAINTS:

Allowed values:

City:
- Mumbai
- Delhi
- Pune
- Bangalore

LoanType:
- Personal
- Home
- Business
- Vehicle
- Education
- Gold

Period:
- this_month
- last_month
- this_quarter
- this_year

group_by:
- loan_type
- city
- status

min_days_overdue:
- int

Axis:
- city
- loan_type
- period
- group_by
- min_days_overdue

RULE:
If the user mentions anything outside this list:
→ map to closest valid value
→ never invent new categories
→ never return unknown strings

TASK:
Extract:
- entity_a
- entity_b
- axis (city | loan_type | period | group_by | min_days_overdue)
- label_a
- label_b

Execution Context:
{json.dumps(execution_context_dict, indent=2)}

User Query:
{enriched_query}

Return JSON ONLY:
{{
  "entity_a": "...",
  "entity_b": "...",
  "axis": "...",
  "label_a": "...",
  "label_b": "..."
}}
"""

    print(f"DEBUG _extract_compare_entities: Calling _call_llm")
    print("---------------------------------------------------------------")

    return _call_llm(
        user_prompt=prompt,
        model_class=CompareEntityOutput,
        model_name=model_name,
        client=client,
        max_tokens=200,
    )


# 2. CACHE KEY BUILDER


def _build_cache_key(intent: str, params: dict) -> str:
    # Debug start
    frame = inspect.currentframe()
    print("---------------------------------------------------------------")
    print(f"DEBUG: Entered function: {frame.f_code.co_name}")

    caller_frame = frame.f_back
    caller_function = caller_frame.f_code.co_name if caller_frame else "<module>"
    print(f"DEBUG _build_cache_key: Called from: {caller_function}")
    print("---------------------------------------------------------------")
    # Debug end

    if intent == "get_overdue_loans":
        return (
            f"overdue_loans:"
            f"{params.get('city') or 'City.all'}:"
            f"{params.get('loan_type') or 'LoanType.all'}:"
            f"{params.get('min_days_overdue') or 1}"
        )

    if intent == "get_loan_portfolio_stats":
        return (
            f"portfolio_stats:"
            f"{params.get('group_by') or 'GroupBy.loan_type'}:"
            f"{params.get('city') or 'City.all'}:"
            f"{params.get('loan_type') or 'LoanType.all'}"
        )

    if intent == "get_collection_efficiency":
        return (
            f"collection_efficiency:"
            f"{params.get('city') or 'City.all'}:"
            f"{params.get('loan_type') or 'LoanType.all'}:"
            f"{params.get('period') or 'Period.full'}"
        )

    return f"{intent}:{json.dumps(params, sort_keys=True)}"


# 3. DETERMINISTIC PARAM BUILDER


def _build_params(intent: Intent, axis: str, entity: str):

    if intent == Intent.GET_OVERDUE_LOANS:

        if axis == "city":
            return OverdueLoansParams(city=City(entity))

        if axis == "loan_type":
            return OverdueLoansParams(loan_type=LoanType(entity))

        if axis == "min_days_overdue":
            return OverdueLoansParams(min_days_overdue=int(entity))

        return OverdueLoansParams()

    if intent == Intent.GET_LOAN_PORTFOLIO_STATS:

        if axis == "group_by":
            return LoanPortfolioStatsParams(group_by=PortfolioGroupBy(entity))

        if axis == "city":
            return LoanPortfolioStatsParams(city=City(entity))

        if axis == "loan_type":
            return LoanPortfolioStatsParams(loan_type=LoanType(entity))

        return LoanPortfolioStatsParams()

    if intent == Intent.GET_COLLECTION_EFFICIENCY:

        if axis == "period":
            return CollectionEfficiencyParams(period=Period(entity))

        if axis == "city":
            return CollectionEfficiencyParams(city=City(entity))

        if axis == "loan_type":
            return CollectionEfficiencyParams(loan_type=LoanType(entity))

        return CollectionEfficiencyParams()

    return None


# 4. MAIN NODE (compare_node)


def compare_node(
    state: AgentState,
    runtime: Runtime[AppContext],
) -> dict:

    # Debug start
    frame = inspect.currentframe()
    print("==============================================================")
    print(f"DEBUG: Entered function: {frame.f_code.co_name}")
    # Debug end

    intent: Intent = state.get("intent")
    enriched_query = state["enriched_query"]

    execution_context: ExecutionContext = state.get("execution_context")
    execution_context_dict = execution_context.to_dict() if execution_context else {}

    params_model = COMPARE_PARAM_MODELS.get(intent)
    target_node = INTENT_TO_NODE.get(intent)

    if not params_model or not target_node:
        print(
            f"DEBUG compare_node: either params_model is falsy or target_node is falsy"
        )
        print(f"DEBUG compare_node: returning error")
        print("==============================================================")
        return {"error": f"Compare not supported for intent: {intent}"}

    try:
        print(f"DEBUG compare_node: execution_context_dict : {execution_context_dict}")
        print(f"DEBUG compare_node: calling _extract_compare_params")

        # STEP 1: LLM extracts entities only
        compare = _extract_compare_entities(
            enriched_query=enriched_query,
            # intent=intent.value if hasattr(intent, "value") else intent,
            execution_context_dict=execution_context_dict,
            model_name=runtime.context.model_name,
            client=runtime.context.client,
        )

        print(f"DEBUG compare_node: returned back from _extract_compare_params")

        print(
            f"DEBUG compare_node: entity_a: {compare.entity_a} | label_a: {compare.label_a}"
        )
        print(
            f"DEBUG compare_node: entity_b: {compare.entity_b} | label_b: {compare.label_b}"
        )
        print(f"DEBUG compare_node: axis: {compare.axis}")

        print(f"DEBUG compare_node: calling _build_params")
        # STEP 2: build params deterministically
        param_a = _build_params(intent, compare.axis, compare.entity_a)
        print("DEBUG compare_node: returned back from _build_params")

        print(f"DEBUG compare_node: calling _build_params")
        param_b = _build_params(intent, compare.axis, compare.entity_b)
        print("DEBUG compare_node: returned back from _build_params")

        print(f"DEBUG compare_node: param_a: {param_a}")
        print(f"DEBUG compare_node: param_b: {param_b}")

        # STEP 3: cache keys
        print(f"DEBUG compare_node: calling _build_cache_key")
        key_a = _build_cache_key(intent.value, param_a.model_dump())
        print(f"DEBUG compare_node: returned back from _build_cache_key")
        print(f"DEBUG compare_node: calling _build_cache_key")
        key_b = _build_cache_key(intent.value, param_b.model_dump())
        print(f"DEBUG compare_node: returned back from _build_cache_key")

        retrieved_data = state.get("retrieved_data", {})

        print(f"DEBUG compare_node: retrieved_data: {retrieved_data}")
        print(f"DEBUG compare_node: key_a: {key_a}")
        print(f"DEBUG compare_node: key_a in cache: {key_a in retrieved_data}")
        print(f"DEBUG compare_node: key_b: {key_b}")
        print(f"DEBUG compare_node: key_b in cache: {key_b in retrieved_data}")

        # STEP 4: reuse optimization
        is_single = (
            execution_context
            and execution_context.last_tool_result
            and execution_context.last_intent
            == (intent.value if hasattr(intent, "value") else intent)
            and key_a in retrieved_data
        )

        # scenario: one param from history -- only need slot_b
        if is_single:
            print(
                f"DEBUG compare_node: We already have data for side A. We only need to fetch side B"
            )
            print("======================================================")

            return {
                "tool_params": param_b,
                "tool_result": None,
                "compare_keys": [key_a, key_b],
                "_compare_labels": {
                    key_a: compare.label_a,
                    key_b: compare.label_b,
                },
                "error": None,
            }

        # scenario: both params explicit -- need two tool calls
        # store both param sets; route_compare will Send them
        print(f"DEBUG compare_node: both sides A and B must be fetched.")
        print("==========================================================")
        return {
            "tool_params": param_a,
            "tool_result": None,
            "compare_keys": [key_a, key_b],
            "_compare_labels": {
                key_a: compare.label_a,
                key_b: compare.label_b,
            },
            "_compare_param_b": param_b,
            "error": None,
        }

    except Exception as e:
        print("DEBUG compare_node: exception occurred:")
        print(f"DEBUG compare_node: error: {e}")
        print("DEBUG compare_node: returning error")
        print("==========================================================")

        return {"error": f"Compare node failed: {str(e)}"}


# ROUTE FUNCTION
# CONDITIONAL EDGE -- dispatches Send objects after compare_node


def route_compare(state: AgentState) -> list[Send] | str:
    """
    Conditional edge function after compare_node.
    Reads prepared compare state and dispatches Send objects.
    Returns list[Send] for parallel execution or str for error routing.
    """
    # Debug start
    frame = inspect.currentframe()
    print("==============================================================")
    print(f"DEBUG: Entered function: {frame.f_code.co_name}")
    # Debug end

    if state.get("error"):
        return "handle_error"

    intent: Intent = state.get("intent")
    target_node = INTENT_TO_NODE.get(intent)

    param_b = state.get("_compare_param_b")

    if not target_node:
        return "handle_error"

    # single send -- one param from history
    if param_b is None:
        print(f"DEBUG route_compare: single Send")
        print("=====================================================")
        return [
            Send(
                target_node,
                {
                    **state,
                    "tool_result": None,
                },
            )
        ]

    # dual send -- both params explicit
    print(f"DEBUG route_compare: dual Send")
    print("=====================================================")
    return [
        Send(
            target_node,
            {
                **state,
                "tool_result": None,
            },
        ),
        Send(
            target_node,
            {
                **state,
                "tool_params": param_b,
                "tool_result": None,
            },
        ),
    ]
