from agent.utils import _rows
from psycopg2 import pool as pg_pool
from psycopg2.extras import RealDictCursor
from agent.agent_state import (
    AgentState,
    LoanPortfolioStatsParams,
)

# Tool node to get ovloan_portfolio_stats:
def get_loan_portfolio_stats_node(
    state: AgentState,
    db_pool: pg_pool.SimpleConnectionPool
) -> dict:
    """
    Returns aggregate statistics across all loans.
    Can group by loan_type, city, or status.
    Includes default rate and outstanding amount per group.
    """
    params: LoanPortfolioStatsParams = state["tool_params"]
    conn = db_pool.getconn()
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
 
        #Overall portfolio summary:
        cur.execute("""
            SELECT
                COUNT(*) AS total_loans,
                SUM(principal_amount) AS total_disbursed,
                SUM(outstanding_amount) AS total_outstanding,
                SUM(CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END) AS active,
                SUM(CASE WHEN status = 'OVERDUE' THEN 1 ELSE 0 END) AS overdue,
                SUM(CASE WHEN status = 'DEFAULTED' THEN 1 ELSE 0 END) AS defaulted,
                SUM(CASE WHEN status = 'NPA' THEN 1 ELSE 0 END) AS npa,
                SUM(CASE WHEN status = 'CLOSED' THEN 1 ELSE 0 END) AS closed,
                ROUND(
                    100.0 * SUM(CASE WHEN status IN ('DEFAULTED','NPA') THEN 1 ELSE 0 END)
                    / NULLIF(COUNT(*), 0), 2
                ) AS default_rate_pct
            FROM loans l
            JOIN customers c ON l.customer_id = c.customer_id
            WHERE (%s IS NULL OR c.city = %s)    --If given city, filter by it. If provided NULL, don't filter at all."
            AND   (%s IS NULL OR l.loan_type = %s)
        """, (params.city, params.city, params.loan_type, params.loan_type))
 
        overall = _rows(cur)[0]
        
        #Breakdown by group_by dimension
        breakdown = []
        group_col = params.group_by or "loan_type"   # default group by loan_type
 
        if group_col == "city":
            group_expr = "c.city"
        elif group_col == "status":
            group_expr = "l.status"
        else:
            group_expr = "l.loan_type"
 
        cur.execute(f"""
            SELECT
                {group_expr} AS group_name,
                COUNT(*) AS total_loans,
                SUM(l.principal_amount) AS total_disbursed,
                SUM(l.outstanding_amount) AS total_outstanding,
                ROUND(
                    100.0 * SUM(CASE WHEN l.status IN ('DEFAULTED','NPA') THEN 1 ELSE 0 END)
                    / NULLIF(COUNT(*), 0), 2
                ) AS default_rate_pct
            FROM loans l
            JOIN customers c ON l.customer_id = c.customer_id
            WHERE (%s IS NULL OR c.city = %s)
            AND (%s IS NULL OR l.loan_type = %s)
            GROUP BY {group_expr}
            ORDER BY default_rate_pct DESC NULLS LAST
        """, (params.city, params.city, params.loan_type, params.loan_type))
 
        breakdown = _rows(cur)
 
        #Building insight — flag high default rate groups:
        for group in breakdown:
            rate = group.get("default_rate_pct") or 0
            if   rate >= 15:
                group["risk_flag"] = "HIGH default rate"
            elif rate >= 8:
                group["risk_flag"] = "MODERATE default rate"
            else:
                group["risk_flag"] = "Healthy"
        
        cur.close()
        return {
            "tool_result": {
                "overall": overall,
                "grouped_by": group_col,
                "breakdown": breakdown,
            },
            "excel_path": None,
            "error": None
        }
 
    except Exception as e:
        return {"tool_result": None,
                "excel_path": None,
                "error": f"get_loan_portfolio_stats tool failed: {str(e)}"}
    finally:
        db_pool.putconn(conn)