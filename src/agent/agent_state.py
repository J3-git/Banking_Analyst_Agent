# from typing import Optional, Literal, Any, Union
# from typing import TypedDict
# from datetime import date
# from decimal import Decimal
# from pydantic import BaseModel

# class CustomerProfileParams(BaseModel):
#     customer_id: int | None

# class OverdueLoansParams(BaseModel):
#     city: Optional[Literal["Mumbai", "Delhi", "Pune", "Bangalore"]] = None
#     loan_type: Optional[Literal["Personal", "Home", "Business", "Vehicle", "Education", "Gold"]] = None
#     min_days_overdue: Optional[int] = None

# class RepaymentSummaryParams(BaseModel):
#     customer_id: int
#     loan_id: Optional[int] = None

# class LoanPortfolioStatsParams(BaseModel):
#     group_by: Optional[Literal["loan_type", "city", "status"]] = None
#     city: Optional[Literal["Mumbai", "Delhi", "Pune", "Bangalore"]] = None
#     loan_type: Optional[Literal["Personal", "Home", "Business", "Vehicle", "Education", "Gold"]] = None

# class CollectionEfficiencyParams(BaseModel):
#     city: Optional[Literal["Mumbai", "Delhi", "Pune", "Bangalore"]] = None
#     loan_type: Optional[Literal["Personal", "Home", "Business", "Vehicle", "Education", "Gold"]] = None
#     period: Optional[Literal["this_month", "last_month", "this_quarter", "this_year"]] = None

# ToolParams = Optional[Union[
#     CustomerProfileParams,
#     OverdueLoansParams,
#     RepaymentSummaryParams,
#     LoanPortfolioStatsParams,
#     CollectionEfficiencyParams,
# ]]

# Intent = Literal[
#     "get_customer_profile",
#     "get_overdue_loans",
#     "get_repayment_summary",
#     "get_loan_portfolio_stats",
#     "get_collection_efficiency",
#     "get_help",
#     "unknown"
# ]


# # AGENT STATE
# class AgentState(TypedDict):

#     user_query: str
#     intent: Intent
#     tool_params: ToolParams

#     tool_result: Optional[Any]
#     final_response: Optional[str]
#     export_path: Optional[str]
#     error: Optional[str]


# def create_initial_state(user_query: str) -> AgentState:
#     """
#     Returns a clean initial AgentState for a new user query.
#     Usage:
#         state = create_initial_state("Show me overdue loans in Mumbai")
#     """
#     return {
#         "user_query": user_query,
#         "intent": "unknown",   # classifier will update this
#         "tool_params": None,        # classifier will update this
#         "tool_result": None,        # tool node will update this
#         "export_path": None,        # tool node sets if result is large
#         "final_response": None,        # summarizer will update this
#         "error": None,        # any node may set this
#     }


from enum import Enum
from typing import TypedDict, Optional, Any, Union

from pydantic import BaseModel
from langchain_core.messages import BaseMessage

from typing import Annotated
from langgraph.graph.message import add_messages

# ENUMS


class Intent(str, Enum):
    GET_CUSTOMER_PROFILE = "get_customer_profile"
    GET_OVERDUE_LOANS = "get_overdue_loans"
    GET_REPAYMENT_SUMMARY = "get_repayment_summary"
    GET_LOAN_PORTFOLIO_STATS = "get_loan_portfolio_stats"
    GET_COLLECTION_EFFICIENCY = "get_collection_efficiency"
    GET_HELP = "get_help"
    UNKNOWN = "unknown"


class City(str, Enum):
    MUMBAI = "Mumbai"
    DELHI = "Delhi"
    PUNE = "Pune"
    BANGALORE = "Bangalore"


class LoanType(str, Enum):
    PERSONAL = "Personal"
    HOME = "Home"
    BUSINESS = "Business"
    VEHICLE = "Vehicle"
    EDUCATION = "Education"
    GOLD = "Gold"


