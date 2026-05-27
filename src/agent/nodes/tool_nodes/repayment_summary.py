from agent.utils import _serialize_value

from agent.agent_state import (
    AgentState,
    RepaymentSummaryParams,
)

from langgraph.runtime import Runtime
from agent.runtime_context import AppContext

from agent.utils import export_csv
from datetime import datetime, timezone

BEHAVIOUR_MAP = {
    "GOOD": {
        "PAID",
        "PAID_PREVIOUS_DUES",
        "PAID_FEES_PENDING",
        "RECOVERY_PAYMENT",
        "FEES_ONLY_PAYMENT",
    },
    "LATE": {
        "PAID_LATE",
        "PARTIAL",
    },
    "BAD": {
        "MISSED",
        "OVERDUE",
        "DEFAULTED",
    },
    "PARTIAL_RECOVERY": {
        "PARTIAL_RECOVERY",
    },
    "UPCOMING": {
        "UPCOMING",
    },
}


def _classify_status(status: str) -> str:
    for group, values in BEHAVIOUR_MAP.items():
        if status in values:
            return group
    return "UNKNOWN"


def _bad_score(rows):
    score = 0
    for r in rows:
        s = _classify_status(r["status"])
        if s == "BAD":
            score += 2
        elif s == "LATE":
            score += 1
        elif s == "GOOD":
            score += 0
        else:
            score += 0
    return score


