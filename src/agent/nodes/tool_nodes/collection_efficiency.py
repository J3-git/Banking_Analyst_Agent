from agent.utils import _rows
from psycopg2 import pool as pg_pool
from psycopg2.extras import RealDictCursor
from agent.agent_state import (
    AgentState,
    CollectionEfficiencyParams,
)

# Tool node to get collection_efficiency:
def get_collection_efficiency_node(
    state:   AgentState,
    db_pool: pg_pool.SimpleConnectionPool
) -> dict:
    """
    Returns how effectively overdue loans are being recovered.
    Shows:
      - How many overdue EMIs were eventually paid vs still missed
      - Recovery rate overall and by loan_type / city
      - Month over month trend
    """
    params: CollectionEfficiencyParams = state["tool_params"]
    conn = db_pool.getconn()
 
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
 
        #Period filter:
        period_filter = ""
        period_values = []
 
        period_map = {
            "this_month": "DATE_TRUNC('month', CURRENT_DATE)", #Returns first day of this month
            "last_month": "DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')", #Returns first day of last month
            "this_quarter": "DATE_TRUNC('quarter', CURRENT_DATE)", #Returns first day of last quarter
            "this_year": "DATE_TRUNC('year', CURRENT_DATE)", #Returns first day of this year
        }
 
        if params.period and params.period in period_map:
            period_filter = f"AND r.due_date >= {period_map[params.period]}"
 
        city_filter = "AND c.city = %s" if params.city else ""
        loan_type_filter = "AND l.loan_type = %s" if params.loan_type else ""
 
        if params.city:
            period_values.append(params.city)
        if params.loan_type:
            period_values.append(params.loan_type)
 
        # Overall recovery stats
        cur.execute(f"""
            SELECT
                COUNT(*) AS total_emis_due,
                SUM(CASE WHEN r.status IN ('PAID_ONTIME','PAID_LATE') THEN 1 ELSE 0 END) AS recovered,
                SUM(CASE WHEN r.status = 'MISSED' THEN 1 ELSE 0 END) AS still_missed,
                SUM(CASE WHEN r.status = 'PARTIAL' THEN 1 ELSE 0 END) AS partial,
                ROUND(
                    100.0 * SUM(CASE WHEN r.status IN ('PAID_ONTIME','PAID_LATE') THEN 1 ELSE 0 END)
                    / NULLIF(COUNT(*), 0), 2           --if somehow total EMIs is zero this returns NULL, avoiding division by zero error.                          
                ) AS recovery_rate_pct,
                SUM(r.amount_due) AS total_amount_due,
                SUM(r.amount_paid) AS total_amount_collected
            FROM repayments r
            JOIN loans l ON r.loan_id = l.loan_id
            JOIN customers c ON l.customer_id = c.customer_id
            WHERE r.status != 'UPCOMING'
            {period_filter}
            {city_filter}
            {loan_type_filter}
        """, period_values)
 
        overall = _rows(cur)[0]
 
        #Monthly trend — last 6 months
        cur.execute(f"""
            SELECT
                TO_CHAR(DATE_TRUNC('month', r.due_date), 'YYYY-MM') AS month,
                COUNT(*) AS total_emis,
                SUM(CASE WHEN r.status IN ('PAID_ONTIME','PAID_LATE') THEN 1 ELSE 0 END) AS recovered,
                ROUND(
                    100.0 * SUM(CASE WHEN r.status IN ('PAID_ONTIME','PAID_LATE') THEN 1 ELSE 0 END)
                    / NULLIF(COUNT(*), 0), 2
                ) AS recovery_rate_pct
            FROM repayments r
            JOIN loans l ON r.loan_id = l.loan_id
            JOIN customers c ON l.customer_id = c.customer_id
            WHERE r.status != 'UPCOMING'
            AND r.due_date >= CURRENT_DATE - INTERVAL '6 months'
            {city_filter}
            {loan_type_filter}
            GROUP BY DATE_TRUNC('month', r.due_date) --groups by month
            ORDER BY month DESC
        """, period_values)
 
        monthly_trend = _rows(cur)
 
        #Build insight — is recovery improving or declining?
        if len(monthly_trend) >= 2:
            latest = monthly_trend[0].get("recovery_rate_pct") or 0   # most recent month
            previous = monthly_trend[1].get("recovery_rate_pct") or 0 # previous month
            diff = round(float(latest) - float(previous), 2)
 
            if   diff > 2:
                trend = f"IMPROVING (+{diff}% vs last month)" 
            elif diff < -2:
                trend = f"DECLINING ({diff}% vs last month)"
            else:
                trend = "STABLE"   #small fluctuations
        else:
            trend = "INSUFFICIENT_DATA"
 
        cur.close()
        return {
            "tool_result": {
                "overall": overall,
                "monthly_trend": monthly_trend,
                "trend": trend,
            },
            "excel_path": None,
            "error": None
        }
 
    except Exception as e:
        return {"tool_result": None,
                "excel_path": None,
                "error": f"get_collection_efficiency tool failed: {str(e)}"}
    finally:
        db_pool.putconn(conn)