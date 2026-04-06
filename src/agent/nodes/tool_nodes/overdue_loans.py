from agent.utils import _rows
from psycopg2 import pool as pg_pool
from psycopg2.extras import RealDictCursor
from agent.agent_state import (
    AgentState,
    OverdueLoansParams,
)

from agent.utils import maybe_export

# Tool node to get overdue_loans:
def get_overdue_loans_node(
    state: AgentState,
    db_pool: pg_pool.SimpleConnectionPool
) -> dict:
    """
    Returns all overdue loans with optional filters.
    Buckets results by DPD (Days Past Due):
      1-30  -> Early overdue
      31-60 -> Moderate
      61-90 -> Serious
      90+   -> Critical / NPA territory
    """
    params: OverdueLoansParams = state["tool_params"]
    conn = db_pool.getconn()
 
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
 
        #dynamic WHERE clause based on provided params
        conditions = ["l.status IN ('OVERDUE', 'DEFAULTED', 'NPA')"]
        values     = []
 
        if params.city:
            conditions.append("c.city = %s")
            values.append(params.city)
 
        if params.loan_type:
            conditions.append("l.loan_type = %s")
            values.append(params.loan_type)
 
        if params.min_days_overdue:
            conditions.append("""
                (SELECT MAX(r2.days_past_due)
                 FROM repayments r2
                 WHERE r2.loan_id = l.loan_id
                 AND r2.status IN ('MISSED', 'PARTIAL')) >= %s
            """)
            values.append(params.min_days_overdue)
 
        where_clause = " AND ".join(conditions)
 
        cur.execute(f"""
            SELECT
                l.loan_id,
                l.loan_type,
                l.status,
                l.principal_amount,
                l.outstanding_amount,
                l.emi_amount,
                c.customer_id,
                c.full_name AS customer_name,
                c.phone AS customer_phone,
                c.city,
                c.branch_name,
                c.credit_score,
                -- Only considering currently unpaid EMIs for max DPD.
                -- Excluding historical late payments that were eventually paid.
                MAX(CASE WHEN r.status IN ('MISSED','PARTIAL') THEN r.days_past_due END) AS max_dpd,
                COUNT(CASE WHEN r.status = 'MISSED' THEN 1 END) AS missed_payments
            FROM loans l
            JOIN customers c ON l.customer_id = c.customer_id
            LEFT JOIN repayments r ON l.loan_id  = r.loan_id
            WHERE {where_clause}
            GROUP BY
                -- Every non-aggregated column must appear in the GROUP BY clause.
                l.loan_id, l.loan_type, l.status,
                l.principal_amount, l.outstanding_amount, l.emi_amount,
                c.customer_id, c.full_name, c.phone,
                c.city, c.branch_name, c.credit_score
            ORDER BY max_dpd DESC NULLS LAST
        """, values)
 
        loans = _rows(cur)
 
        #Insight: DPD bucketing:
        buckets = {
            "1_to_30": [],   # Early overdue
            "31_to_60": [],   # Moderate
            "61_to_90": [],   # Serious
            "above_90": [],   # Critical
        }
        for loan in loans:
            dpd = loan.get("max_dpd") or 0
            if dpd <= 30:
                buckets["1_to_30"].append(loan)
            elif dpd <= 60:
                buckets["31_to_60"].append(loan)
            elif dpd <= 90:
                buckets["61_to_90"].append(loan)
            else:
                buckets["above_90"].append(loan)
 
        cur.close()
        tool_result = {
            "total_overdue": len(loans),
            "loans": loans,
            "dpd_buckets": {
                "early_1_to_30_days": len(buckets["1_to_30"]),
                "moderate_31_to_60_days": len(buckets["31_to_60"]),
                "serious_61_to_90_days": len(buckets["61_to_90"]),
                "critical_above_90_days": len(buckets["above_90"]),
            },
        }
        excel_path = maybe_export("get_overdue_loans", tool_result)
        return {
            "tool_result": tool_result,
            "excel_path": excel_path,
            "error": None
        }
 
    except Exception as e:
        return {"tool_result": None, "error": f"get_overdue_loans tool failed: {str(e)}"}
    finally:
        db_pool.putconn(conn)