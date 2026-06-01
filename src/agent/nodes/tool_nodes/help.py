# from agent.agent_state import (
#     AgentState,
#     Intent,
#     City,
#     LoanType,
#     PortfolioGroupBy,
#     Period,
# )

# def get_help_node(state: AgentState) -> dict:
#     """
#     Returns a structured guide of all supported agent capabilities,
#     aligned with current intents + tool parameter schemas.
#     """

#     capabilities = [
#         {
#             "intent": Intent.GET_CUSTOMER_PROFILE.value,
#             "tool": "Customer Profile",
#             "description": """
# Retrieve the complete profile of a customer including:
# - personal details
# - branch + city
# - credit score
# - all active/past loans
# - repayment behaviour
# - portfolio risk level
# - delinquency insights
#             """,
#             "examples": [
#                 "Show me the profile of customer 42",
#                 "Get customer details for ID 105",
#                 "What is the risk level of customer 15?",
#                 "Show all loans for customer 88",
#             ],
#             "required": ["customer_id"],
#             "optional": [],
#         },
#         {
#             "intent": Intent.GET_OVERDUE_LOANS.value,
#             "tool": "Overdue Loans",
#             "description": """
# Retrieve all overdue/defaulted loans with optional filters.
# Useful for collections and risk monitoring.

# Supports:
# - city filtering
# - loan type filtering
# - minimum DPD filtering
#             """,
#             "examples": [
#                 "Show me all overdue loans",
#                 "Show overdue home loans in Mumbai",
#                 "Which loans are overdue more than 60 days?",
#                 "Show personal loans overdue in Delhi",
#                 "Show all loans overdue above 90 days",
#             ],
#             "required": [],
#             "optional": [
#                 "city",
#                 "loan_type",
#                 "min_days_overdue",
#             ],
#         },
#         {
#             "intent": Intent.GET_REPAYMENT_SUMMARY.value,
#             "tool": "Repayment Summary",
#             "description": """
# Get repayment history and EMI behaviour for a customer or specific loan.

# Includes:
# - paid EMIs
# - missed EMIs
# - late payments
# - partial payments
# - DPD trends
#             """,
#             "examples": [
#                 "Show repayment summary for customer 25",
#                 "Get repayment details for loan 9001",
#                 "Show EMI history for customer 15",
#                 "How many EMIs has customer 77 missed?",
#             ],
#             "required": ["customer_id"],
#             "optional": ["loan_id"],
#         },
#         {
#             "intent": Intent.GET_LOAN_PORTFOLIO_STATS.value,
#             "tool": "Loan Portfolio Statistics",
#             "description": """
# Retrieve aggregate portfolio analytics across all loans.

# Includes:
# - total disbursed amount
# - outstanding exposure
# - active/defaulted loan counts
# - default rates
# - grouped analytics

# Can group by:
# - loan type
# - city
# - status
#             """,
#             "examples": [
#                 "Give me portfolio statistics",
#                 "Show portfolio stats by city",
#                 "What is the default rate by loan type?",
#                 "Show portfolio stats for Mumbai",
#                 "Group portfolio by status",
#             ],
#             "required": [],
#             "optional": [
#                 "group_by",
#                 "city",
#                 "loan_type",
#             ],
#         },
#         {
#             "intent": Intent.GET_COLLECTION_EFFICIENCY.value,
#             "tool": "Collection Efficiency",
#             "description": """
# Analyze collections performance and recovery efficiency.

# Supports:
# - city-wise efficiency
# - loan-type-wise efficiency
# - period comparisons

# Useful for collections MIS reporting.
#             """,
#             "examples": [
#                 "Show collection efficiency this month",
#                 "Collection efficiency for Mumbai",
#                 "Show business loan collection efficiency",
#                 "Compare collection efficiency this quarter",
#             ],
#             "required": [],
#             "optional": [
#                 "city",
#                 "loan_type",
#                 "period",
#             ],
#         },
#     ]

#     supported_filters = {
#         "Cities": [city.value for city in City],
#         "Loan Types": [loan.value for loan in LoanType],
#         "Portfolio Group By": [grp.value for grp in PortfolioGroupBy],
#         "Periods": [period.value for period in Period],
#     }

