from agent.utils import _rows
from psycopg2 import pool as pg_pool
from psycopg2.extras import RealDictCursor
from agent.agent_state import (
    AgentState,
    RepaymentSummaryParams,
)

from agent.utils import maybe_export

# Tool node to get repayment_summary:
def get_repayment_summary_node(
    state: AgentState,
    db_pool: pg_pool.SimpleConnectionPool
) -> dict:
    """
    Returns repayment history for a customer: all loans or a specific loan.
    Includes trend analysis — is behaviour improving or worsening?
    """
    params: RepaymentSummaryParams = state["tool_params"]
    conn = db_pool.getconn()
 
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
 
        #Validating whether the customer exists:
        cur.execute(
            "SELECT full_name FROM customers WHERE customer_id = %s",
            (params.customer_id,)
        )

        customer = cur.fetchone()
        if not customer:
            return {
                "tool_result": None,
                "error": f"Customer ID {params.customer_id} not found"
            }
 
        #Building loan filter:
        loan_values = [params.customer_id]
        loan_filter = "AND l.loan_id = %s" if params.loan_id else ""
        if params.loan_id:
            loan_values.append(params.loan_id)
 
        #Repayment records
        cur.execute(f"""
            SELECT
                r.repayment_id,
                r.loan_id,
                l.loan_type,
                r.due_date,
                r.paid_date,
                r.amount_due,
                r.amount_paid,
                r.days_past_due,
                r.status
            FROM repayments r
            JOIN loans l ON r.loan_id = l.loan_id --Inner Join
            WHERE l.customer_id = %s {loan_filter}
            ORDER BY r.due_date DESC
        """, loan_values)
 
        repayments = _rows(cur)
 
        #payment behaviour summary
        past = [r for r in repayments if r["status"] != "UPCOMING"]
        total = len(past)
 
        if total == 0:
            summary = {"message": "No past repayment records found"}
        else:
            on_time = sum(1 for r in past if r["status"] == "PAID_ONTIME")
            late = sum(1 for r in past if r["status"] == "PAID_LATE")
            missed = sum(1 for r in past if r["status"] == "MISSED")
            partial = sum(1 for r in past if r["status"] == "PARTIAL")
            avg_dpd = sum(r["days_past_due"] for r in past) / total
 
            on_time_pct = round(on_time / total * 100, 1)
 
            # For payment behaviour — compare last 3 months vs previous 3 months
            # Sort by due_date ascending for trend analysis
            sorted_past = sorted(past, key=lambda r: r["due_date"])
            recent = sorted_past[-3:] if len(sorted_past) >= 3 else sorted_past
            earlier = sorted_past[-6:-3] if len(sorted_past) >= 6 else []
 
            recent_missed = sum(1 for r in recent if r["status"] == "MISSED")
            earlier_missed = sum(1 for r in earlier if r["status"] == "MISSED")
 
            if earlier:
                if recent_missed > earlier_missed:
                    trend = "DETERIORATING"
                elif recent_missed < earlier_missed:
                    trend = "IMPROVING"
                else:
                    trend = "STABLE"
            else:
                trend = "INSUFFICIENT_DATA"
 
            summary = {
                "total_past_emis": total,
                "paid_on_time": on_time,
                "paid_late": late,
                "missed": missed,
                "partial": partial,
                "on_time_rate_pct": on_time_pct,
                "avg_days_past_due": round(avg_dpd, 1),
                "payment_trend": trend,
            }
 
        cur.close()
        tool_result = {
            "customer_name": customer["full_name"],
            "repayments": repayments,
            "summary": summary,
        }
        excel_path = maybe_export("get_repayment_summary", tool_result)
        return {
            "tool_result": tool_result,
            "excel_path": excel_path,
            "error": None
        }
 
    except Exception as e:
        return {
            "tool_result": None,
            "error": f"get_repayment_summary tool failed: {str(e)}"
        }
    finally:
        db_pool.putconn(conn)