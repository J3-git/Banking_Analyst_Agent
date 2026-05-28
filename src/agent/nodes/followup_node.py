from langchain_core.messages import HumanMessage, AIMessage
from langgraph.runtime import Runtime

from agent.agent_state import AgentState
from agent.runtime_context import AppContext
from agent.utils import _call_llm, _serialize_messages


def followup_node(state: AgentState, runtime: Runtime[AppContext]) -> dict:
    """
    Answers purely from conversation history.
    Only reached when context_node sets needs_db: false.
    No DB call, no intent classification.
    """
    try:
        messages = list(state.get("messages", []))
        conversation_history = _serialize_messages(messages)
        enriched_query = state.get("enriched_query") or state["user_query"]

        prompt = f"""You are a banking loan analyst assistant.
Answer the user's question using only the conversation history below.
Do not fetch new data. Do not make up values not present in history.
If the answer is not in history, say so clearly.

Conversation history:
{conversation_history}

User question: {enriched_query}


Respond in plain text. Be concise.
"""

        response = _call_llm(
            user_prompt=prompt,
            model_name=runtime.context.model_name,
            client=runtime.context.client,
        )

        print("==========================================================")
        print(f"DEBUG:follow up node: ")
        print(f"DEBUG:conversation_history: {conversation_history}")
        print(f"DEBUG:post response: {response}")
        print("==========================================================")

        return {
            "final_response": response,
            "error": None,
        }

    except Exception as e:
        print("==========================================================")
        print(f"in follow up node: exception occured:")
        print(f"error: {e}")
        print("==========================================================")
        return {
            "final_response": None,
            "error": f"Followup node failed: {str(e)}",
        }
