# prompt = f"""You are a context resolver for a banking loan analyst agent.

# Analyse the conversation history and current query. Output:
# - enriched_query: fully self-contained rewrite (no ambiguous references)
# - needs_db: whether a new database call is required
# - is_followup: whether this query refers to, filters, drills into, compares, or visualizes previously fetched data
# - follow_up_type: classify the type of follow-up (or "none" if not a follow-up)
# - reasoning: one line for logs

# TOOLS AND REQUIRED PARAMS
# Customer Profile        -- required: customer_id
# Overdue Loans           -- optional: city, loan_type, min_days_overdue
# Repayment Summary       -- required: customer_id | optional: loan_id
# Loan Portfolio Stats    -- optional: group_by, city, loan_type
# Collection Efficiency   -- optional: city, loan_type, period

# RESOLUTION RULES
# - Replace all pronouns/references using history or execution_context:
#   "his/her/same customer" -> customer_id | "those loans" -> loan_id
#   "that city" -> city | "same period" -> period
# - If a required param is missing from query but exists in execution_context, inject it.
# - If a reference cannot be resolved, preserve it as-is and set needs_db: true.
# - If nothing needs resolving, return the original query unchanged.

# NEEDS_DB RULES
# - Check execution_context first:
#   if requested field is in execution_context -> needs_db: false
# - Check last_fetched_fields:
#   if requested field was already fetched this session -> needs_db: false
# - needs_db: true only if none of the above apply

# IS_FOLLOWUP RULES
# - is_followup: true if the query refers to, filters, drills into, compares,
#   or visualizes previously fetched data
# - is_followup: false if it is a fresh independent question with no dependency
#   on prior results

# FOLLOW_UP_TYPE RULES
# - "compare"       : user wants to compare two entities (Mumbai vs Delhi, this month vs last month)
# - "drill_down"    : user wants more detail on a subset of fetched data
# - "visualize"     : user wants a chart or graph of fetched data
# - "report"        : user wants a structured report of fetched data
# - "conversational": user asks a question answerable from history, no new data needed
# - "none"          : fresh independent query, not a follow-up at all

# COMPARE DETECTION -- also applies to first-turn queries:
# - If the query mentions two explicit entities to compare (cities, periods, loan types),
#   set follow_up_type: "compare" even if is_followup is false

# ROUTING OUTCOME (for your reasoning -- do not output this field)
# - is_followup: true  + needs_db: false -> followup node (answer from history/context)
# - is_followup: true  + needs_db: true  -> parse node (re-run tool with new params)
# - is_followup: false + needs_db: true  -> parse node (fresh query)
# - is_followup: false + needs_db: false -> followup node (edge case, treat as conversational)

# EDGE CASES

# Follow-up on fetched data
#   history: Customer Profile fetched for customer 1
#   query: "what is his name"
#   -> enriched_query: "what is the name of customer_id 1"
#   -> needs_db: false | is_followup: true | follow_up_type: conversational

# Different tool, same customer
#   history: Customer Profile fetched for customer 1
#   query: "show his repayment history"
#   -> enriched_query: "repayment history for customer_id 1"
#   -> needs_db: true | is_followup: true

# Same tool, different customer
#   history: Customer Profile fetched for customer 1
#   query: "show profile of customer 2"
#   -> enriched_query: "profile of customer_id 2"
#   -> needs_db: true | is_followup: false

# Partial filter change
#   history: Overdue Loans fetched -- city: Mumbai, loan_type: personal
#   query: "now show me home loans"
#   -> enriched_query: "overdue home loans in Mumbai"
#   -> needs_db: true | is_followup: true

# Unresolvable reference
#   history: no customer mentioned
#   query: "show his repayment history"
#   -> enriched_query: "repayment history for customer_id unknown"
#   -> needs_db: true | is_followup: false

# Period change
#   history: Collection Efficiency fetched for this month
#   query: "how about last month"
#   -> enriched_query: "collection efficiency for last month"
#   -> needs_db: true | is_followup: true

# Follow-up on aggregate data
#   history: Loan Portfolio Stats fetched (default rate by city)
#   query: "which city had the highest default rate"
#   -> enriched_query: unchanged
#   -> needs_db: false | is_followup: true

# Drill-down request
#   history: Overdue Loans fetched -- all cities
#   query: "break this down by loan type"
#   -> enriched_query: "overdue loans grouped by loan type"
#   -> needs_db: true | is_followup: true | follow_up_type: drill_down

