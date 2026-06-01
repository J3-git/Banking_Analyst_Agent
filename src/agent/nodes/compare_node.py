import json
from langgraph.types import Send
from langgraph.runtime import Runtime
from pydantic import BaseModel
from agent.agent_state import (
    AgentState,
    ExecutionContext,
    Intent,
    OverdueLoansParams,
    LoanPortfolioStatsParams,
    CollectionEfficiencyParams,
)
from agent.runtime_context import AppContext
from agent.utils import _call_llm

# PARAM EXTRACTION FOR COMPARE

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


class CompareParamsOutput(BaseModel):
    param_a: dict
    param_b: dict
    label_a: str
    label_b: str


def _extract_compare_params(
    enriched_query: str,
    intent: str,
    params_schema: dict,
    execution_context_dict: dict,
    model_name: str,
    client,
) -> CompareParamsOutput:
    """
    Extracts two sets of params from a compare query.
    e.g. "compare Mumbai vs Delhi" -> param_a: {city: Mumbai}, param_b: {city: Delhi}
    """

    prompt = f"""You are a banking assistant parameter extractor for comparison queries.

The user wants to compare two scenarios for intent: {intent}

Extract TWO sets of parameters and a human-readable label for each.

Rules:
- param_a: first entity mentioned OR the one from execution context (history)
- param_b: second entity mentioned (the new one being compared)
- label_a / label_b: short human-readable label e.g. "Mumbai", "Last Month", "Personal Loans"
- Only extract values explicitly mentioned or clearly inferable from context
- If a param is not mentioned, set to null

Execution context (contains last fetched params if one side is from history):
{json.dumps(execution_context_dict, indent=2)}

Parameter schema:
{json.dumps(params_schema, indent=2)}

User query: {enriched_query}

Respond with JSON only:
{{
  "param_a": {{...}},
  "param_b": {{...}},
  "label_a": "...",
  "label_b": "..."
}}
"""

    return _call_llm(
        user_prompt=prompt,
        model_class=CompareParamsOutput,
        model_name=model_name,
        client=client,
        max_tokens=300,
    )


def _build_cache_key(intent: str, params: dict) -> str:
    """Build cache key matching tool node pattern."""
    if intent == "get_overdue_loans":
        return (
            f"overdue_loans:"
            f"{params.get('city') or 'all'}:"
            f"{params.get('loan_type') or 'all'}:"
            f"{params.get('min_days_overdue') or 1}"
        )
    if intent == "get_loan_portfolio_stats":
        return (
            f"portfolio_stats:"
            f"{params.get('group_by') or 'loan_type'}:"
            f"{params.get('city') or 'all'}:"
            f"{params.get('loan_type') or 'all'}"
        )
    if intent == "get_collection_efficiency":
        return (
            f"collection_efficiency:"
            f"{params.get('city') or 'all'}:"
            f"{params.get('loan_type') or 'all'}:"
            f"{params.get('period') or 'full'}"
        )
    return f"{intent}:{json.dumps(params, sort_keys=True)}"


# MAIN NODE -- prepares compare state (LLM call, writes compare_keys etc.)


