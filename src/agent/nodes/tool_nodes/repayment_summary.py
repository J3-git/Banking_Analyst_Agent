from agent.utils import _rows
from psycopg2 import pool as pg_pool
from psycopg2.extras import RealDictCursor
from agent.agent_state import (
    AgentState,
    RepaymentSummaryParams,
)

from agent.utils import maybe_export

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
    state: AgentState, db_pool: pg_pool.SimpleConnectionPool
) -> dict:
    """
    Returns repayment history for a customer: all loans or a specific loan.
    Includes trend analysis — is behaviour improving or worsening?
    """
    params: RepaymentSummaryParams = state["tool_params"]
    conn = db_pool.getconn()

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Validating whether the customer exists:
        cur.execute(
            "SELECT full_name FROM customers WHERE customer_id = %s",
            (params.customer_id,),
        )

        customer = cur.fetchone()
        if not customer:
            return {
                "tool_result": None,
                "error": f"Customer ID {params.customer_id} not found",
            }

        # Building loan filter:
        loan_values = [params.customer_id]
        loan_filter = "AND l.loan_id = %s" if params.loan_id else ""
        if params.loan_id:
            loan_values.append(params.loan_id)

        # Repayment records
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
            loan_values,
        )

        repayments = _rows(cur)

        # payment behaviour summary
        past = [r for r in repayments if r["status"] != "UPCOMING"]
        total = len(past)

        if total == 0:
            summary = {"message": "No past repayment records found"}
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

        cur.close()
        tool_result = {
            "customer_name": customer["full_name"],
            "repayments": repayments,
            "summary": summary,
        }
        excel_path = maybe_export("get_repayment_summary", tool_result)
        return {"tool_result": tool_result, "excel_path": excel_path, "error": None}

    except Exception as e:
        return {
            "tool_result": None,
            "error": f"get_repayment_summary tool failed: {str(e)}",
        }
    finally:
        db_pool.putconn(conn)