# Compare request (follow-up)
#   history: Collection Efficiency fetched for Mumbai
#   query: "how does Delhi compare"
#   -> enriched_query: "collection efficiency for Delhi compared to Mumbai"
#   -> needs_db: true | is_followup: true | follow_up_type: compare

# Compare request (first turn, both explicit)
#   history: none
#   query: "loan portfolio stats Mumbai vs Delhi"
#   -> enriched_query: unchanged
#   -> needs_db: true | is_followup: false | follow_up_type: compare

# Visualization request
#   history: Loan Portfolio Stats fetched
#   query: "show me a chart of this"
#   -> enriched_query: "visualize loan portfolio stats as chart"
#   -> needs_db: false | is_followup: true | follow_up_type: visualize

# Fresh unrelated query
#   history: Customer Profile fetched for customer 1
#   query: "show overdue loans in Pune"
#   -> enriched_query: unchanged
#   -> needs_db: true | is_followup: false

# Conversation history:
# {conversation_history}

# Execution context:
# {json.dumps(execution_context_dict, indent=2, default=str)}

# Current query: {state["user_query"]}

# OUTPUT -- JSON only, no explanation
# {{
#   "enriched_query": "<fully resolved, self-contained query>",
#   "needs_db": true or false,
#   "is_followup": true or false,
#   "follow_up_type": "compare" | "drill_down" | "visualize" | "report" | "conversational" | "none",
#   "reasoning": "<one line>"
# }}
# """


from langgraph.runtime import Runtime
from agent.runtime_context import AppContext
from pydantic import BaseModel
from agent.agent_state import AgentState, ExecutionContext, FollowUpType
from agent.utils import _call_llm, _serialize_messages
import json

# for debugging
import inspect


class ContextOutput(BaseModel):
    enriched_query: str
    needs_db: bool
    is_followup: bool
    follow_up_type: (
        str  # compare | drill_down | visualize | report | conversational | none
    )
    reasoning: str  # for logs/debugging only


