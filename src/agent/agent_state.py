# from enum import Enum
# from typing import TypedDict, Optional, Any, Union

# from pydantic import BaseModel
# from langchain_core.messages import BaseMessage

# from typing import Annotated
# from langgraph.graph.message import add_messages

# # ENUMS


# class Intent(str, Enum):
#     GET_CUSTOMER_PROFILE = "get_customer_profile"
#     GET_OVERDUE_LOANS = "get_overdue_loans"
#     GET_REPAYMENT_SUMMARY = "get_repayment_summary"
#     GET_LOAN_PORTFOLIO_STATS = "get_loan_portfolio_stats"
#     GET_COLLECTION_EFFICIENCY = "get_collection_efficiency"
#     GET_HELP = "get_help"
#     UNKNOWN = "unknown"


# class City(str, Enum):
#     MUMBAI = "Mumbai"
#     DELHI = "Delhi"
#     PUNE = "Pune"
#     BANGALORE = "Bangalore"


# class LoanType(str, Enum):
#     PERSONAL = "Personal"
#     HOME = "Home"
#     BUSINESS = "Business"
#     VEHICLE = "Vehicle"
#     EDUCATION = "Education"
#     GOLD = "Gold"


# class PortfolioGroupBy(str, Enum):
#     LOAN_TYPE = "loan_type"
#     CITY = "city"
#     STATUS = "status"


# class Period(str, Enum):
#     THIS_MONTH = "this_month"
#     LAST_MONTH = "last_month"
#     THIS_QUARTER = "this_quarter"
#     THIS_YEAR = "this_year"


# # TOOL PARAM SCHEMAS


# class CustomerProfileParams(BaseModel):
#     customer_id: int


# class OverdueLoansParams(BaseModel):
#     city: Optional[City] = None
#     loan_type: Optional[LoanType] = None
#     min_days_overdue: Optional[int] = None


# class RepaymentSummaryParams(BaseModel):
#     customer_id: int
#     loan_id: Optional[int] = None


# class LoanPortfolioStatsParams(BaseModel):
#     group_by: Optional[PortfolioGroupBy] = None
#     city: Optional[City] = None
#     loan_type: Optional[LoanType] = None


# class CollectionEfficiencyParams(BaseModel):
#     city: Optional[City] = None
#     loan_type: Optional[LoanType] = None
#     period: Optional[Period] = None


# # TOOL PARAM UNION

# ToolParams = Union[
#     CustomerProfileParams,
#     OverdueLoansParams,
#     RepaymentSummaryParams,
#     LoanPortfolioStatsParams,
#     CollectionEfficiencyParams,
# ]

# # AGENT STATE


# class AgentState(TypedDict):

#     # CURRENT USER INPUT
#     user_query: str

#     # CONVERSATION MEMORY
#     messages: Annotated[list[BaseMessage], add_messages]
#     conversation_summary: str

#     # INTENT + PARAM EXTRACTION
#     intent: Optional[Intent]
#     tool_params: Optional[ToolParams]

#     # SHARED WORKING MEMORY
#     execution_context: dict[str, Any]

#     # STORED TOOL OUTPUTS
#     retrieved_data: dict[str, Any]

#     # CURRENT EXECUTION RESULT
#     tool_result: Optional[Any]

#     # FINAL RESPONSE
#     final_response: Optional[str]
#     export_path: Optional[str]

#     # ERROR HANDLING
#     error: Optional[str]

#     enriched_query: str  # resolved query from context_node
#     needs_db: bool
#     is_followup: bool


# # INITIAL STATE FACTORY


# # def create_initial_state(user_query: str) -> AgentState:
# #     """
# #     Create clean initial graph state for each invocation.
# #     """

# #     return {
# #         # USER INPUT
# #         "user_query": user_query,
# #         # MEMORY
# #         "messages": [],
# #         "conversation_summary": "",
# #         # INTENT EXTRACTION
# #         "intent": None,
# #         "tool_params": None,
# #         # WORKING MEMORY
# #         "execution_context": {},
# #         # TOOL MEMORY
# #         "retrieved_data": {},
# #         # CURRENT EXECUTION
# #         "tool_result": None,
# #         # RESPONSE
# #         "final_response": None,
# #         "export_path": None,
# #         # ERROR
# #         "error": None,
# #     }

# from langchain_core.messages import HumanMessage, AIMessage


# def create_initial_state(
#     user_query: str,
#     history: list | None = None,
# ) -> AgentState:
#     """
#     Create per-turn initial state.

#     IMPORTANT:
#     - Persistent memory (execution_context, retrieved_data, messages)
#       comes from LangGraph checkpointing.
#     - We only initialize transient per-turn fields here.
#     """

#     formatted_messages = []

#     # Optional UI history hydration
#     # Useful mainly for first load / external chat UIs like Gradio
#     if history:
#         for turn in history:

#             role = turn.get("role")
#             content = turn.get("content")

#             if not content:
#                 continue

#             if role == "user":
#                 formatted_messages.append(HumanMessage(content=content))

#             elif role == "assistant":
#                 formatted_messages.append(AIMessage(content=content))

#     # Add current user query
#     formatted_messages.append(HumanMessage(content=user_query))

#     return {
#         "user_query": user_query,
#         "messages": formatted_messages,
#         "execution_context": {},
#         "intent": None,
#         "tool_params": None,
#         "tool_result": None,
#         "final_response": None,
#         "export_path": None,
#         "error": None,
#     }

from enum import Enum
from typing import TypedDict, Optional, Any, Union
from datetime import datetime

from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

import operator
from typing import Annotated
from langgraph.graph.message import add_messages

# REDUCERS FOR PARALLEL EXECUTION


