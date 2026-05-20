import json
from openai import OpenAI
from agent.agent_state import (
    AgentState,
)

from agent.utils import _call_llm

SYSTEM_PROMPT = """
You are a banking analyst assistant. Convert structured loan data into clear, actionable summaries.

Rules:
- Do NOT include any reasoning or <think> tags.
- Start with the most important insight
- Use Indian currency format (₹, lakh, crore)
- Highlight critical issues
- Be professional and concise
- Do not invent data
- Recommend actions for risks or trends
- Keep responses under 150 words unless necessary
"""

# Each intent gets a tailored instruction so the LLM knows how to frame the response for that specific tool.
INTENT_PROMPTS = {
    "get_customer_profile": """
Summarise this customer profile for a loan officer preparing for a review.
Structure your response as:
1. Customer basics (name, employment, income, credit score)
2. Loan summary (how many loans, total outstanding)
3. Risk assessment (risk level and why)
4. Recommended action based on risk level
""",
    "get_overdue_loans": """
Summarise these overdue loans for a loan officer.
Structure your response as:
1. Total count and overall outstanding amount
2. Severity breakdown using DPD buckets
3. Most critical cases by name with days overdue
4. Recommended priority actions
Frame this as an action list — loan officers need to know what to do next.
""",
    "get_repayment_summary": """
Summarise this customer's repayment behaviour for a loan officer.
Structure your response as:
1. Payment Behaviour
   - Distribution of repayment statuses (GOOD, LATE, BAD, PARTIAL_RECOVERY, UPCOMING)
   - Overall discipline based on mix of statuses
2. Recent Trend
   - Use payment_trend (IMPROVING / STABLE / DETERIORATING / INSUFFICIENT_DATA)
3. Risk Signals
   - Presence of BAD statuses (MISSED, OVERDUE, DEFAULTED)
   - Any pattern of worsening behaviour or repeated bad payments
4. Recommended Action
   - Brief action based on trend and risk (monitor / follow-up / escalate / review)
""",
    "get_loan_portfolio_stats": """
Summarise these portfolio statistics for a branch manager.
Structure your response as:
1. Portfolio health overview (total loans, outstanding, default rate)
2. Key findings from the breakdown — which group is performing worst?
3. Any groups flagged as high default rate
4. Management recommendation
""",
    "get_collection_efficiency": """
Summarise collection efficiency for a branch manager.
Structure your response as:
1. Current recovery rate and what it means
2. Amount collected vs uncollected in rupees
3. Trend — improving, stable, or declining
4. Management action if declining
""",
    "get_help": """
Present agent capabilities as a simple guide:
- Start with a brief intro
- List each capability with one example query
- End with 2–3 usage tips

Keep it clear and beginner-friendly.
""",
    "unknown": """
The query could not be matched to any known capability.
Politely explain this and suggest the user ask for help
to see what queries are supported.
""",
}


# Helper functions
def _format_currency(amount: float) -> str:
    """
    Converts a float to Indian currency string.
    e.g. 4500000 - ₹45 lakh
         12500000 - ₹1.25 crore
         450000   - ₹4.5 lakh
    """
    if amount >= 10_000_000:
        return f"₹{amount / 10_000_000:.2f} crore"
    elif amount >= 100_000:
        return f"₹{amount / 100_000:.1f} lakh"
    else:
        return f"₹{amount:,.0f}"


def _top_n(rows: list, n: int = 3) -> list:
    """Return first N rows — used for worst-case illustration only."""
    return rows[:n]


def _prepare_result_for_prompt(tool_result: dict, intent: str) -> str:
    """
    Converts tool_result dict to a clean string for the LLM prompt.

    Strategy — never send raw row lists to the LLM:
      - Aggregate stats (counts, totals, rates)
      - Raw rows (individual loans/customers) -> replaced with top 3 worst cases for illustration only
      - Full dataset always goes to CSV — not to the LLM

    This ensures the LLM summary is based on complete aggregate data not a misleading truncated slice of rows.
    (Handling lower context window/token count of smaller models)
    """
    if tool_result is None:
        return "No data available."

    summary = {}

    if intent == "get_overdue_loans":
        loans = tool_result.get("loans", [])
        summary = {
            "total_overdue": tool_result.get("total_overdue"),
            "dpd_buckets": tool_result.get("dpd_buckets"),
            # Top 3 most critical loans for illustration
            "top_3_critical": _top_n(loans, 3),
            "note": (
                (
                    f"Full list of {len(loans)} loans exported to CSV. "
                    "Summary above covers all loans."
                )
                if len(loans) > 3
                else None
            ),
        }

    elif intent == "get_repayment_summary":
        repayments = tool_result.get("repayments", [])
        summary = {
            "customer_name": tool_result.get("customer_name"),
            # Summary stats cover all repayments — no need for raw rows
            "summary": tool_result.get("summary"),
            "note": (
                (
                    f"Full repayment history of {len(repayments)} records "
                    "exported to CSV."
                )
                if len(repayments) > 10
                else None
            ),
        }

    else:
        # For all other intents — no large row lists expected
        # Send tool_result as-is
        summary = tool_result

    # Remove None values to keep prompt clean
    summary = {k: v for k, v in summary.items() if v is not None}
    return json.dumps(summary, indent=2, default=str)


# SUMMARIZER NODE
def summarize_node(state: AgentState, client: OpenAI, model_name: str) -> dict:
    """
    converts tool_result to natural language.

    Uses two-part prompt:
      System: professional guidelines
      User: intent-specific framing + structured tool result data
    """
    intent = state["intent"]
    tool_result = state["tool_result"]
    user_query = state["user_query"]

    # Get intent-specific instruction
    intent_instruction = INTENT_PROMPTS.get(intent, INTENT_PROMPTS["unknown"])

    # Prepare tool result for prompt
    result_str = _prepare_result_for_prompt(tool_result, intent)

    # Build user prompt
    user_prompt = f"""Original query: "{user_query}"
 
        {intent_instruction}
        
        Data to summarise:
        {result_str}
        
        Write your summary now:
        """

    try:
        # messages=[
        #         {"role": "system", "content": SYSTEM_PROMPT},
        #         {"role": "user",   "content": user_prompt},
        #     ]
        # print(f"message: {messages}")
        summarizer_response = _call_llm(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=300,
            client=client,
            model_name=model_name,
        )

        # Append Excel file path if tool node generated one
        excel_path = state.get("excel_path")
        if excel_path:
            summarizer_response += f"\n\n Full data exported to Excel: {excel_path}"

        return {"final_response": summarizer_response, "error": None}

    except Exception as e:
        print(e)
        return {"final_response": None, "error": f"Summarization failed: {str(e)}"}