# Tool node to get repayment_summary:
def get_repayment_summary_node(
    state: AgentState,
    runtime: Runtime[AppContext],
) -> dict:
    """
    Returns repayment history for a customer: all loans or a specific loan.
    Includes trend analysis — is behaviour improving or worsening?
    """
    params: RepaymentSummaryParams = state.get("tool_params")
    if not isinstance(params, RepaymentSummaryParams):
        return {
            "tool_result": None,
            "retrieved_data": state.get("retrieved_data", {}),
            "execution_context": state.get("execution_context", {}),
            "error": "Required parameters to process the repayment summary are either missing, invalid or could not be extracted.",
        }

    try:
        db_client = runtime.context.db

        with db_client.conn() as conn:
            with db_client.cursor(conn, dict_cursor=True) as cur:

                # Validating whether the customer exists:
                cur.execute(
                    "SELECT full_name FROM customers WHERE customer_id = %s",
                    (params.customer_id,),
                )

                customer = cur.fetchone()
                if not customer:
                    result = {
                        "customer_name": None,
                        # "repayments": [],
                        "summary": {},
                        "message": f"Customer ID : {params.customer_id} not found",
                    }

                    execution_context = {
                        **state.get("execution_context", {}),
                        "last_tool": "get_repayment_summary",
                        "active_customer_id": params.customer_id,
                        "last_result_empty": True,
                    }

                    cache_key = f"repayment_summary:" f"{params.customer_id}"

                    retrieved_data = {
                        **state.get("retrieved_data", {}),
                        cache_key: result,
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                    }

                    return {
                        "tool_result": result,
                        "retrieved_data": retrieved_data,
                        "execution_context": execution_context,
                        "error": None,
                    }

                # Building query filter:
                query_values = [params.customer_id]
                loan_filter = ""

                if params.loan_id:
                    loan_filter = "AND l.loan_id = %s"
                    query_values.append(params.loan_id)

                # Fetch Repayment records
                cur.execute(
                    f"""
                    SELECT
                        r.repayment_id,
                        r.loan_id,
                        l.loan_type,
                        r.due_date,
                        r.paid_date,
                        r.amount_due,
                        r.amount_paid,
                        r.dpd_days,
                        r.status
                    FROM repayments r
                    JOIN loans l ON r.loan_id = l.loan_id --Inner Join
                    WHERE l.customer_id = %s {loan_filter}
                    ORDER BY r.due_date DESC
                """,
                    query_values,
                )

                rows = cur.fetchall()

        repayments = [{k: _serialize_value(v) for k, v in row.items()} for row in rows]

        # payment behaviour summary
        past = [r for r in repayments if r["status"] != "UPCOMING"]
        total = len(past)

        # EMPTY RESULT HANDLING
        if total == 0:
            result = {
                "customer_name": customer["full_name"],
                **({"loan_id": params.loan_id} if params.loan_id else {}),
                # "repayments": [],
                "summary": {},
                "message": (
                    f"No past payment records found for Customer ID: {params.customer_id}"
                    f"{f' and Loan ID: {params.loan_id}' if params.loan_id else ''}"
                ),
                "export_path": None,
                "dataset_id": None,
            }

            execution_context = {
                **state.get("execution_context", {}),
                "last_tool": "get_repayment_summary",
                "current_customer_id": params.customer_id,
                "last_result_empty": True,
                **({"active_loan_id": params.loan_id} if params.loan_id else {}),
                "export_path": None,
                "dataset_id": None,
            }

            cache_key = (
                f"repayment_summary:"
                f"{params.customer_id}:"
                f"{params.loan_id or 'all'}"
            )

            retrieved_data = {
                **state.get("retrieved_data", {}),
                cache_key: result,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }

            return {
                "tool_result": result,
                "retrieved_data": retrieved_data,
                "execution_context": execution_context,
                "error": None,
            }

        else:
            good = sum(1 for r in past if _classify_status(r["status"]) == "GOOD")
            late = sum(1 for r in past if _classify_status(r["status"]) == "LATE")
            bad = sum(1 for r in past if _classify_status(r["status"]) == "BAD")
            partial_recovery = sum(
                1 for r in past if _classify_status(r["status"]) == "PARTIAL_RECOVERY"
            )
            avg_dpd = (
                round(sum(r["dpd_days"] or 0 for r in past) / total, 1) if total else 0
            )

            # For payment behaviour — compare last 3 months vs previous 3 months
            # Sort by due_date ascending for trend analysis
            sorted_past = sorted(past, key=lambda r: r["due_date"])
            recent = sorted_past[-3:] if len(sorted_past) >= 3 else sorted_past
            earlier = sorted_past[-6:-3] if len(sorted_past) >= 6 else []

            if earlier:
                recent_score = _bad_score(recent)
                earlier_score = _bad_score(earlier)

                if recent_score > earlier_score:
                    trend = "DETERIORATING"
                elif recent_score < earlier_score:
                    trend = "IMPROVING"
                else:
                    trend = "STABLE"
            else:
                trend = "INSUFFICIENT_DATA"

            summary = {
                "total_past_emis": total,
                "good_payments": good,
                "late_payments": late,
                "bad_payments": bad,
                "partial_recovery": partial_recovery,
                "avg_dpd_days": avg_dpd,
                "payment_trend": trend,
            }

        dataset_id, export_path = export_csv(
            prefix="repayment_summary", rows=repayments
        )

        result = {
            "customer_name": customer["full_name"],
            **({"loan_id": params.loan_id} if params.loan_id else {}),
            # "repayments": repayments,
            "summary": summary,
            "total_repayment_records": len(repayments),
            "export_path": export_path,
            "dataset_id": dataset_id,
        }

        # EXECUTION CONTEXT UPDATE
        execution_context = {
            **state.get("execution_context", {}),
            "last_tool": "get_repayment_summary",
            "current_customer_id": params.customer_id,
            **({"active_loan_id": params.loan_id} if params.loan_id else {}),
            "export_path": export_path,
            "dataset_id": dataset_id,
        }

        # RETRIEVED DATA CACHE
        cache_key = (
            f"repayment_summary:" f"{params.customer_id}:" f"{params.loan_id or 'all'}"
        )

        retrieved_data = {
            **state.get("retrieved_data", {}),
            cache_key: result,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

        return {
            "tool_result": result,
            "retrieved_data": retrieved_data,
            "execution_context": execution_context,
            "error": None,
        }

    except Exception as e:
        return {
            "tool_result": None,
            "retrieved_data": state.get("retrieved_data", {}),
            "execution_context": state.get("execution_context", {}),
            "error": f",get_repayment_summary tool failed: {str(e)}",
        }