def _keep_last(left: Any, right: Any) -> Any:
    """Last write wins — used for scalar fields written by parallel branches."""
    return right if right is not None else left


def _merge_dicts(left: dict, right: dict) -> dict:
    """Merge two dicts — used for retrieved_data written by parallel branches."""
    if not left:
        return right or {}
    if not right:
        return left or {}
    return {**left, **right}


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


class FollowUpType(str, Enum):
    DRILL_DOWN = "drill_down"
    COMPARE = "compare"
    VISUALIZE = "visualize"
    REPORT = "report"
    CONVERSATIONAL = "conversational"  # answer from history, no tool needed


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


ToolParams = Union[
    CustomerProfileParams,
    OverdueLoansParams,
    RepaymentSummaryParams,
    LoanPortfolioStatsParams,
    CollectionEfficiencyParams,
]


# RETRIEVED DATA ENTRY - Each cache entry is self-contained with its own metadata.


class RetrievedDataEntry(BaseModel):
    intent: str
    params: dict[str, Any]
    result: dict[str, Any]
    fetched_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    csv_path: Optional[str] = None
    chart_path: Optional[str] = None
    dataset_id: Optional[str] = None


# COMPARE SLOT
# Holds one side of a comparison (params + result).
# Populated by merge_node after parallel/sequential tool calls.


class CompareSlot(BaseModel):
    label: str  # human-readable e.g. "Mumbai" or "this_month"
    intent: str
    params: dict[str, Any]
    result: dict[str, Any]
    csv_path: Optional[str] = None


# EXECUTION CONTEXT
# Single source of truth for cross-turn analytical state.
# Owned and written ONLY by summarize_node and merge_node.
# Tool nodes must NOT write to this.


class ExecutionContext(BaseModel):

    # last successful turn
    last_intent: Optional[str] = None
    last_params: Optional[dict[str, Any]] = None
    last_tool_result: Optional[dict[str, Any]] = None
    last_response: Optional[str] = None

    # active entity references (resolved by context_node for follow-ups)
    current_customer_id: Optional[int] = None
    current_customer_name: Optional[str] = None
    active_loan_id: Optional[int] = None
    active_city: Optional[str] = None
    active_loan_type: Optional[str] = None
    active_period: Optional[str] = None

    # compare state
    # slot_a is filled first (from history or first tool call)
    # slot_b is filled by the second tool call
    # both slots present -> merge_node triggers comparison summary
    compare_slot_a: Optional[CompareSlot] = None
    compare_slot_b: Optional[CompareSlot] = None

    def to_dict(self) -> dict:
        return self.model_dump(exclude_none=True)


# AGENT STATE


class AgentState(TypedDict):

    # current user input
    user_query: str

    # conversation memory
    messages: Annotated[list[BaseMessage], add_messages]
    conversation_summary: str

    # context resolution output (written by context_node)
    enriched_query: str
    needs_db: bool
    is_followup: bool
    follow_up_type: Optional[FollowUpType] = None  # set by context_node

    # intent + param extraction (written by parse_node)
    intent: Optional[Intent]
    tool_params: Optional[ToolParams]

    # tool execution outputs (written ONLY by tool nodes)
    # tool_results is a list to support compare (two results in one turn)
    tool_result: Annotated[Optional[Any], _keep_last]  # single result - standard flow
    tool_results: Annotated[
        list[Any], operator.add
    ]  # multi-result - compare flow, reducer appends

    # retrieved data cache
    # key: "intent:param1_val:param2_val:..."
    # value: RetrievedDataEntry.model_dump()
    retrieved_data: Annotated[dict[str, Any], _merge_dicts]

    # analytical context - written ONLY by summarize_node and merge_node
    execution_context: Optional[ExecutionContext]

    # response
    final_response: Optional[str]
    csv_paths: list[str]  # CSV exports - accumulates across turns
    chart_paths: list[str]  # image exports - accumulates across turns

    # compare routing - set by compare_router, read by merge_node
    compare_keys: list[str]
    _compare_labels: dict[str, str]
    _compare_param_b: Optional[dict[str, Any]]  # second param set for dual Send

    # error
    error: Annotated[Optional[str], _keep_last]


# INITIAL STATE FACTORY
# Only transient per-turn fields are initialized here.
# Persistent fields (execution_context, retrieved_data, messages history, csv_paths) are intentionally omitted - the checkpointer carries them.


def create_initial_state(
    user_query: str,
    history: list | None = None,
) -> AgentState:
    """
    Create per-turn initial state.

    Only resets transient fields. Persistent analytical state
    (execution_context, retrieved_data, csv_paths) is carried
    forward by LangGraph checkpointing.
    """

    formatted_messages = []

    if history:
        for turn in history:
            role = turn.get("role")
            content = turn.get("content")
            if not content:
                continue
            if role == "user":
                formatted_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                formatted_messages.append(AIMessage(content=content))

    formatted_messages.append(HumanMessage(content=user_query))

    return {
        # per-turn inputs
        "user_query": user_query,
        "messages": formatted_messages,
        # reset routing signals each turn
        "enriched_query": "",
        "needs_db": True,
        "is_followup": False,
        "follow_up_type": None,
        # reset intent extraction each turn
        "intent": None,
        "tool_params": None,
        # reset tool execution outputs each turn
        "tool_result": None,
        "tool_results": [],
        "compare_keys": [],
        "_compare_labels": {},
        "_compare_param_b": None,
        # reset response each turn
        "final_response": None,
        "error": None,
        # --- DO NOT initialize these ---
        # execution_context   -> checkpointer carries forward
        # retrieved_data      -> checkpointer carries forward
        # csv_paths        -> checkpointer carries forward
        # chart_paths         -> checkpointer carries forward
        # conversation_summary -> checkpointer carries forward
    }