def compare_node(
    state: AgentState,
    runtime: Runtime[AppContext],
) -> dict:
    """
    Calls LLM to extract two param sets from the compare query.
    Writes compare_keys, _compare_labels, tool_params into state.
    Returns a dict -- route_compare (conditional edge) handles Send dispatch.

    Ownership rules:
    - Writes ONLY to: compare_keys, _compare_labels, tool_params, error
    - Does NOT touch execution_context
    """

    intent: Intent = state.get("intent")
    enriched_query = state["enriched_query"]
    execution_context: ExecutionContext = state.get("execution_context")
    execution_context_dict = execution_context.to_dict() if execution_context else {}

    params_model = COMPARE_PARAM_MODELS.get(intent)
    target_node = INTENT_TO_NODE.get(intent)

    if not params_model or not target_node:
        return {"error": f"Compare not supported for intent: {intent}"}

    try:
        compare_params = _extract_compare_params(
            enriched_query=enriched_query,
            intent=intent.value if hasattr(intent, "value") else intent,
            params_schema=params_model.model_json_schema(),
            execution_context_dict=execution_context_dict,
            model_name=runtime.context.model_name,
            client=runtime.context.client,
        )

        param_a = compare_params.param_a
        param_b = compare_params.param_b
        label_a = compare_params.label_a
        label_b = compare_params.label_b

        key_a = _build_cache_key(
            intent.value if hasattr(intent, "value") else intent,
            param_a,
        )
        key_b = _build_cache_key(
            intent.value if hasattr(intent, "value") else intent,
            param_b,
        )

        retrieved_data = state.get("retrieved_data", {})

        print("==========================================================")
        print("DEBUG: in compare_node:")
        print(f"DEBUG: intent: {intent}")
        print(f"DEBUG: param_a: {param_a} label_a: {label_a}")
        print(f"DEBUG: param_b: {param_b} label_b: {label_b}")
        print(f"DEBUG: key_a in cache: {key_a in retrieved_data}")
        print(f"DEBUG: key_b in cache: {key_b in retrieved_data}")
        print("==========================================================")

        # scenario: one param from history -- only need slot_b
        is_single = (
            execution_context
            and execution_context.last_tool_result
            and execution_context.last_intent
            == (intent.value if hasattr(intent, "value") else intent)
            and key_a in retrieved_data
        )

        if is_single:
            validated_b = params_model(**param_b)
            return {
                "tool_params": validated_b,
                "tool_result": None,
                "compare_keys": [key_a, key_b],
                "_compare_labels": {key_a: label_a, key_b: label_b},
                "error": None,
            }

        # scenario: both params explicit -- need two tool calls
        # store both param sets; route_compare will Send them
        validated_a = params_model(**param_a)
        validated_b = params_model(**param_b)

        return {
            "tool_params": validated_a,  # used by first Send
            "tool_result": None,
            "compare_keys": [key_a, key_b],
            "_compare_labels": {key_a: label_a, key_b: label_b},
            "_compare_param_b": param_b,  # stored for route_compare to build second Send
            "error": None,
        }

    except Exception as e:
        print("==========================================================")
        print("DEBUG: in compare_node exception occurred:")
        print(f"DEBUG: error: {e}")
        print("==========================================================")

        return {"error": f"Compare node failed: {str(e)}"}


# CONDITIONAL EDGE -- dispatches Send objects after compare_node


def route_compare(state: AgentState) -> list[Send] | str:
    """
    Conditional edge function after compare_node.
    Reads prepared compare state and dispatches Send objects.
    Returns list[Send] for parallel execution or str for error routing.
    """

    if state.get("error"):
        return "handle_error"

    intent: Intent = state.get("intent")
    target_node = INTENT_TO_NODE.get(intent)

    if not target_node:
        return "handle_error"

    compare_keys = state.get("compare_keys", [])
    compare_labels = state.get("_compare_labels", {})
    tool_params = state.get("tool_params")
    param_b_raw = state.get("_compare_param_b")

    params_model = COMPARE_PARAM_MODELS.get(intent)

    # single Send -- one param from history
    if param_b_raw is None:
        return [
            Send(
                target_node,
                {
                    **state,
                    "tool_result": None,
                    "compare_keys": compare_keys,
                    "_compare_labels": compare_labels,
                },
            )
        ]

    # dual Send -- both params explicit
    validated_b = params_model(**param_b_raw)
    return [
        Send(
            target_node,
            {
                **state,
                "tool_result": None,
                "compare_keys": compare_keys,
                "_compare_labels": compare_labels,
            },
        ),
        Send(
            target_node,
            {
                **state,
                "tool_params": validated_b,
                "tool_result": None,
                "compare_keys": compare_keys,
                "_compare_labels": compare_labels,
            },
        ),
    ]
