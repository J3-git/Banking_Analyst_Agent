# from langchain_core.messages import AIMessage
# from agent.agent_state import AgentState
# from langgraph.runtime import Runtime
# from agent.runtime_context import AppContext

# RESPONSE NODE


# def response_node(
#     state: AgentState,
# ) -> dict:

#     response = state.get("final_response", "No response generated.")

#     # add assistant response to memory
#     state["messages"].append(AIMessage(content=response))

#     return {"messages": state["messages"]}

# from langchain_core.messages import AIMessage


# def response_node(state: AgentState, runtime: Runtime[AppContext]) -> dict:

#     response = state.get("final_response", "No response generated.")

#     messages = list(state.get("messages", []))
#     messages.append(AIMessage(content=response))

#     return {
#         "messages": messages,
#         "execution_context": state.get("execution_context", {}),
#         "retrieved_data": state.get("retrieved_data", {}),
#     }

from langchain_core.messages import AIMessage
from agent.agent_state import AgentState

# for debug
import inspect


def response_node(state: AgentState) -> dict:
    """
    Appends assistant response to message history and returns final response.

    Ownership rules:
      - This node writes ONLY to: messages, final_response
    """
    # Debug start
    frame = inspect.currentframe()
    print("==============================================================")
    print(f"DEBUG: Entered function: {frame.f_code.co_name}")
    # Debug end

    response = state.get("final_response") or "No response generated."

    print(f"DEBUG response_node: final_response: {response}")

    csv_paths = state.get("csv_paths") or []
    chart_paths = state.get("chart_paths") or []

    print(f"DEBUG response_node: csv_paths: {csv_paths}")
    print(f"DEBUG response_node: chart_paths: {chart_paths}")
    print("==========================================================")

    # add_messages reducer handles appending -- return only the new message
    return {
        "messages": [AIMessage(content=response)],
        "final_response": response,
        "csv_paths": csv_paths,
        "chart_paths": chart_paths,
    }
