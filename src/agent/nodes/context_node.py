from langgraph.runtime import Runtime
from agent.runtime_context import AppContext
from pydantic import BaseModel

# from langchain_core.messages import BaseMessage
# from collections.abc import Sequence

from agent.agent_state import AgentState

from agent.utils import _call_llm, _serialize_messages

import json


class ContextOutput(BaseModel):
    enriched_query: str
    needs_db: bool
    reasoning: str  # for logs/debugging only


def context_node(state: AgentState, runtime: Runtime[AppContext]) -> dict:
    messages = list(state.get("messages", []))

    # No history — nothing to enrich
    if not messages:
        return {
            "enriched_query": state["user_query"],
            "needs_db": True,
        }

    conversation_history = _serialize_messages(messages)
    execution_context = state.get("execution_context", {})

    prompt = f"""You are a context resolver for a banking loan analyst agent.

Analyse the conversation history and current query. Output:
- enriched_query: fully self-contained rewrite (no ambiguous references)
- needs_db: whether a new database call is required
- reasoning: one line for logs

TOOLS AND REQUIRED PARAMS
Customer Profile        — required: customer_id
Overdue Loans           — optional: city, loan_type, min_days_overdue
Repayment Summary       — required: customer_id | optional: loan_id
Loan Portfolio Stats    — optional: group_by, city, loan_type
Collection Efficiency   — optional: city, loan_type, period

RESOLUTION RULES
- Replace all pronouns/references using history or execution_context:
  "his/her/same customer" → customer_id | "those loans" → loan_id
  "that city" → city | "same period" → period
- If a required param is missing from query but exists in execution_context, inject it.
- If a reference cannot be resolved, preserve it as-is and set needs_db: true.
- If nothing needs resolving, return the original query unchanged.

NEEDS_DB RULES
- Check execution_context first:
  if requested field is in execution_context → needs_db: false
- Check last_fetched_fields:
  if requested field was already fetched this session → needs_db: false  
- needs_db: true only if none of the above apply


EDGE CASES
Follow-up on fetched data
  history: Customer Profile fetched for customer 1
  query: "what is his name"
  → enriched_query: "what is the name of customer_id 1" | needs_db: false

Different tool, same customer
  history: Customer Profile fetched for customer 1
  query: "show his repayment history"
  → enriched_query: "repayment history for customer_id 1" | needs_db: true

Same tool, different customer
  history: Customer Profile fetched for customer 1
  query: "show profile of customer 2"
  → enriched_query: "profile of customer_id 2" | needs_db: true

Partial filter change
  history: Overdue Loans fetched — city: Mumbai, loan_type: personal
  query: "now show me home loans"
  → enriched_query: "overdue home loans in Mumbai" | needs_db: true

Unresolvable reference
  history: no customer mentioned
  query: "show his repayment history"
  → enriched_query: "repayment history for customer_id unknown" | needs_db: true

Period change
  history: Collection Efficiency fetched for this month
  query: "how about last month"
  → enriched_query: "collection efficiency for last month" | needs_db: true

Follow-up on aggregate data
  history: Loan Portfolio Stats fetched (default rate by city)
  query: "which city had the highest default rate"
  → enriched_query: unchanged | needs_db: false

Conversation history:
{conversation_history}

Execution context:
{json.dumps(execution_context, indent=2)}

Current query: {state["user_query"]}

OUTPUT — JSON only, no explanation
{{
  "enriched_query": "<fully resolved, self-contained query>",
  "needs_db": true or false,
  "reasoning": "<one line>"
}}
"""

    output = _call_llm(
        user_prompt=prompt,
        model_class=ContextOutput,
        model_name=runtime.context.model_name,
        client=runtime.context.client,
        max_tokens=200,
    )

    print(f"DEBUG: in context node:")
    print(f"DEBUG: conversation_history: {conversation_history}")
    print(f"DEBUG: execution_context: {execution_context}")
    print(f"DEBUG: enriched_query: {output.enriched_query}")
    print(f"DEBUG: needs_db: {output.needs_db}")
    print(f"DEBUG: resoning: {output.reasoning}")

    return {
        "enriched_query": output.enriched_query,
        "needs_db": output.needs_db,
    }
