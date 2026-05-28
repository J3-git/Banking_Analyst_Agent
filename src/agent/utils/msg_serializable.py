from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)

from collections.abc import Sequence


def _serialize_messages(messages: Sequence[BaseMessage], max_messages: int = 5) -> str:
    """
    Convert recent messages into prompt-friendly text.
    Supports LangGraph's native message sequence wrappers safely.
    """
    # 1. Fallback to empty list if None is passed
    if not messages:
        return ""

    # 2. Safely grab the last N elements from the sequence
    # This works flawlessly across lists and LangGraph sequence proxies
    recent_messages = list(messages)[-max_messages:]

    lines = []

    for msg in recent_messages:
        if isinstance(msg, HumanMessage):
            role = "User"
        elif isinstance(msg, AIMessage):
            role = "Assistant"
        elif isinstance(msg, SystemMessage):
            role = "System"
        else:
            role = "Unknown"
        lines.append(f"{role}: {msg.content}")

    return "\n".join(lines)
