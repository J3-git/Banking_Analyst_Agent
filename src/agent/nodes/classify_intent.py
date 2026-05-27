from typing import get_args
from pydantic import BaseModel
import json
from openai import OpenAI

from langgraph.runtime import Runtime
from agent.runtime_context import AppContext

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)
from collections.abc import Sequence

from agent.utils import _call_llm

from agent.agent_state import (
    AgentState,
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
    Intent.GET_HELP: None,
    Intent.UNKNOWN: None,  # no params for unknown intent
}


# VALID INTENT SCHEMA:
class ValidIntent(BaseModel):
    intent: Intent


# HELPERS


def _is_valid_value(v):
    return v is not None and v != "" and v is not False


def _serialize_messages(messages: Sequence[BaseMessage], max_messages: int = 5) -> str:
    """
    Convert recent messages into prompt-friendly text.
    Supports LangGraph's native message sequence wrappers safely.
    """
    # 1. Fallback to empty list if None is passed
    if not messages:
        return ""

    # 2. Safely grab the last N elements from the sequence
    # This works flawlessly across lists and LangGraph sequence proxies
    recent_messages = list(messages)[-max_messages:]

    lines = []

    for msg in recent_messages:
        if isinstance(msg, HumanMessage):
            role = "User"
        elif isinstance(msg, AIMessage):
            role = "Assistant"
        elif isinstance(msg, SystemMessage):
            role = "System"
        else:
            role = "Unknown"
        lines.append(f"{role}: {msg.content}")

    return "\n".join(lines)


# STEP 1 — CLASSIFY INTENT
def _classify_intent(
    user_query: str,
    messages: Sequence[BaseMessage],
    execution_context: dict,
    model_name: str,
    client: OpenAI,
) -> Intent:
    """
    Returns intent string e.g. 'get_overdue_loans'.
    """

    valid_intents = {i.value for i in Intent}
    conversation_history = _serialize_messages(messages)

    prompt = f"""You are a banking assistant intent classifier.

    Given a user query, classify it into exactly one intent from this list:
    {valid_intents}

    Intent definitions:
    - get_customer_profile: user wants info about a specific customer
    - get_overdue_loans: user wants to see loans that are overdue or past due
    - get_repayment_summary: user wants repayment history of a specific customer or loan
    - get_loan_portfolio_stats: user wants aggregate stats across all loans
    - get_collection_efficiency: user wants to see how well overdue loans are being recovered
    - get_help: user is asking what the agent can do, asking for help, examples, or capabilities
    - unknown: query does not match any of the above

    IMPORTANT:
    Use BOTH:
    1. current query
    2. conversation history

    to resolve references like:
    - them
    - those loans
    - same customer
    - export it

    Conversation history:
    {conversation_history}

    Execution context:
    {json.dumps(execution_context, indent=2)}

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

    # parsed = ValidIntent.model_validate_json(output)
    # return parsed.intent

    return output.intent


# STEP 2 — EXTRACT PARAMETERS


def _extract_params(
    user_query: str,
    intent: Intent,
    messages: Sequence[BaseMessage],
    execution_context: dict,
    model_name: str,
    client: OpenAI,
) -> BaseModel | None:
    """
    Returns the correct populated params or None for unknown intent.
    """

    params_class = INTENT_PARAMS_MAP.get(intent)

    # No params needed for unknown intent
    if params_class is None:
        return None

    params_schema = params_class.model_json_schema()
    conversation_history = _serialize_messages(messages)

    prompt = f"""You are a banking assistant parameter extractor.

    The user query has been classified as intent: {intent.value}

    RULES:
    - Only extract values EXPLICITLY mentioned in the query.
    - OR clearly inferable from conversation context
    - If not mentioned, set to null. No exceptions.

    Conversation history:
    {conversation_history}

    Execution context:
    {json.dumps(execution_context, indent=2)}

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
        max_tokens=200,
    )

    # parsed = params_class.model_validate_json(output)
    # return parsed

    return output


# LANGGRAPH NODE
def parse_node(state: AgentState, runtime: Runtime[AppContext]) -> dict:
    """
    LangGraph node — extracts intent and respective parameters.
    Returns partial state.
    """
    try:
        # print(f"model name: {runtime.context.model_name}")
        messages = list(state.get("messages", []))
        execution_context = state.get("execution_context", {})

        messages.append(HumanMessage(content=state["user_query"]))
        # Call 1 — get intent
        intent = _classify_intent(
            user_query=state["user_query"],
            messages=state["messages"],
            execution_context=state["execution_context"],
            model_name=runtime.context.model_name,
            client=runtime.context.client,
        )

        print(f"after intent: {intent.value}")

        # Call 2 — get params for that intent
        tool_params = _extract_params(
            user_query=state["user_query"],
            intent=intent,
            messages=state["messages"],
            execution_context=state["execution_context"],
            model_name=runtime.context.model_name,
            client=runtime.context.client,
        )

        print(f"after tool_params: {messages}")

        execution_context.update({"last_tool": "parse_node", "intent": intent.value})

        updates = {
            "customer_id": "current_customer_id",
            "city": "current_city",
            "loan_type": "current_loan_type",
            "loan_id": "current_loan_id",
            "period": "selected_period",
        }

        # Update EXECUTION CONTEXT
        for field, ctx_key in updates.items():
            value = getattr(tool_params, field, None)
            if _is_valid_value(value):
                execution_context[ctx_key] = value

        return {
            "intent": intent,
            "tool_params": tool_params,
            "execution_context": execution_context,
            "error": None,
        }

    except Exception as e:

        return {
            "intent": Intent.UNKNOWN,
            "tool_params": None,
            "execution_context": state.get("execution_context", {}),
            "error": f"Parse node failed: {str(e)}",
        }
