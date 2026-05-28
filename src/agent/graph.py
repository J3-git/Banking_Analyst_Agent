# import os
# from functools import partial
# from psycopg2 import pool as pg_pool
# from openai import OpenAI

# from langgraph.graph import StateGraph, END

# from agent.agent_state import AgentState, create_initial_state

# # Node imports
# from agent.nodes import parse_node
# from agent.nodes import summarize_node
# from agent.nodes import handle_error_node
# from agent.nodes.tool_nodes import (
#     get_customer_profile_node,
#     get_overdue_loans_node,
#     get_repayment_summary_node,
#     get_loan_portfolio_stats_node,
#     get_collection_efficiency_node,
#     get_help_node,
# )


# # ROUTING FUNCTIONS:

# def route_to_tool(state: AgentState) -> str:
#     """
#     Called after classify_intent node.
#     Routes to the correct tool node based on intent.
#     If classification itself failed (error set) -> go to error handler.
#     """
#     # If classifier set an error — skip tools entirely
#     if state.get("error"):
#         return "handle_error"

#     intent = state.get("intent", "unknown")

#     route_map = {
#         "get_customer_profile": "get_customer_profile",
#         "get_overdue_loans": "get_overdue_loans",
#         "get_repayment_summary": "get_repayment_summary",
#         "get_loan_portfolio_stats": "get_loan_portfolio_stats",
#         "get_collection_efficiency": "get_collection_efficiency",
#         "get_help": "get_help",
#         "unknown": "handle_error",
#     }

#     return route_map.get(intent, "handle_error")


# def route_after_tool(state: AgentState) -> str:
#     """
#     Called after every tool node.
#     If tool set an error -> go to error handler.
#     Otherwise -> go to summarizer.
#     """
#     if state.get("error"):
#         return "handle_error"
#     return "summarize"


# # GRAPH BUILDING

# def build_graph(
#     db_pool: pg_pool.SimpleConnectionPool,
#     llm_client: OpenAI,
#     model_name: str,
# ) -> StateGraph:
#     """
#     Builds and compiles the LangGraph graph.

#     Args:
#         db_pool: psycopg2 connection pool — shared across all tool nodes
#         llm_client: OpenAI client pointed at vLLM container
#         model_name: model loaded in vLLM e.g. "Qwen/Qwen2.5-1.5B-Instruct"

#     Returns:
#         Compiled LangGraph graph
#     """

#     # Injecting/pre-filling dependencies into nodes via partial
#     # so that only state needs to be passed to LangGraph nodes.

#     classify = partial(parse_node,
#                        client=llm_client,
#                        model_name=model_name)

#     summarize = partial(summarize_node,
#                         client=llm_client,
#                         model_name=model_name)

#     customer_profile = partial(get_customer_profile_node, db_pool = db_pool)
#     overdue_loans = partial(get_overdue_loans_node, db_pool = db_pool)
#     repayment_summary = partial(get_repayment_summary_node, db_pool = db_pool)
#     portfolio_stats = partial(get_loan_portfolio_stats_node, db_pool = db_pool)
#     collection_eff = partial(get_collection_efficiency_node, db_pool = db_pool)

#     # Note: get_help_node needs no injection.

#     # Build graph
#     graph = StateGraph(AgentState)

#     # Add nodes
#     graph.add_node("classify_intent", classify)
#     graph.add_node("get_customer_profile", customer_profile)
#     graph.add_node("get_overdue_loans", overdue_loans)
#     graph.add_node("get_repayment_summary", repayment_summary)
#     graph.add_node("get_loan_portfolio_stats", portfolio_stats)
#     graph.add_node("get_collection_efficiency", collection_eff)
#     graph.add_node("get_help", get_help_node)
#     graph.add_node("summarize", summarize)
#     graph.add_node("handle_error", handle_error_node)

#     # Set entry point
#     graph.set_entry_point("classify_intent")

#     # Adding conditional edges after classifier node:
#     # route_to_tool reads intent and returns the next node name
#     graph.add_conditional_edges(
#         "classify_intent",
#         route_to_tool,
#         {
#             "get_customer_profile": "get_customer_profile",
#             "get_overdue_loans": "get_overdue_loans",
#             "get_repayment_summary": "get_repayment_summary",
#             "get_loan_portfolio_stats": "get_loan_portfolio_stats",
#             "get_collection_efficiency": "get_collection_efficiency",
#             "get_help": "get_help",
#             "handle_error": "handle_error",
#         }
#     )

#     # Adding conditional edges after every tool node:
#     # route_after_tool checks for errors then routes to summarize or handle_error
#     tool_nodes = [
#         "get_customer_profile",
#         "get_overdue_loans",
#         "get_repayment_summary",
#         "get_loan_portfolio_stats",
#         "get_collection_efficiency",
#     ]