#     tips = [
#         "You can combine multiple filters in one query.",
#         "Example: 'Show overdue home loans in Mumbai older than 30 days'",
#         "Customer queries work best when customer_id is explicitly mentioned.",
#         "90+ DPD loans are treated as CRITICAL risk.",
#         "Portfolio analytics support grouping and filtering simultaneously.",
#         "Use 'help' anytime to see this guide again.",
#     ]

#     lines = []

#     lines.append("# Loan Intelligence Assistant\n")

#     lines.append(
#         "I can help you analyze customer loans, repayments, "
#         "portfolio risk, collections, and delinquency data.\n"
#     )

#     # CAPABILITIES
#     lines.append("## Supported Capabilities\n")

#     for idx, tool in enumerate(capabilities, start=1):

#         lines.append(f"### {idx}. {tool['tool']}")
#         lines.append(f"**Intent:** `{tool['intent']}`\n")

#         lines.append(tool["description"].strip() + "\n")

#         lines.append("#### Example Queries")
#         for example in tool["examples"]:
#             lines.append(f"- {example}")

#         if tool["required"]:
#             lines.append(
#                 f"\n**Required Parameters:** " f"{', '.join(tool['required'])}"
#             )

#         if tool["optional"]:
#             lines.append(
#                 f"\n**Optional Parameters:** " f"{', '.join(tool['optional'])}"
#             )

#         lines.append("\n---\n")

#     # ENUM / FILTER SUPPORT
#     lines.append("## Supported Filter Values\n")

#     for key, values in supported_filters.items():
#         lines.append(f"### {key}")
#         for value in values:
#             lines.append(f"- {value}")
#         lines.append("")

#     # TIPS
#     lines.append("## Tips\n")

#     for tip in tips:
#         lines.append(f"- {tip}")

#     # CONTEXT AWARE ADDITIONAL HELP
#     execution_context = state.get("execution_context", {})

#     current_customer = execution_context.get("current_customer_id")

#     if current_customer:
#         lines.append("\n## Current Session Context\n")
#         lines.append(f"- Last accessed customer ID: {current_customer}")

#     return {
#         "final_response": "\n".join(lines),
#         "tool_result": {
#             "capabilities_count": len(capabilities),
#         },
#         "retrieved_data": state.get("retrieved_data", {}),
#         "execution_context": {
#             **state.get("execution_context", {}),
#             "last_tool": "get_help",
#         },
#         "export_path": None,
#         "error": None,
#     }

from agent.agent_state import (
    AgentState,
    Intent,
    City,
    LoanType,
    PortfolioGroupBy,
    Period,
)


