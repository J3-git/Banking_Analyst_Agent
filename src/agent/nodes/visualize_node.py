import os
import uuid
from collections import defaultdict
import matplotlib

matplotlib.use("Agg")  # non-interactive backend - no display needed
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from agent.agent_state import AgentState, ExecutionContext, CompareSlot

CHARTS_DIR = os.path.join("exports", "charts")


def _ensure_charts_dir():
    os.makedirs(CHARTS_DIR, exist_ok=True)


def _chart_path(prefix: str) -> str:
    _ensure_charts_dir()
    return os.path.join(CHARTS_DIR, f"{prefix}_{uuid.uuid4().hex[:8]}.png")


# SINGLE RESULT CHARTS


def _chart_overdue_loans(result: dict, title: str) -> str:
    buckets = result.get("dpd_buckets", {})
    if not buckets:
        return None

    labels = ["1-30 days", "31-60 days", "61-90 days", "90+ days"]
    values = [
        buckets.get("early_1_to_30_days", 0),
        buckets.get("moderate_31_to_60_days", 0),
        buckets.get("serious_61_to_90_days", 0),
        buckets.get("critical_above_90_days", 0),
    ]
    colors = ["#4CAF50", "#FFC107", "#FF5722", "#B71C1C"]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(labels, values, color=colors)
    ax.bar_label(bars, padding=3)
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_ylabel("Number of Loans")
    ax.set_xlabel("DPD Bucket")
    plt.tight_layout()

    path = _chart_path("overdue_loans")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def _chart_portfolio_stats(result: dict, title: str) -> str:
    breakdown = result.get("breakdown", [])
    if not breakdown:
        return None

    labels = [str(r.get("group_name", "")) for r in breakdown]
    values = [float(r.get("default_rate_pct") or 0) for r in breakdown]

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(labels, values, color="#1565C0")
    ax.bar_label(bars, fmt="%.1f%%", padding=3)
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_ylabel("Default Rate (%)")
    ax.set_xlabel(f"Grouped by: {result.get('grouped_by', '')}")
    ax.yaxis.set_major_formatter(mticker.PercentFormatter())
    plt.tight_layout()

    path = _chart_path("portfolio_stats")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def _chart_collection_efficiency(result: dict, title: str) -> str:
    trend_data = result.get("monthly_trend", [])
    if not trend_data:
        return None

    months = [r.get("month", "") for r in reversed(trend_data)]
    rates = [float(r.get("recovery_rate_pct") or 0) for r in reversed(trend_data)]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(months, rates, marker="o", color="#00695C", linewidth=2)
    ax.fill_between(months, rates, alpha=0.1, color="#00695C")
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_ylabel("Recovery Rate (%)")
    ax.set_xlabel("Month")
    ax.yaxis.set_major_formatter(mticker.PercentFormatter())
    plt.xticks(rotation=30)
    plt.tight_layout()

    path = _chart_path("collection_efficiency")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def _chart_repayment_summary(result: dict, title: str) -> str:
    summary = result.get("summary", {})
    if not summary:
        return None

    labels = ["Good", "Late", "Bad", "Partial Recovery"]
    values = [
        summary.get("good_payments", 0),
        summary.get("late_payments", 0),
        summary.get("bad_payments", 0),
        summary.get("partial_recovery", 0),
    ]
    colors = ["#388E3C", "#F9A825", "#C62828", "#6A1B9A"]

    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(labels, values, color=colors)
    ax.bar_label(bars, padding=3)
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_ylabel("Number of EMIs")
    plt.tight_layout()

    path = _chart_path("repayment_summary")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def _chart_customer_profile(result: dict, title: str) -> str:
    loans = result.get("loan_summaries", [])
    if not loans:
        return None

    exposure = defaultdict(float)
    for loan in loans:
        loan_type = loan.get("loan_type", "Unknown")
        exposure[loan_type] += float(loan.get("outstanding_amount") or 0)

    labels = list(exposure.keys())
    values = list(exposure.values())

    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(labels, values, color="#1565C0")
    ax.bar_label(bars, fmt="₹%.0f", padding=3)
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_ylabel("Outstanding Amount (₹)")
    ax.set_xlabel("Loan Type")
    plt.tight_layout()

    path = _chart_path("customer_profile")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


CHART_BUILDERS = {
    "get_overdue_loans": _chart_overdue_loans,
    "get_loan_portfolio_stats": _chart_portfolio_stats,
    "get_collection_efficiency": _chart_collection_efficiency,
    "get_repayment_summary": _chart_repayment_summary,
    "get_customer_profile": _chart_customer_profile,
}


# COMPARE CHARTS


