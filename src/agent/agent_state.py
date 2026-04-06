from typing import Optional, Literal, Any, Union
from typing import TypedDict
from datetime import date
from decimal import Decimal
from pydantic import BaseModel

class CustomerProfileParams(BaseModel):
    customer_id: int | None

class OverdueLoansParams(BaseModel):
    city: Optional[Literal["Mumbai", "Delhi", "Pune", "Bangalore"]] = None
    loan_type: Optional[Literal["Personal", "Home", "Business", "Vehicle", "Education", "Gold"]] = None
    min_days_overdue: Optional[int] = None

class RepaymentSummaryParams(BaseModel):
    customer_id: int
    loan_id: Optional[int] = None

class LoanPortfolioStatsParams(BaseModel):
    group_by: Optional[Literal["loan_type", "city", "status"]] = None
    city: Optional[Literal["Mumbai", "Delhi", "Pune", "Bangalore"]] = None
    loan_type: Optional[Literal["Personal", "Home", "Business", "Vehicle", "Education", "Gold"]] = None

class CollectionEfficiencyParams(BaseModel):
    city: Optional[Literal["Mumbai", "Delhi", "Pune", "Bangalore"]] = None
    loan_type: Optional[Literal["Personal", "Home", "Business", "Vehicle", "Education", "Gold"]] = None
    period: Optional[Literal["this_month", "last_month", "this_quarter", "this_year"]] = None

ToolParams = Optional[Union[
    CustomerProfileParams,
    OverdueLoansParams,
    RepaymentSummaryParams,
    LoanPortfolioStatsParams,
    CollectionEfficiencyParams,
]]

Intent = Literal[
    "get_customer_profile",
    "get_overdue_loans",
    "get_repayment_summary",
    "get_loan_portfolio_stats",
    "get_collection_efficiency",
    "get_help",
    "unknown"
]


# AGENT STATE
class AgentState(TypedDict):

    user_query: str
    intent: Intent
    tool_params: ToolParams

    tool_result: Optional[Any]
    final_response: Optional[str]
    excel_path: Optional[str]
    error: Optional[str]


def create_initial_state(user_query: str) -> AgentState:
    """
    Returns a clean initial AgentState for a new user query.
    Usage:
        state = create_initial_state("Show me overdue loans in Mumbai")
    """
    return {
        "user_query": user_query,
        "intent": "unknown",   # classifier will update this
        "tool_params": None,        # classifier will update this
        "tool_result": None,        # tool node will update this
        "excel_path": None,        # tool node sets if result is large
        "final_response": None,        # summarizer will update this
        "error": None,        # any node may set this
    }