def get_help_node(state: AgentState) -> dict:
    """
    Returns a structured guide of all supported agent capabilities,
    aligned with current intents + tool parameter schemas.

    Ownership rules:
    - This node writes ONLY to: final_response, error
    - execution_context is NOT touched here - owned by summarize_node / merge_node
    """

    capabilities = [
        {
            "intent": Intent.GET_CUSTOMER_PROFILE.value,
            "tool": "Customer Profile",
            "description": """
Retrieve the complete profile of a customer including:
- personal details
- branch + city
- credit score
- all active/past loans
- repayment behaviour
- portfolio risk level
- delinquency insights
            """,
            "examples": [
                "Show me the profile of customer 42",
                "Get customer details for ID 105",
                "What is the risk level of customer 15?",
                "Show all loans for customer 88",
            ],
            "required": ["customer_id"],
            "optional": [],
        },
        {
            "intent": Intent.GET_OVERDUE_LOANS.value,
            "tool": "Overdue Loans",
            "description": """
Retrieve all overdue/defaulted loans with optional filters.
Useful for collections and risk monitoring.

Supports:
- city filtering
- loan type filtering
- minimum DPD filtering
            """,
            "examples": [
                "Show me all overdue loans",
                "Show overdue home loans in Mumbai",
                "Which loans are overdue more than 60 days?",
                "Show personal loans overdue in Delhi",
                "Show all loans overdue above 90 days",
            ],
            "required": [],
            "optional": ["city", "loan_type", "min_days_overdue"],
        },
        {
            "intent": Intent.GET_REPAYMENT_SUMMARY.value,
            "tool": "Repayment Summary",
            "description": """
Get repayment history and EMI behaviour for a customer or specific loan.

Includes:
- paid EMIs
- missed EMIs
- late payments
- partial payments
- DPD trends
            """,
            "examples": [
                "Show repayment summary for customer 25",
                "Get repayment details for loan 9001",
                "Show EMI history for customer 15",
                "How many EMIs has customer 77 missed?",
            ],
            "required": ["customer_id"],
            "optional": ["loan_id"],
        },
        {
            "intent": Intent.GET_LOAN_PORTFOLIO_STATS.value,
            "tool": "Loan Portfolio Statistics",
            "description": """
Retrieve aggregate portfolio analytics across all loans.

Includes:
- total disbursed amount
- outstanding exposure
- active/defaulted loan counts
- default rates
- grouped analytics

Can group by:
- loan type
- city
- status
            """,
            "examples": [
                "Give me portfolio statistics",
                "Show portfolio stats by city",
                "What is the default rate by loan type?",
                "Show portfolio stats for Mumbai",
                "Group portfolio by status",
            ],
            "required": [],
            "optional": ["group_by", "city", "loan_type"],
        },
        {
            "intent": Intent.GET_COLLECTION_EFFICIENCY.value,
            "tool": "Collection Efficiency",
            "description": """
Analyze collections performance and recovery efficiency.

Supports:
- city-wise efficiency
- loan-type-wise efficiency
- period comparisons

Useful for collections MIS reporting.
            """,
            "examples": [
                "Show collection efficiency this month",
                "Collection efficiency for Mumbai",
                "Show business loan collection efficiency",
                "Compare collection efficiency this quarter",
            ],
            "required": [],
            "optional": ["city", "loan_type", "period"],
        },
    ]

    supported_filters = {
        "Cities": [city.value for city in City],
        "Loan Types": [loan.value for loan in LoanType],
        "Portfolio Group By": [grp.value for grp in PortfolioGroupBy],
        "Periods": [period.value for period in Period],
    }

    tips = [
        "You can combine multiple filters in one query.",
        "Example: 'Show overdue home loans in Mumbai older than 30 days'",
        "Customer queries work best when customer_id is explicitly mentioned.",
        "90+ DPD loans are treated as CRITICAL risk.",
        "Portfolio analytics support grouping and filtering simultaneously.",
        "Use 'help' anytime to see this guide again.",
    ]

    lines = []
    lines.append("# Loan Intelligence Assistant\n")
    lines.append(
        "I can help you analyze customer loans, repayments, "
        "portfolio risk, collections, and delinquency data.\n"
    )

    lines.append("## Supported Capabilities\n")
    for idx, tool in enumerate(capabilities, start=1):
        lines.append(f"### {idx}. {tool['tool']}")
        lines.append(f"**Intent:** `{tool['intent']}`\n")
        lines.append(tool["description"].strip() + "\n")
        lines.append("#### Example Queries")
        for example in tool["examples"]:
            lines.append(f"- {example}")
        if tool["required"]:
            lines.append(f"\n**Required Parameters:** {', '.join(tool['required'])}")
        if tool["optional"]:
            lines.append(f"\n**Optional Parameters:** {', '.join(tool['optional'])}")
        lines.append("\n---\n")

    lines.append("## Supported Filter Values\n")
    for key, values in supported_filters.items():
        lines.append(f"### {key}")
        for value in values:
            lines.append(f"- {value}")
        lines.append("")

    lines.append("## Tips\n")
    for tip in tips:
        lines.append(f"- {tip}")

    # session context hint - read only, no writes
    execution_context = state.get("execution_context")
    if execution_context:
        current_customer = execution_context.current_customer_id
        if current_customer:
            lines.append("\n## Current Session Context\n")
            lines.append(f"- Last accessed customer ID: {current_customer}")

    return {
        "final_response": "\n".join(lines),
        "error": None,
    }
