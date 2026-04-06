import os
from functools import partial
from psycopg2 import pool as pg_pool
from openai import OpenAI
 
from langgraph.graph import StateGraph, END
 
from agent.agent_state import AgentState, create_initial_state
 
# Node imports
from agent.nodes import parse_node
from agent.nodes import summarize_node
from agent.nodes import handle_error_node
from agent.nodes.tool_nodes import (
    get_customer_profile_node,
    get_overdue_loans_node,
    get_repayment_summary_node,
    get_loan_portfolio_stats_node,
    get_collection_efficiency_node,
    get_help_node,
)
 

# ROUTING FUNCTIONS:

def route_to_tool(state: AgentState) -> str:
    """
    Called after classify_intent node.
    Routes to the correct tool node based on intent.
    If classification itself failed (error set) -> go to error handler.
    """
    # If classifier set an error — skip tools entirely
    if state.get("error"):
        return "handle_error"
 
    intent = state.get("intent", "unknown")
 
    route_map = {
        "get_customer_profile": "get_customer_profile",
        "get_overdue_loans": "get_overdue_loans",
        "get_repayment_summary": "get_repayment_summary",
        "get_loan_portfolio_stats": "get_loan_portfolio_stats",
        "get_collection_efficiency": "get_collection_efficiency",
        "get_help": "get_help",
        "unknown": "handle_error",
    }
 
    return route_map.get(intent, "handle_error")
 
 
def route_after_tool(state: AgentState) -> str:
    """
    Called after every tool node.
    If tool set an error -> go to error handler.
    Otherwise -> go to summarizer.
    """
    if state.get("error"):
        return "handle_error"
    return "summarize"
 
 

# GRAPH BUILDING
 
def build_graph(
    db_pool: pg_pool.SimpleConnectionPool,
    llm_client: OpenAI,
    model_name: str,
) -> StateGraph:
    """
    Builds and compiles the LangGraph graph.
 
    Args:
        db_pool: psycopg2 connection pool — shared across all tool nodes
        llm_client: OpenAI client pointed at vLLM container
        model_name: model loaded in vLLM e.g. "Qwen/Qwen2.5-1.5B-Instruct"
 
    Returns:
        Compiled LangGraph graph
    """
 
    # Injecting/pre-filling dependencies into nodes via partial
    # so that only state needs to be passed to LangGraph nodes.
 
    classify = partial(parse_node,
                       client=llm_client,
                       model_name=model_name)

    summarize = partial(summarize_node,
                        client=llm_client,
                        model_name=model_name)
 
    customer_profile = partial(get_customer_profile_node, db_pool = db_pool)
    overdue_loans = partial(get_overdue_loans_node, db_pool = db_pool)
    repayment_summary = partial(get_repayment_summary_node, db_pool = db_pool)
    portfolio_stats = partial(get_loan_portfolio_stats_node, db_pool = db_pool)
    collection_eff = partial(get_collection_efficiency_node, db_pool = db_pool)

    # Note: get_help_node needs no injection.
 
    # Build graph
    graph = StateGraph(AgentState)
 
    # Add nodes
    graph.add_node("classify_intent", classify)
    graph.add_node("get_customer_profile", customer_profile)
    graph.add_node("get_overdue_loans", overdue_loans)
    graph.add_node("get_repayment_summary", repayment_summary)
    graph.add_node("get_loan_portfolio_stats", portfolio_stats)
    graph.add_node("get_collection_efficiency", collection_eff)
    graph.add_node("get_help", get_help_node)
    graph.add_node("summarize", summarize)
    graph.add_node("handle_error", handle_error_node)
 
    # Set entry point
    graph.set_entry_point("classify_intent")
 
    # Adding conditional edges after classifier node:
    # route_to_tool reads intent and returns the next node name
    graph.add_conditional_edges(
        "classify_intent",
        route_to_tool,
        {
            "get_customer_profile": "get_customer_profile",
            "get_overdue_loans": "get_overdue_loans",
            "get_repayment_summary": "get_repayment_summary",
            "get_loan_portfolio_stats": "get_loan_portfolio_stats",
            "get_collection_efficiency": "get_collection_efficiency",
            "get_help": "get_help",
            "handle_error": "handle_error",
        }
    )
 
    # Adding conditional edges after every tool node:
    # route_after_tool checks for errors then routes to summarize or handle_error
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
            }
        )

    # Adding fixed edges:
    graph.add_edge("get_help", END)
    
    # Adding terminal edges:
    graph.add_edge("summarize", END)
    graph.add_edge("handle_error", END)
 
    # Compile:
    return graph.compile()


# Query runner
def run_query(graph, user_query: str) -> str:
    """
    Run a single query through the graph.
    Returns the final natural language response.
    """
    initial_state = create_initial_state(user_query)
    final_state   = graph.invoke(initial_state)
    return final_state.get("final_response", "No response generated.")