class PortfolioGroupBy(str, Enum):
    LOAN_TYPE = "loan_type"
    CITY = "city"
    STATUS = "status"


class Period(str, Enum):
    THIS_MONTH = "this_month"
    LAST_MONTH = "last_month"
    THIS_QUARTER = "this_quarter"
    THIS_YEAR = "this_year"


# TOOL PARAM SCHEMAS


class CustomerProfileParams(BaseModel):
    customer_id: int


class OverdueLoansParams(BaseModel):
    city: Optional[City] = None
    loan_type: Optional[LoanType] = None
    min_days_overdue: Optional[int] = None


class RepaymentSummaryParams(BaseModel):
    customer_id: int
    loan_id: Optional[int] = None


class LoanPortfolioStatsParams(BaseModel):
    group_by: Optional[PortfolioGroupBy] = None
    city: Optional[City] = None
    loan_type: Optional[LoanType] = None


class CollectionEfficiencyParams(BaseModel):
    city: Optional[City] = None
    loan_type: Optional[LoanType] = None
    period: Optional[Period] = None


# TOOL PARAM UNION

ToolParams = Union[
    CustomerProfileParams,
    OverdueLoansParams,
    RepaymentSummaryParams,
    LoanPortfolioStatsParams,
    CollectionEfficiencyParams,
]

# AGENT STATE


class AgentState(TypedDict):

    # CURRENT USER INPUT
    user_query: str

    # CONVERSATION MEMORY
    messages: Annotated[list[BaseMessage], add_messages]
    conversation_summary: str

    # INTENT + PARAM EXTRACTION
    intent: Optional[Intent]
    tool_params: Optional[ToolParams]

    # SHARED WORKING MEMORY
    execution_context: dict[str, Any]

    # STORED TOOL OUTPUTS
    retrieved_data: dict[str, Any]

    # CURRENT EXECUTION RESULT
    tool_result: Optional[Any]

    # FINAL RESPONSE
    final_response: Optional[str]
    export_path: Optional[str]

    # ERROR HANDLING
    error: Optional[str]


# INITIAL STATE FACTORY


# def create_initial_state(user_query: str) -> AgentState:
#     """
#     Create clean initial graph state for each invocation.
#     """

#     return {
#         # USER INPUT
#         "user_query": user_query,
#         # MEMORY
#         "messages": [],
#         "conversation_summary": "",
#         # INTENT EXTRACTION
#         "intent": None,
#         "tool_params": None,
#         # WORKING MEMORY
#         "execution_context": {},
#         # TOOL MEMORY
#         "retrieved_data": {},
#         # CURRENT EXECUTION
#         "tool_result": None,
#         # RESPONSE
#         "final_response": None,
#         "export_path": None,
#         # ERROR
#         "error": None,
#     }

from langchain_core.messages import HumanMessage, AIMessage


def create_initial_state(user_query: str, history: list) -> AgentState:
    """
    Create graph state containing past conversation history and the new query.
    """
    # 1. Convert Gradio dict history into LangChain Message objects
    formatted_messages = []
    if history:
        for turn in history:
            if turn["role"] == "user":
                formatted_messages.append(HumanMessage(content=turn["content"]))
            elif turn["role"] == "assistant":
                formatted_messages.append(AIMessage(content=turn["content"]))

    # 2. Append the brand new query as the final HumanMessage
    formatted_messages.append(HumanMessage(content=user_query))

    return {
        # USER INPUT
        "user_query": user_query,
        # MEMORY - LangGraph nodes will now see the entire chat history
        "messages": formatted_messages,
        "conversation_summary": "",
        # INTENT EXTRACTION
        "intent": None,
        "tool_params": None,
        # WORKING MEMORY
        "execution_context": {},
        # TOOL MEMORY
        "retrieved_data": {},
        # CURRENT EXECUTION
        "tool_result": None,
        # RESPONSE
        "final_response": None,
        "export_path": None,
        # ERROR
        "error": None,
    }
