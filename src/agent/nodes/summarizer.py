import json
from openai import OpenAI
from langgraph.runtime import Runtime
from agent.agent_state import AgentState
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
}


# -------------------------
# HELPERS
# -------------------------


def _safe_intent(intent):
    if hasattr(intent, "value"):
        return intent.value
    return intent or "unknown"


def _extract_data(intent: str, tool_result: dict) -> str:
    """
    Normalize different tool outputs into LLM-friendly JSON.
    """

    if not tool_result:
        return "No data available."

    # OVERDUE LOANS (your new structure)
    if intent == "get_overdue_loans":
        return json.dumps(
            {
                "total_overdue": tool_result.get("overall", {}).get("total_overdue"),
                "dpd_buckets": tool_result.get("dpd_buckets"),
                "top_critical": tool_result.get("top_critical", []),
                "export_path": tool_result.get("export_path"),
            },
            indent=2,
            default=str,
        )

    # REPAYMENT SUMMARY
    if intent == "get_repayment_summary":
        return json.dumps(
            {
                "customer_name": tool_result.get("customer_name"),
                "summary": tool_result.get("summary"),
                "total_records": tool_result.get("total_repayment_records"),
            },
            indent=2,
            default=str,
        )

    # CUSTOMER PROFILE / OTHERS
    return json.dumps(tool_result, indent=2, default=str)


# -------------------------
# MAIN NODE
# -------------------------


def summarize_node(state: AgentState, runtime: Runtime[AppContext]) -> dict:

    # CONTEXT
    client = runtime.context.client
    model_name = runtime.context.model_name

    # STATE
    intent = _safe_intent(state.get("intent"))
    tool_result = state.get("tool_result")
    user_query = state.get("user_query", "")

    intent_instruction = INTENT_PROMPTS.get(intent, INTENT_PROMPTS["unknown"])

    structured_data = _extract_data(intent, tool_result)

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
        response = _call_llm(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            client=client,
            model_name=model_name,
            max_tokens=350,
        )

        export_path = state.get("execution_context", {}).get("export_path")

        if export_path:
            response += f"\n\nExport file available at: {export_path}"

        return {
            "final_response": response,
            "error": None,
        }

    except Exception as e:
        return {
            "final_response": None,
            "error": f"Summarization failed: {str(e)}",
        }