#     for tool_node in tool_nodes:
#         graph.add_conditional_edges(
#             tool_node,
#             route_after_tool,
#             {
#                 "summarize": "summarize",
#                 "handle_error": "handle_error",
#             }
#         )

#     # Adding fixed edges:
#     graph.add_edge("get_help", END)

#     # Adding terminal edges:
#     graph.add_edge("summarize", END)
#     graph.add_edge("handle_error", END)

#     # Compile:
#     return graph.compile()


# # Query runner
# def run_query(graph, user_query: str) -> str:
#     """
#     Run a single query through the graph.
#     Returns the final natural language response.
#     """
#     initial_state = create_initial_state(user_query)
#     final_state   = graph.invoke(initial_state)
#     return final_state.get("final_response", "No response generated.")


from langgraph.graph import StateGraph, END

# from langgraph.runtime import Runtime

from agent.agent_state import AgentState, create_initial_state, Intent
from agent.runtime_context import AppContext

# Nodes
from agent.nodes import (
    parse_node,
    summarize_node,
    handle_error_node,
    response_node,
    context_node,
    followup_node,
)

from agent.nodes.tool_nodes import (
    get_customer_profile_node,
    get_overdue_loans_node,
    get_repayment_summary_node,
    get_loan_portfolio_stats_node,
    get_collection_efficiency_node,
    get_help_node,
)

from langgraph.checkpoint.memory import InMemorySaver

# ROUTING FUNCTIONS


def route_after_context(state: AgentState) -> str:
    """
    Called after context_node.
    Short-circuits to followup if no DB call needed.
    """
    if state.get("error"):
        return "handle_error"

    if not state.get("needs_db", True):
        return "followup"

    return "parse"


def route_to_tool(state: AgentState) -> str:
    """
    Called after parse node.
    Routes to the correct tool node based on intent.
    """

    if state.get("error"):
        return "handle_error"

    intent = state.get("intent", "unknown")
    routing_map = {
        Intent.GET_CUSTOMER_PROFILE: "get_customer_profile",
        Intent.GET_OVERDUE_LOANS: "get_overdue_loans",
        Intent.GET_REPAYMENT_SUMMARY: "get_repayment_summary",
        Intent.GET_LOAN_PORTFOLIO_STATS: "get_loan_portfolio_stats",
        Intent.GET_COLLECTION_EFFICIENCY: "get_collection_efficiency",
        Intent.GET_HELP: "get_help",
        Intent.UNKNOWN: "handle_error",
    }
    return routing_map.get(intent, "handle_error")


def route_after_tool(state: AgentState) -> str:
    """
    Called after tool execution.
    """

    if state.get("error"):
        return "handle_error"

    return "summarize"


# Checkpoint
checkpointer = InMemorySaver()

# GRAPH BUILDING


# def build_graph() -> StateGraph:
#     """
#     Build and compile LangGraph workflow.
#     """

#     graph = StateGraph(state_schema=AgentState, context_schema=AppContext)

#     # PARSER
#     graph.add_node("parse", parse_node)

#     # TOOL NODES
#     graph.add_node("get_customer_profile", get_customer_profile_node)

#     graph.add_node("get_overdue_loans", get_overdue_loans_node)

#     graph.add_node(
#         "get_repayment_summary",
#         get_repayment_summary_node,
#     )

#     graph.add_node(
#         "get_loan_portfolio_stats",
#         get_loan_portfolio_stats_node,
#     )

#     graph.add_node(
#         "get_collection_efficiency",
#         get_collection_efficiency_node,
#     )

#     graph.add_node("get_help", get_help_node)

#     # FINAL NODES
#     graph.add_node("summarize", summarize_node)

#     graph.add_node("response", response_node)

#     graph.add_node("handle_error", handle_error_node)

#     # ENTRY POINT
#     graph.set_entry_point("parse")

#     # ROUTING AFTER PARSE
#     graph.add_conditional_edges(
#         "parse",
#         route_to_tool,
#         {
#             "get_customer_profile": "get_customer_profile",
#             "get_overdue_loans": "get_overdue_loans",
#             "get_repayment_summary": "get_repayment_summary",
#             "get_loan_portfolio_stats": "get_loan_portfolio_stats",
#             "get_collection_efficiency": "get_collection_efficiency",
#             "get_help": "get_help",
#             "handle_error": "handle_error",
#         },
#     )

#     # ROUTING AFTER TOOLS
#     tool_nodes = [
#         "get_customer_profile",
#         "get_overdue_loans",
#         "get_repayment_summary",
#         "get_loan_portfolio_stats",
#         "get_collection_efficiency",
#     ]

#     for tool_node in tool_nodes:

#         graph.add_conditional_edges(
#             tool_node,
#             route_after_tool,
#             {
#                 "summarize": "summarize",
#                 "handle_error": "handle_error",
#             },
#         )

