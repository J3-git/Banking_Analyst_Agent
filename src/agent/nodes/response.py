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
from langgraph.runtime import Runtime
from agent.runtime_context import AppContext


def response_node(state: AgentState, runtime: Runtime[AppContext]) -> dict:
    response = state.get("final_response", "No response generated.")

    # 1. Fetch current historical trace
    messages = list(state.get("messages", []))

    # 2. Append the assistant output to history sequence safely
    messages.append(AIMessage(content=response))

    execution_context = {
        **state.get("execution_context", {}),
        "last_node": "response_node",
        "response_generated": True,
    }

    print("==========================================================")
    print(f"DEBUG:in response node:")
    print(f"DEBUG:messages: {messages}")
    print(f"DEBUG:execution_context: {execution_context}")
    print("==========================================================")

    # 3. Explicitly forward 'messages' and updated 'execution_context' back to graph state
    return {
        "messages": messages,
        "execution_context": execution_context,
        "retrieved_data": state.get("retrieved_data", {}),
        "tool_result": state.get("tool_result"),
        "final_response": response,
        "error": state.get("error"),
    }