def context_node(state: AgentState, runtime: Runtime[AppContext]) -> dict:

    # Debug start
    frame = inspect.currentframe()
    print("===========================================================")
    print(f"DEBUG: Entered function: {frame.f_code.co_name}")
    # Debug end

    messages = list(state.get("messages", []))

    # No history -- fresh query, nothing to enrich
    if not messages:
        # Debug start
        print(f"DEBUG context_node: fresh query")
        print(f"DEBUG context_node: returning default values")
        print("===========================================================")
        # Debug end
        return {
            "enriched_query": state["user_query"],
            "needs_db": True,
            "is_followup": False,
            "follow_up_type": None,
        }

    conversation_history = _serialize_messages(messages)
    execution_context: ExecutionContext = state.get("execution_context")
    if execution_context:
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

    prompt = f"""You are a context resolver for a banking loan analyst agent.

Analyse the conversation history and current query. Output:
- enriched_query: fully self-contained rewrite (no ambiguous references)
- needs_db: whether a new database call is required
- is_followup: whether this query refers to, filters, drills into, compares, or visualizes previously fetched data
- follow_up_type: classify the type of follow-up (or "none" if not a follow-up)
- reasoning: one line for logs

TOOLS AND REQUIRED PARAMS
Customer Profile        -- required: customer_id
Overdue Loans           -- optional: city, loan_type, min_days_overdue
Repayment Summary       -- required: customer_id | optional: loan_id
Loan Portfolio Stats    -- optional: group_by, city, loan_type
Collection Efficiency   -- optional: city, loan_type, period
Policy Info (RAG)       -- no params required (semantic search on policy documents)

RESOLUTION RULES
- Replace all pronouns/references using history or execution_context:
  "his/her/same customer" -> customer_id | "those loans" -> loan_id
  "that city" -> city | "same period" -> period
- If a required param is missing from query but exists in execution_context, inject it.
- If a reference cannot be resolved, preserve it as-is and set needs_db: true.
- If nothing needs resolving, return the original query unchanged.
- Policy queries (definitions, RBI rules, classifications) never need DB or resolution.
- If the query is a vague follow-up on a prior policy answer ("explain more", "give an example",
  "what about that", "elaborate"), resolve enriched_query to repeat the prior policy topic explicitly.
  Still set is_followup: false, needs_db: false.

NEEDS_DB RULES
- Check execution_context first:
  if requested field is in execution_context -> needs_db: false
- Check last_fetched_fields:
  if requested field was already fetched this session -> needs_db: false
- needs_db: true only if none of the above apply
- Policy queries always set needs_db: false (answered from policy documents, not DB)

IS_FOLLOWUP RULES
- is_followup: true if the query contains an unresolved pronoun or reference
  ("his", "those loans", "that city", "same period") that depends on prior results
- is_followup: true if the query explicitly filters, drills into, compares, or
  visualizes data that was already fetched in a prior turn
- is_followup: false if the query is fully self-contained — all params are
  explicitly stated and no resolution from history is needed
- A shared entity name (city, loan type) alone does NOT make a query a follow-up.
  The test is: could this query be executed in a completely fresh session with
  zero history and still be fully resolved? If yes -> is_followup: false
- Policy queries always set is_followup: false (self-contained by nature)

FRESH QUERY INDICATORS — these always set is_followup: false
- Query invokes a different tool than the last turn AND contains no pronoun or
  implicit reference that depends on prior results
- The user explicitly names all params needed — no resolution required
- A city, loan type, or customer ID that happens to match a prior turn is not
  a dependency unless the query uses a reference word ("that city", "same type")
- Policy definition or RBI rule questions are always fresh queries

FOLLOW_UP_TYPE RULES
- "compare"       : user wants to compare two entities (Mumbai vs Delhi, this month vs last month)
- "drill_down"    : user wants more detail on a subset of previously fetched data,
                    using the SAME tool as the prior turn
- "visualize"     : user wants a chart or graph of fetched data
- "report"        : user wants a structured report of fetched data
- "conversational": user asks a question answerable from history, no new data needed
- "none"          : fresh independent query, not a follow-up at all

COMPARE DETECTION -- also applies to first-turn queries:
- If the query mentions two explicit entities to compare (cities, periods, loan types),
  set follow_up_type: "compare" even if is_followup is false

ROUTING OUTCOME (for your reasoning -- do not output this field)
- is_followup: true  + needs_db: false -> followup node (answer from history/context)
- is_followup: true  + needs_db: true  -> parse node (re-run tool with new params)
- is_followup: false + needs_db: true  -> parse node (fresh query)
- is_followup: false + needs_db: false -> followup node (edge case, treat as conversational)
- policy query                         -> always: is_followup: false + needs_db: false -> parse node -> retrieve_policy

EDGE CASES

Follow-up on fetched data
  history: Customer Profile fetched for customer 1
  query: "what is his name"
  -> enriched_query: "what is the name of customer_id 1"
  -> needs_db: false | is_followup: true | follow_up_type: conversational
  reasoning: pronoun "his" resolved from execution_context, data already in context

Different tool, same customer
  history: Customer Profile fetched for customer 1
  query: "show his repayment history"
  -> enriched_query: "repayment history for customer_id 1"
  -> needs_db: true | is_followup: true | follow_up_type: none
  reasoning: pronoun "his" depends on prior result, different tool requires new DB call

Same tool, different customer
  history: Customer Profile fetched for customer 1
  query: "show profile of customer 2"
  -> enriched_query: "profile of customer_id 2"
  -> needs_db: true | is_followup: false | follow_up_type: none
  reasoning: fully self-contained, no reference to prior result

Different tool, shared entity name — NOT a follow-up
  history: Loan Portfolio Stats fetched -- city: Mumbai vs Delhi
  query: "overdue loans in Mumbai"
  -> enriched_query: "overdue loans in Mumbai"
  -> needs_db: true | is_followup: false | follow_up_type: none
  reasoning: different tool, all params explicit, no pronoun or implicit reference to prior result

Partial filter change
  history: Overdue Loans fetched -- city: Mumbai, loan_type: personal
  query: "now show me home loans"
  -> enriched_query: "overdue home loans in Mumbai"
  -> needs_db: true | is_followup: true | follow_up_type: drill_down
  reasoning: "now" signals continuation, city resolved from prior context, same tool

Unresolvable reference
  history: no customer mentioned
  query: "show his repayment history"
  -> enriched_query: "repayment history for customer_id unknown"
  -> needs_db: true | is_followup: false | follow_up_type: none
  reasoning: pronoun cannot be resolved, treated as fresh broken query

Period change
  history: Collection Efficiency fetched for this month
  query: "how about last month"
  -> enriched_query: "collection efficiency for last month"
  -> needs_db: true | is_followup: true | follow_up_type: compare
  reasoning: "how about" signals continuation, same tool, period change implies comparison

Follow-up on aggregate data
  history: Loan Portfolio Stats fetched (default rate by city)
  query: "which city had the highest default rate"
  -> enriched_query: unchanged
  -> needs_db: false | is_followup: true | follow_up_type: conversational
  reasoning: answer derivable from already fetched aggregate data

Drill-down request
  history: Overdue Loans fetched -- all cities
  query: "break this down by loan type"
  -> enriched_query: "overdue loans grouped by loan type"
  -> needs_db: true | is_followup: true | follow_up_type: drill_down
  reasoning: "this" refers to prior result, same tool, new grouping dimension

Compare request (follow-up)
  history: Collection Efficiency fetched for Mumbai
  query: "how does Delhi compare"
  -> enriched_query: "collection efficiency for Delhi compared to Mumbai"
  -> needs_db: true | is_followup: true | follow_up_type: compare
  reasoning: implicit reference to prior Mumbai result, same tool, new city for comparison

Compare request (first turn, both explicit)
  history: none
  query: "loan portfolio stats Mumbai vs Delhi"
  -> enriched_query: unchanged
  -> needs_db: true | is_followup: false | follow_up_type: compare
  reasoning: fully self-contained, two explicit entities named, no prior context needed

Visualization request
  history: Loan Portfolio Stats fetched
  query: "show me a chart of this"
  -> enriched_query: "visualize loan portfolio stats as chart"
  -> needs_db: false | is_followup: true | follow_up_type: visualize
  reasoning: "this" refers to prior result, no new data needed

Fresh unrelated query
  history: Customer Profile fetched for customer 1
  query: "show overdue loans in Pune"
  -> enriched_query: unchanged
  -> needs_db: true | is_followup: false | follow_up_type: none
  reasoning: different tool, all params explicit, no reference to prior result

Policy definition query (fresh)
  history: none
  query: "what is SMA-2?"
  -> enriched_query: unchanged
  -> needs_db: false | is_followup: false | follow_up_type: none
  reasoning: self-contained policy question, no DB or prior context needed

Vague follow-up on prior policy answer
  history: Policy Info fetched -- topic: SMA-2 classification
  query: "can you explain that in more detail?"
  -> enriched_query: "explain SMA-2 classification in more detail"
  -> needs_db: false | is_followup: false | follow_up_type: none
  reasoning: vague reference resolved to prior policy topic, still routed as fresh policy query

Policy query after DB result
  history: Customer Profile fetched for customer 1, risk level HIGH
  query: "what does high risk mean as per RBI?"
  -> enriched_query: unchanged
  -> needs_db: false | is_followup: false | follow_up_type: none
  reasoning: policy question is self-contained, does not depend on prior DB result

Conversation history:
{conversation_history}

Execution context:
{json.dumps(execution_context_dict, indent=2, default=str)}

Current query: {state["user_query"]}

OUTPUT -- JSON only, no explanation
{{
  "enriched_query": "<fully resolved, self-contained query>",
  "needs_db": true or false,
  "is_followup": true or false,
  "follow_up_type": "compare" | "drill_down" | "visualize" | "report" | "conversational" | "none",
  "reasoning": "<one line>"
}}
"""

    try:
        print("DEBUG context_node: calling _call_llm")

        output = _call_llm(
            user_prompt=prompt,
            model_class=ContextOutput,
            model_name=runtime.context.model_name,
            client=runtime.context.client,
            max_tokens=300,
        )

        print("DEBUG context_node: returning back from _call_llm):")
        print(f"DEBUG context_node: conversation_history: {conversation_history}")
        print(f"DEBUG context_node: execution_context: {execution_context_dict}")
        print(f"DEBUG context_node: enriched_query: {output.enriched_query}")
        print(f"DEBUG context_node: needs_db: {output.needs_db}")
        print(f"DEBUG context_node: is_followup: {output.is_followup}")
        print(f"DEBUG context_node: follow_up_type: {output.follow_up_type}")
        print(f"DEBUG context_node: reasoning: {output.reasoning}")
        print("==========================================================")

        # map string to FollowUpType enum, None if "none" or unrecognised
        follow_up_type_map = {
            "compare": FollowUpType.COMPARE,
            "drill_down": FollowUpType.DRILL_DOWN,
            "visualize": FollowUpType.VISUALIZE,
            "report": FollowUpType.REPORT,
            "conversational": FollowUpType.CONVERSATIONAL,
        }
        follow_up_type = follow_up_type_map.get(output.follow_up_type)

        return {
            "enriched_query": output.enriched_query,
            "needs_db": output.needs_db,
            "is_followup": output.is_followup,
            "follow_up_type": follow_up_type,
        }

    except Exception as e:
        print("DEBUG context_node: in context_node exception occurred:")
        print(f"DEBUG context_node: error: {e}")
        print(f"DEBUG context_node: returning default values")
        print("==========================================================")

        return {
            "enriched_query": state["user_query"],
            "needs_db": True,
            "is_followup": False,
            "follow_up_type": None,
        }