def _chart_compare_overdue(slot_a: CompareSlot, slot_b: CompareSlot) -> str:
    buckets_a = slot_a.result.get("dpd_buckets", {})
    buckets_b = slot_b.result.get("dpd_buckets", {})

    labels = ["1-30 days", "31-60 days", "61-90 days", "90+ days"]
    keys = [
        "early_1_to_30_days",
        "moderate_31_to_60_days",
        "serious_61_to_90_days",
        "critical_above_90_days",
    ]

    values_a = [buckets_a.get(k, 0) for k in keys]
    values_b = [buckets_b.get(k, 0) for k in keys]

    x = range(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    bars_a = ax.bar(
        [i - width / 2 for i in x], values_a, width, label=slot_a.label, color="#1565C0"
    )
    bars_b = ax.bar(
        [i + width / 2 for i in x], values_b, width, label=slot_b.label, color="#C62828"
    )
    ax.bar_label(bars_a, padding=3)
    ax.bar_label(bars_b, padding=3)
    ax.set_title(
        f"Overdue Loans: {slot_a.label} vs {slot_b.label}",
        fontsize=13,
        fontweight="bold",
    )
    ax.set_ylabel("Number of Loans")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.legend()
    plt.tight_layout()

    path = _chart_path("compare_overdue")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def _chart_compare_portfolio(slot_a: CompareSlot, slot_b: CompareSlot) -> str:
    breakdown_a = {
        r["group_name"]: float(r.get("default_rate_pct") or 0)
        for r in slot_a.result.get("breakdown", [])
    }
    breakdown_b = {
        r["group_name"]: float(r.get("default_rate_pct") or 0)
        for r in slot_b.result.get("breakdown", [])
    }

    all_groups = sorted(set(breakdown_a) | set(breakdown_b))
    values_a = [breakdown_a.get(g, 0) for g in all_groups]
    values_b = [breakdown_b.get(g, 0) for g in all_groups]

    x = range(len(all_groups))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    bars_a = ax.bar(
        [i - width / 2 for i in x], values_a, width, label=slot_a.label, color="#1565C0"
    )
    bars_b = ax.bar(
        [i + width / 2 for i in x], values_b, width, label=slot_b.label, color="#C62828"
    )
    ax.bar_label(bars_a, fmt="%.1f%%", padding=3)
    ax.bar_label(bars_b, fmt="%.1f%%", padding=3)
    ax.set_title(
        f"Portfolio Default Rate: {slot_a.label} vs {slot_b.label}",
        fontsize=13,
        fontweight="bold",
    )
    ax.set_ylabel("Default Rate (%)")
    ax.set_xticks(list(x))
    ax.set_xticklabels(all_groups, rotation=20)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter())
    ax.legend()
    plt.tight_layout()

    path = _chart_path("compare_portfolio")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def _chart_compare_collection(slot_a: CompareSlot, slot_b: CompareSlot) -> str:
    overall_a = slot_a.result.get("overall", {})
    overall_b = slot_b.result.get("overall", {})

    metrics = ["Recovery Rate %", "Total Collected", "Still Missed"]
    values_a = [
        float(overall_a.get("recovery_rate_pct") or 0),
        float(overall_a.get("total_amount_collected") or 0) / 100000,
        float(overall_a.get("still_missed") or 0),
    ]
    values_b = [
        float(overall_b.get("recovery_rate_pct") or 0),
        float(overall_b.get("total_amount_collected") or 0) / 100000,
        float(overall_b.get("still_missed") or 0),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(14, 5))
    fig.suptitle(
        f"Collection Efficiency: {slot_a.label} vs {slot_b.label}",
        fontsize=13,
        fontweight="bold",
    )

    for i, (ax, metric, va, vb) in enumerate(zip(axes, metrics, values_a, values_b)):
        bars = ax.bar(
            [slot_a.label, slot_b.label], [va, vb], color=["#1565C0", "#C62828"]
        )
        ax.bar_label(bars, fmt="%.1f", padding=3)
        ax.set_title(metric)

    plt.tight_layout()
    path = _chart_path("compare_collection")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


COMPARE_CHART_BUILDERS = {
    "get_overdue_loans": _chart_compare_overdue,
    "get_loan_portfolio_stats": _chart_compare_portfolio,
    "get_collection_efficiency": _chart_compare_collection,
}


# MAIN NODE


def visualize_node(state: AgentState) -> dict:
    """
    Generates matplotlib charts for:
      - Compare flow: reads compare_slot_a/b from ExecutionContext
      - Single result flow: reads last_tool_result from ExecutionContext

    Ownership rules:
      - This node writes ONLY to: chart_paths, error
    """

    execution_context: ExecutionContext = state.get("execution_context")

    if not execution_context:
        return {"error": "visualize_node: no execution_context available"}

    chart_paths = list(state.get("chart_paths") or [])
    chart_path = None

    try:
        # compare flow - both slots present
        if execution_context.compare_slot_a and execution_context.compare_slot_b:
            slot_a = execution_context.compare_slot_a
            slot_b = execution_context.compare_slot_b
            intent = slot_a.intent

            builder = COMPARE_CHART_BUILDERS.get(intent)
            if builder:
                chart_path = builder(slot_a, slot_b)
            else:
                print(
                    f"DEBUG: visualize_node - no compare chart builder for intent: {intent}"
                )

        # single result flow
        elif execution_context.last_tool_result:
            intent = execution_context.last_intent or ""
            result = execution_context.last_tool_result

            builder = CHART_BUILDERS.get(intent)
            if builder:
                chart_path = builder(
                    result, title=f"{intent.replace('_', ' ').title()}"
                )
            else:
                print(f"DEBUG: visualize_node - no chart builder for intent: {intent}")

        if chart_path and chart_path not in chart_paths:
            chart_paths.append(chart_path)

        print("==========================================================")
        print("DEBUG: in visualize_node:")
        print(f"DEBUG: chart_path: {chart_path}")
        print(f"DEBUG: chart_paths: {chart_paths}")
        print("==========================================================")

        return {
            "chart_paths": chart_paths,
            "error": None,
        }

    except Exception as e:
        print("==========================================================")
        print("DEBUG: in visualize_node exception occurred:")
        print(f"DEBUG: error: {e}")
        print("==========================================================")

        return {
            "chart_paths": chart_paths,
            "error": f"visualize_node failed: {str(e)}",
        }
