from pydantic import BaseModel
import json
from openai import OpenAI

from langgraph.runtime import Runtime
from agent.runtime_context import AppContext

from langchain_core.messages import BaseMessage
from collections.abc import Sequence

from agent.utils import _call_llm, _serialize_messages

from agent.agent_state import (
    AgentState,
    ExecutionContext,
    CustomerProfileParams,
    OverdueLoansParams,
    RepaymentSummaryParams,
    LoanPortfolioStatsParams,
    CollectionEfficiencyParams,
    Intent,
)

# MAPPING : intent -> its parameter model
INTENT_PARAMS_MAP: dict[str, type[BaseModel] | None] = {
    Intent.GET_CUSTOMER_PROFILE: CustomerProfileParams,
    Intent.GET_OVERDUE_LOANS: OverdueLoansParams,
    Intent.GET_REPAYMENT_SUMMARY: RepaymentSummaryParams,
    Intent.GET_LOAN_PORTFOLIO_STATS: LoanPortfolioStatsParams,
    Intent.GET_COLLECTION_EFFICIENCY: CollectionEfficiencyParams,
    Intent.GET_POLICY_INFO: None,
    Intent.GET_HELP: None,
    Intent.UNKNOWN: None,
}


# VALID INTENT SCHEMA:
class ValidIntent(BaseModel):
    intent: Intent


# # HELPERS
# def _is_valid_value(v):
#     return v is not None and v != "" and v is not False


# NOTE: The query is already fully resolved - all pronouns and references have been
# replaced with explicit values by the context resolver. No history needed.

# for debuging
import inspect

# STEP 1 - CLASSIFY INTENT


def _classify_intent(
    user_query: str,
    execution_context_dict: dict,
    model_name: str,
    client: OpenAI,
) -> Intent:
    """
    Returns intent string e.g. 'get_overdue_loans'.
    """

    # Debug start
    frame = inspect.currentframe()
    print("---------------------------------------------------------------")
    print(f"DEBUG: Entered function: {frame.f_code.co_name}")

    caller_frame = frame.f_back
    caller_function = caller_frame.f_code.co_name if caller_frame else "<module>"
    print(f"DEBUG _classify_intent: Called from: {caller_function}")
    # Debug end

    valid_intents = {i.value for i in Intent}

    prompt = f"""You are a banking assistant intent classifier.
 
Given a user query, classify it into exactly one intent from this list:
{valid_intents}
 
Intent definitions:
- get_customer_profile: user wants info about a specific customer
- get_overdue_loans: user wants to see loans that are overdue or past due
- get_repayment_summary: user wants repayment history of a specific customer or loan
- get_loan_portfolio_stats: user wants aggregate stats across all loans
- get_collection_efficiency: user wants to see how well overdue loans are being recovered
- get_policy_info: user is asking about banking policy, RBI rules, NPA definitions, SMA classification, provisioning norms, or any regulatory/policy concept
- get_help: user is asking what the agent can do, asking for help, examples, or capabilities
- unknown: query does not match any of the above
  
Execution context:
{json.dumps(execution_context_dict, indent=2)}
 
Current user query:
{user_query}
 
Respond with JSON only. No explanation.
"""

    output = _call_llm(
        user_prompt=prompt,
        model_class=ValidIntent,
        model_name=model_name,
        client=client,
        max_tokens=50,
    )

    print(f"DEBUG _classify_intent: rturned: {output.intent}")
    print("-------------------------------------------------------")

    return output.intent


# STEP 2 - EXTRACT PARAMETERS


def _extract_params(
    user_query: str,
    intent: Intent,
    execution_context_dict: dict,
    model_name: str,
    client: OpenAI,
) -> BaseModel | None:
    """
    Returns the correct populated params or None for unknown intent.
    """

    # Debug start
    frame = inspect.currentframe()
    print("---------------------------------------------------------------")
    print(f"DEBUG: Entered function: {frame.f_code.co_name}")

    caller_frame = frame.f_back
    caller_function = caller_frame.f_code.co_name if caller_frame else "<module>"
    print(f"DEBUG _extract_params: Called from: {caller_function}")
    # Debug end

    params_class = INTENT_PARAMS_MAP.get(intent)

    if params_class is None:
        return None

    params_schema = params_class.model_json_schema()

    prompt = f"""You are a banking assistant parameter extractor.
 
The user query has been classified as intent: {intent.value}
 
RULES:
- Only extract values EXPLICITLY mentioned in the query.
- OR clearly inferable from conversation context.
- If not mentioned, set to null. No exceptions.
  
Execution context:
{json.dumps(execution_context_dict, indent=2)}
 
Parameter schema:
{json.dumps(params_schema, indent=2)}
 
Current user query:
{user_query}
 
Example:
Query: "Get overdue loans in Mumbai"
Correct:   {{"city": "Mumbai", "loan_type": null, "min_days_overdue": null}}
Incorrect: {{"city": "Mumbai", "loan_type": "Personal", "min_days_overdue": null}}
 
Respond with JSON only. No explanation.
"""

    output = _call_llm(
        user_prompt=prompt,
        model_class=params_class,
        model_name=model_name,
        client=client,
        max_tokens=300,
    )

    print(f"DEBUG _extract_params: rturned: {output}")
    print("-------------------------------------------------------")

    return output


