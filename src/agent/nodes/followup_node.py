import json
from langgraph.runtime import Runtime
from agent.agent_state import AgentState, ExecutionContext
from agent.runtime_context import AppContext
from agent.utils import _call_llm, _serialize_messages

# for debug
import inspect


def followup_node(state: AgentState, runtime: Runtime[AppContext]) -> dict:
    """
    Answers purely from conversation history and execution context.
    Only reached when context_node sets needs_db: false.

    Ownership rules:
    - This node writes ONLY to: final_response, error
    """

    # Debug start
    frame = inspect.currentframe()
    print("==============================================================")
    print(f"DEBUG: Entered function: {frame.f_code.co_name}")
    # Debug end

    try:
        messages = list(state.get("messages", []))
        conversation_history = _serialize_messages(messages)
        query = state["enriched_query"]

        execution_context: ExecutionContext = state.get("execution_context")
        execution_context_dict = (
            execution_context.to_dict() if execution_context else {}
        )

        prompt = f"""You are a banking loan analyst assistant.

Answer the user's question using only the conversation history and execution context below.
Do not fetch new data. Do not make up values not present in history or context.
If the answer is not available, say so clearly.

Execution context (last fetched data summary):
{json.dumps(execution_context_dict, indent=2)}

Conversation history:
{conversation_history}

User question: {query}

Respond in plain text. Be concise and action-oriented.
"""
        print(f"DEBUG followup_node: calling _call_llm")

        response = _call_llm(
            user_prompt=prompt,
            model_name=runtime.context.model_name,
            client=runtime.context.client,
        )

        print(f"DEBUG followup_node: returned back from _call_llm")
        print(f"DEBUG followup_node: query: {query}")
        print(f"DEBUG followup_node: execution_context: {execution_context_dict}")
        print(f"DEBUG followup_node: response: {response}")
        print("==========================================================")

        return {
            "final_response": response,
            "error": None,
        }

    except Exception as e:
        print("DEBUG followup_node: in followup_node exception occurred:")
        print(f"DEBUG followup_node: error: {e}")
        print(f"DEBUG followup_node: returning default values")
        print("==========================================================")

        return {
            "final_response": None,
            "error": f"Followup node failed: {str(e)}",
        }
