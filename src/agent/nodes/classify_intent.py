from typing import get_args
from pydantic import BaseModel
import json
from openai import OpenAI

from agent.utils import _call_llm

from agent.agent_state import (
    AgentState,
    CustomerProfileParams,
    OverdueLoansParams,
    RepaymentSummaryParams,
    LoanPortfolioStatsParams,
    CollectionEfficiencyParams,
    Intent
)


# MAPPING : intent -> its parameter model
INTENT_PARAMS_MAP: dict[str, type[BaseModel] | None] = {
    "get_customer_profile": CustomerProfileParams,
    "get_overdue_loans": OverdueLoansParams,
    "get_repayment_summary": RepaymentSummaryParams,
    "get_loan_portfolio_stats": LoanPortfolioStatsParams,
    "get_collection_efficiency": CollectionEfficiencyParams,
    "get_help": None,
    "unknown": None,   # no params for unknown intent
}

# VALID INTENT SCHEMA:
class ValidIntent(BaseModel):
    intent: Intent


# STEP 1 — CLASSIFY INTENT
def _classify_intent(user_query: str,
                     model_name: str,
                     client: OpenAI,
                     ) -> str:
    """
    Returns intent string e.g. 'get_overdue_loans'.
    """

    valid_intents = list(get_args(Intent))

    prompt = f"""You are a banking assistant intent classifier.

    Given a user query, classify it into exactly one intent from this list:
    {valid_intents}

    Intent definitions:
    - get_customer_profile: user wants info about a specific customer
    - get_overdue_loans: user wants to see loans that are overdue or past due
    - get_repayment_summary: user wants repayment history of a specific customer or loan
    - get_loan_portfolio_stats: user wants aggregate stats across all loans
    - get_high_risk_customers: user wants to find risky customers
    - get_collection_efficiency: user wants to see how well overdue loans are being recovered
    - get_officer_workload: user wants to see loans assigned to a specific officer
    - get_help: user is asking what the agent can do, asking for help, examples, or capabilities
    - unknown: query does not match any of the above

    User query: {user_query}

    Respond with JSON only. No explanation.
    """

    output = _call_llm(user_prompt=prompt,
                       model_class=ValidIntent,
                       model_name= model_name,
                       client = client,
                       max_tokens=50)

    parsed = ValidIntent.model_validate_json(output)
    return parsed.intent


# STEP 2 — EXTRACT PARAMETERS

def _extract_params(user_query: str,
                    intent: str,
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

    prompt = f"""You are a banking assistant parameter extractor.

    The user query has been classified as intent: {intent}

    RULES:
    - Only extract values EXPLICITLY mentioned in the query.
    - If not mentioned, set to null. No exceptions.

    Example:
    Query: "Get overdue loans in Mumbai"
    Correct:   {{"city": "Mumbai", "loan_type": null, "min_days_overdue": null}}
    Incorrect: {{"city": "Mumbai", "loan_type": "Personal", "min_days_overdue": null}}

    Parameter schema:
    {json.dumps(params_schema, indent=2)}

    User query: {user_query}

    Respond with JSON only. No explanation.
    """

    output = _call_llm(user_prompt = prompt,
                       model_class = params_class,
                       model_name = model_name,
                       client = client,
                       max_tokens = 200)

    parsed = params_class.model_validate_json(output)
    return parsed


# LANGGRAPH NODE
def parse_node(state: AgentState,
               client: OpenAI,
               model_name: str,
               ) -> dict:
    """
    LangGraph node — extracts intent and respective parameters.
    Returns partial state.
    """
    user_query = state["user_query"]

    try:
        # Call 1 — get intent
        intent = _classify_intent(user_query,
                                  client = client,
                                  model_name = model_name
                                  )

        # Call 2 — get params for that intent
        tool_params = _extract_params(user_query = user_query,
                                      intent = intent,
                                      client = client,
                                      model_name = model_name,
                                      )

        return {
            "intent":      intent,
            "tool_params": tool_params,
            "error":       None        # clear any previous error
        }

    except Exception as e:
        return {
            "intent":      "unknown",
            "tool_params": None,
            "error":       f"Intent classification failed: {str(e)}"
        }