# def parse_node(state: AgentState, runtime: Runtime[AppContext]) -> dict:
#     try:
#         # Always use enriched_query if available
#         query = state.get("enriched_query") or state["user_query"]
#         execution_context = state.get("execution_context", {})

#         print("==========================================================")
#         print(f"DEBUG:in parse_node:")
#         print(f"DEBUG:post messages: {state.get('messages',[])}")
#         print(f"DEBUG:initial execution_context: {execution_context}")
#         print("==========================================================")

#         intent = _classify_intent(
#             user_query=query,  # fully resolved, no ambiguity
#             messages=[],  # no history needed anymore
#             execution_context=execution_context,
#             model_name=runtime.context.model_name,
#             client=runtime.context.client,
#         )

#         tool_params = _extract_params(
#             user_query=query,
#             intent=intent,
#             messages=[],  # no history needed anymore
#             execution_context=execution_context,
#             model_name=runtime.context.model_name,
#             client=runtime.context.client,
#         )

#         # Update execution context
#         updates = {
#             "customer_id": "current_customer_id",
#             "city": "current_city",
#             "loan_type": "current_loan_type",
#             "loan_id": "current_loan_id",
#             "period": "selected_period",
#         }
#         for field, ctx_key in updates.items():
#             value = getattr(tool_params, field, None)
#             if _is_valid_value(value):
#                 execution_context[ctx_key] = value

#         print("==========================================================")
#         print(f"DEBUG:Intent: { intent.value}")
#         print(f"DEBUG:tool_params: {tool_params}")
#         print(f"DEBUG:post messages: {state.get('messages',[])}")
#         print(f"DEBUG:post execution_context: {execution_context}")
#         print("==========================================================")

#         return {
#             "intent": intent,
#             "tool_params": tool_params,
#             "execution_context": execution_context,
#             "error": None,
#         }

#     except Exception as e:
#         print("==========================================================")
#         print(f"in parse_node exception occured:")
#         print(f"error: {e}")
#         print("==========================================================")
#         return {
#             "intent": Intent.UNKNOWN,
#             "tool_params": None,
#             "execution_context": state.get("execution_context", {}),
#             "error": f"Parse node failed: {str(e)}",
#         }

# PARSE NAODE


def parse_node(state: AgentState, runtime: Runtime[AppContext]) -> dict:
    """
    Classifies intent and extracts tool parameters from the enriched query.

    Ownership rules:
      - This node writes ONLY to: intent, tool_params, error
    """
    # Debug start
    frame = inspect.currentframe()
    print("===========================================================")
    print(f"DEBUG: Entered function: {frame.f_code.co_name}")

    # Debug end

    try:
        query = state.get("enriched_query")

        # execution_context is an ExecutionContext BaseModel - serialize for LLM prompt
        execution_context = state.get("execution_context")
        if execution_context:
            # strip heavy fields -- last_tool_result and last_response are too large
            # for intent classification and param extraction
            raw = execution_context.to_dict()
            execution_context_dict = {
                k: v
                for k, v in raw.items()
                if k
                not in (
                    "last_tool_result",
                    "last_response",
                    "compare_slot_a",
                    "compare_slot_b",
                )
            }
        else:
            execution_context_dict = {}

        print(f"DEBUG parse_node: query: {query}")
        print(f"DEBUG parse_node: execution_context: {execution_context_dict}")

        print(f"DEBUG parse_node: calling _classify_intent...")
        intent = _classify_intent(
            user_query=query,
            execution_context_dict=execution_context_dict,
            model_name=runtime.context.model_name,
            client=runtime.context.client,
        )

        print(f"DEBUG parse_node: returned back from _classify_intent")

        print(f"DEBUG parse_node: calling _extract_params...")
        tool_params = _extract_params(
            user_query=query,
            intent=intent,
            execution_context_dict=execution_context_dict,
            model_name=runtime.context.model_name,
            client=runtime.context.client,
        )

        print(f"DEBUG parse_node: returned back from _extract_params.")

        print(f"DEBUG parse_node: intent: {intent.value}")
        print(f"DEBUG parse_node: tool_params: {tool_params}")
        print("==========================================================")

        return {
            "intent": intent,
            "tool_params": tool_params,
            "error": None,
        }

    except Exception as e:
        print("DEBUG parse_node: in parse_node exception occurred:")
        print(f"DEBUG parse_node: error: {e}")
        print(f"DEBUG context_node: returning default values")
        print("==========================================================")

        return {
            "intent": Intent.UNKNOWN,
            "tool_params": None,
            "error": f"Parse node failed: {str(e)}",
        }
