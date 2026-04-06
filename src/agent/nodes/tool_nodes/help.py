from agent.agent_state import (
    AgentState,
)


# Tool node that provides help regarding agent use:
def get_help_node(state: AgentState) -> dict:
    """
    Returns a structured guide of all agent capabilities with example queries for each tool.
    Triggered when user asks "help", "what can you do" etc.
    """
 
    capabilities = [
        {
            "tool": "Customer Profile",
            "description": 
    """
    Full profile of a specific customer:
    - personal details,
    - all their loans,
    - repayment behaviour
    - overall risk level
    """,
            "examples": [
                "Show me the profile of customer 42",
                "What is the risk level of customer ID 15?",
            ],
            "required": ["customer ID"],
            "optional": [],
        },
        {
            "tool": "Overdue Loans",
            "description": 
    """
    All loans that are currently overdue, defaulted, or NPA.
    Results are bucketed by severity — 1-30, 31-60, 61-90, 90+ days past due.
    """,
            "examples": [
                "Show me all overdue loans",
                "Show me overdue home loans in Mumbai",
                "Which loans are more than 60 days past due in Delhi?",
                "Show me all NPA loans for personal loans",
            ],
            "required": [],
            "optional": ["city", "loan type", "minimum days overdue"],
        },
        {
            "tool": "Repayment Summary",
            "description": 
    """
    Full repayment history for a customer across all their loans or a specific loan.
    Includes:
    - on-time rate,
    - missed count,
    - payment trend — improving, stable, or deteriorating.
    """,
            "examples": [
                "Show repayment history for customer 42",
                "How has customer 7 been paying their home loan?",
                "Summarise the payment behaviour of Priya Sharma",
            ],
            "required": ["customer ID"],
            "optional": ["specific loan ID"],
        },
        {
            "tool": "Loan Portfolio Stats",
            "description": 
    """
    Aggregate statistics across all loans:
    - total disbursed
    - outstanding
    - default rates
    Can be grouped by:
    - loan type
    - city
    - status
    """,
            "examples": [
                "Give me an overview of the entire loan portfolio",
                "What is the default rate by loan type?",
                "Show me portfolio stats for Mumbai",
                "Which city has the highest default rate?",
            ],
            "required": [],
            "optional": ["group by (loan type / city / status)", "city", "loan type"],
        },
        {
            "tool":        "Collection Efficiency",
            "description":
    """
    How effectively overdue loans are being recovered.
    Shows recovery rate, amount collected vs due, and month-over-month trend
    """,
            "examples": [
                "What is our collection efficiency this month?",
                "How well are we recovering personal loans in Mumbai?",
                "Show collection efficiency for this quarter",
                "Is our recovery rate improving or declining?",
            ],
            "required":  [],
            "optional":  ["city", "loan type", "period (this month / last month / this quarter / this year)"],
        },
    ]
 
    # Supported filter values:
    filters = {
        "cities": ["Mumbai", "Delhi", "Pune", "Bangalore"],
        "loan_types": ["Personal", "Home", "Business", "Vehicle", "Education", "Gold"],
        "periods": ["this_month", "last_month", "this_quarter", "this_year"],
    }
 
    # Usage tips:
    tips = [
        "You can combine filters — e.g. 'overdue home loans in Mumbai older than 30 days'",
        "For customer queries always provide a customer ID for best results",
        "Risk levels follow RBI DPD classification — CRITICAL means 90+ days overdue",
        "Collection efficiency shows recovery trends — useful for management reviews",
        "Type 'help' anytime to see this guide again"
    ]
    print(f"help executed. intent:{state["intent"]}")

    guide_lines = ["I can help you analyze loan data. Here's what you can ask:\n"]

    for i, tool in enumerate(capabilities, 1):
        guide_lines.append(f"{i}. {tool['tool']}")
        guide_lines.append(f"   {tool['description'].strip()}")
        guide_lines.append("   Example queries:")
        for ex in tool["examples"]:
            guide_lines.append(f"     - {ex}")
        if tool["required"]:
            guide_lines.append(f"   Required: {', '.join(tool['required'])}")
        if tool["optional"]:
            guide_lines.append(f"   Optional: {', '.join(tool['optional'])}")
        guide_lines.append("")

    guide_lines.append("Tips:")
    for tip in tips:
        guide_lines.append(f"- {tip}")

    return {
        "final_response": "\n".join(guide_lines),
        "tool_result": None,
        "excel_path": None,
        "error": None,
    }
    # return {
    #     "tool_result": {
    #         "capabilities": capabilities,
    #         "filters":      filters,
    #         "tips":         tips,
    #         "total_tools":  len(capabilities),
    #     },
    #     "excel_path": None,
    #     "error": None,
    # }