#     # FIXED EDGES
#     # graph.add_edge("get_help", END)
#     # graph.add_edge("summarize", END)
#     # graph.add_edge("handle_error", END)

#     graph.add_edge(
#         "get_help", "response"
#     )  # Route directly to response to log system help text

#     graph.add_edge(
#         "summarize", "response"
#     )  # Route summarize results into response formatter

#     graph.add_edge("handle_error", "response")  # Route fallback errors into response

#     graph.add_edge("response", END)

#     return graph.compile(checkpointer=checkpointer)


def build_graph() -> StateGraph:
    """
    Build and compile LangGraph workflow.
    """

    graph = StateGraph(state_schema=AgentState, context_schema=AppContext)

    # CONTEXT ENRICHER
    graph.add_node("context", context_node)

    # FOLLOW UP NODE
    graph.add_node("followup", followup_node)

    # PARSER
    graph.add_node("parse", parse_node)

    # TOOL NODES
    graph.add_node("get_customer_profile", get_customer_profile_node)

    graph.add_node("get_overdue_loans", get_overdue_loans_node)

    graph.add_node(
        "get_repayment_summary",
        get_repayment_summary_node,
    )

    graph.add_node(
        "get_loan_portfolio_stats",
        get_loan_portfolio_stats_node,
    )

    graph.add_node(
        "get_collection_efficiency",
        get_collection_efficiency_node,
    )

    graph.add_node("get_help", get_help_node)

    # FINAL NODES
    graph.add_node("summarize", summarize_node)

    graph.add_node("response", response_node)

    graph.add_node("handle_error", handle_error_node)

    # ENTRY POINT
    graph.set_entry_point("context")

    # routing after context
    graph.add_conditional_edges(
        "context",
        route_after_context,
        {
            "followup": "followup",
            "parse": "parse",
            "handle_error": "handle_error",
        },
    )

    # ROUTING AFTER PARSE
    graph.add_conditional_edges(
        "parse",
        route_to_tool,
        {
            "get_customer_profile": "get_customer_profile",
            "get_overdue_loans": "get_overdue_loans",
            "get_repayment_summary": "get_repayment_summary",
            "get_loan_portfolio_stats": "get_loan_portfolio_stats",
            "get_collection_efficiency": "get_collection_efficiency",
            "get_help": "get_help",
            "handle_error": "handle_error",
        },
    )

    # ROUTING AFTER TOOLS
    tool_nodes = [
        "get_customer_profile",
        "get_overdue_loans",
        "get_repayment_summary",
        "get_loan_portfolio_stats",
        "get_collection_efficiency",
    ]

    for tool_node in tool_nodes:

        graph.add_conditional_edges(
            tool_node,
            route_after_tool,
            {
                "summarize": "summarize",
                "handle_error": "handle_error",
            },
        )

    # FIXED EDGES
    # graph.add_edge("get_help", END)
    # graph.add_edge("summarize", END)
    # graph.add_edge("handle_error", END)

    graph.add_edge(
        "get_help", "response"
    )  # Route directly to response to log system help text

    graph.add_edge(
        "summarize", "response"
    )  # Route summarize results into response formatter

    graph.add_edge("handle_error", "response")  # Route fallback errors into response

    # followup fixed edge
    graph.add_edge("followup", "response")

    graph.add_edge("response", END)

    # # To create flowchart image
    # import os

    # os.makedirs("./exports", exist_ok=True)
    # graph = graph.compile(checkpointer=checkpointer)
    # graph_visual = graph.get_graph()
    # graph_visual_png = graph_visual.draw_mermaid_png()
    # with open("./exports/graph.png", "wb") as f:
    #     f.write(graph_visual_png)
    # print("Graph image saved in exports directory.")
    # return graph

    return graph.compile(checkpointer=checkpointer)


# QUERY RUNNER


def run_query(graph, user_query: str, context: AppContext, history: list = None) -> str:
    """
    Execute one query through graph, passing down multi-turn history.
    """
    # Pass history
    config = {"configurable": {"thread_id": "1"}}

    # Check if this thread already has memory stored in the checkpointer
    current_state = graph.get_state(config)

    if not current_state.values:
        # Fresh thread. Run your full setup tool.
        input_state = create_initial_state(user_query=user_query, history=history)
    else:
        # TURN 2+: Reused thread.
        # Only pass the fresh transient query. LangGraph automatically fetches your previous messages and execution_context from memory!
        input_state = {"user_query": user_query}

    print(f"DEBUG:in run_query:")
    print(f"DEBUG:current_state: {current_state}")
    print(f"DEBUG:input_state: {input_state}")
    print(f"DEBUG:history: {history}")

    final_state = graph.invoke(
        input_state,
        config,
        context=context,
    )

    return final_state["final_response"]
