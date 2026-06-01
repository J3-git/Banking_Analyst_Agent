from agent.agent_state import (
    AgentState,
    ExecutionContext,
    CompareSlot,
)


def _make_label(params: dict) -> str:
    """Build a human-readable label from params dict."""
    parts = []
    if params.get("city"):
        parts.append(str(params["city"]))
    if params.get("loan_type"):
        parts.append(str(params["loan_type"]))
    if params.get("period"):
        parts.append(str(params["period"]))
    if params.get("group_by"):
        parts.append(f"by {params['group_by']}")
    return ", ".join(parts) if parts else "Overall"


def merge_node(state: AgentState) -> dict:
    """
    Collects tool results from compare flow and builds CompareSlots
    in ExecutionContext.

    Two scenarios handled:
    1. Both params explicit (two tool calls) -- tool_results has two entries
    2. One param from history (one tool call) -- slot_a from execution_context,
       slot_b from current tool_result

    Ownership rules:
      - This node writes ONLY to: execution_context, tool_results
    """

    intent = state.get("intent")
    intent_str = intent.value if hasattr(intent, "value") else (intent or "unknown")

    tool_results = list(state.get("tool_results") or [])
    tool_result = state.get("tool_result")
    retrieved_data = state.get("retrieved_data", {})
    compare_keys = list(state.get("compare_keys") or [])
    compare_labels: dict = state.get("_compare_labels") or {}

    prev: ExecutionContext = state.get("execution_context")

    print("==========================================================")
    print("DEBUG: in merge_node:")
    print(f"DEBUG: intent: {intent_str}")
    print(f"DEBUG: tool_results count: {len(tool_results)}")
    print(f"DEBUG: retrieved_data keys: {list(retrieved_data.keys())}")
    print(f"DEBUG: compare_keys: {compare_keys}")
    print(f"DEBUG: compare_labels: {compare_labels}")
    print("==========================================================")

    # ---------------------------------------------------------------------------
    # SCENARIO 1: Both params explicit -- two tool calls, two results in tool_results
    # ---------------------------------------------------------------------------
    if len(tool_results) == 2 and len(compare_keys) == 2:
        key_a, key_b = compare_keys

        entry_a = retrieved_data.get(key_a, {})
        entry_b = retrieved_data.get(key_b, {})

        params_a = entry_a.get("params", {})
        params_b = entry_b.get("params", {})

        label_a = compare_labels.get(key_a) or _make_label(params_a)
        label_b = compare_labels.get(key_b) or _make_label(params_b)

        slot_a = CompareSlot(
            label=label_a,
            intent=intent_str,
            params=params_a,
            result=entry_a.get("result", {}),
            csv_path=entry_a.get("csv_path"),
        )

        slot_b = CompareSlot(
            label=label_b,
            intent=intent_str,
            params=params_b,
            result=entry_b.get("result", {}),
            csv_path=entry_b.get("csv_path"),
        )

    # ---------------------------------------------------------------------------
    # SCENARIO 2: One param from history -- slot_a from ExecutionContext,
    # slot_b from current tool_result
    # ---------------------------------------------------------------------------
    elif len(tool_results) == 1 and prev and prev.last_tool_result:
        key_b = compare_keys[1] if len(compare_keys) == 2 else None
        key_a = compare_keys[0] if len(compare_keys) == 2 else None

        params_a = prev.last_params or {}
        params_b = state.get("tool_params")
        params_b_dict = params_b.model_dump(exclude_none=True) if params_b else {}

        label_a = compare_labels.get(key_a) if key_a else _make_label(params_a)
        label_b = compare_labels.get(key_b) if key_b else _make_label(params_b_dict)

        slot_a = CompareSlot(
            label=label_a or _make_label(params_a),
            intent=intent_str,
            params=params_a,
            result=prev.last_tool_result,
        )

        slot_b = CompareSlot(
            label=label_b or _make_label(params_b_dict),
            intent=intent_str,
            params=params_b_dict,
            result=tool_result or (tool_results[0] if tool_results else {}),
        )

    else:
        # fallback -- should not happen in normal flow
        print("DEBUG: merge_node -- unexpected state, cannot build compare slots")
        return {
            "error": "merge_node: insufficient data to build comparison",
        }

    # carry forward all previous context, update only compare slots
    updated_context = ExecutionContext(
        last_intent=prev.last_intent if prev else intent_str,
        last_params=prev.last_params if prev else {},
        last_tool_result=prev.last_tool_result if prev else None,
        last_response=prev.last_response if prev else None,
        current_customer_id=prev.current_customer_id if prev else None,
        current_customer_name=prev.current_customer_name if prev else None,
        active_loan_id=prev.active_loan_id if prev else None,
        active_city=prev.active_city if prev else None,
        active_loan_type=prev.active_loan_type if prev else None,
        active_period=prev.active_period if prev else None,
        compare_slot_a=slot_a,
        compare_slot_b=slot_b,
    )

    print("==========================================================")
    print("DEBUG: merge_node built compare slots:")
    print(f"DEBUG: slot_a label: {slot_a.label}")
    print(f"DEBUG: slot_b label: {slot_b.label}")
    print("==========================================================")
    print(f"DEBUG: slot_a.result: {slot_a.result}")
    print(f"DEBUG: slot_b.result: {slot_b.result}")
    print("==========================================================")

    return {
        "execution_context": updated_context,
        "tool_results": [slot_a.result, slot_b.result],
    }
