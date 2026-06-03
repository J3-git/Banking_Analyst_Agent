from agent.utils import _serialize_value
from agent.agent_state import (
    AgentState,
    CollectionEfficiencyParams,
    RetrievedDataEntry,
)
from langgraph.runtime import Runtime
from agent.runtime_context import AppContext


def get_collection_efficiency_node(
    state: AgentState,
    runtime: Runtime[AppContext],
) -> dict:
    """
    Returns how effectively overdue loans are being recovered.
    Shows:
      - How many overdue EMIs were eventually paid vs still missed
      - Recovery rate overall and by loan_type / city
      - Month over month trend

    Ownership rules:
      - This node writes ONLY to: tool_result, tool_results, retrieved_data, error
    """

    params: CollectionEfficiencyParams = state.get("tool_params")
    if not isinstance(params, CollectionEfficiencyParams):
        return {
            "error": "Required parameters to process the collection efficiency are either missing, invalid or could not be extracted.",
        }

    cache_key = (
        f"collection_efficiency:"
        f"{params.city if params.city else 'City.all'}:"
        f"{params.loan_type if params.loan_type else 'LoanType.all'}:"
        f"{params.period if params.period else 'Period.full'}"
    )

    try:
        db_client = runtime.context.db

        with db_client.conn() as conn:
            with db_client.cursor(conn, dict_cursor=True) as cur:

                period_map = {
                    "this_month": "DATE_TRUNC('month', CURRENT_DATE)",
                    "last_month": "DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')",
                    "this_quarter": "DATE_TRUNC('quarter', CURRENT_DATE)",
                    "this_year": "DATE_TRUNC('year', CURRENT_DATE)",
                }

                period_filter = ""
                values = []

                if params.period and params.period.value in period_map:
                    period_filter = (
                        f"AND r.due_date >= {period_map[params.period.value]}"
                    )

                city_filter = ""
                loan_type_filter = ""

                if params.city:
                    city_filter = "AND c.city = %s"
                    values.append(params.city.value)

                if params.loan_type:
                    loan_type_filter = "AND l.loan_type = %s"
                    values.append(params.loan_type.value)

                # overall recovery stats
                cur.execute(
                    f"""
                    SELECT
                        COUNT(*) AS total_emis_due,
                        ROUND(
                            100.0 *
                            SUM(COALESCE(r.amount_paid, 0))
                            /
                            NULLIF(SUM(COALESCE(r.amount_due, 0)), 0),
                            2
                        ) AS recovery_rate_pct,
                        SUM(r.amount_due) AS total_amount_due,
                        SUM(r.amount_paid) AS total_amount_collected,
                        SUM(CASE WHEN r.status = 'MISSED' THEN 1 ELSE 0 END) AS still_missed,
                        SUM(CASE WHEN r.status = 'PARTIAL' THEN 1 ELSE 0 END) AS partial
                    FROM repayments r
                    JOIN loans l ON r.loan_id = l.loan_id
                    JOIN customers c ON l.customer_id = c.customer_id
                    WHERE r.status != 'UPCOMING'
                    {period_filter}
                    {city_filter}
                    {loan_type_filter}
                    """,
                    values,
                )

                overall_row = cur.fetchone()
                overall = {k: _serialize_value(v) for k, v in overall_row.items()}
                total_emis = overall.get("total_emis_due", 0) or 0

                # empty result
                if total_emis == 0:
                    result = {
                        "overall": overall,
                        "monthly_trend": [],
                        "trend": "NO DATA AVAILABLE",
                        "message": "No repayment records found.",
                    }

                    entry = RetrievedDataEntry(
                        intent="get_collection_efficiency",
                        params=params.model_dump(exclude_none=True),
                        result=result,
                    )

                    retrieved_data = {
                        **state.get("retrieved_data", {}),
                        cache_key: entry.model_dump(),
                    }

                    return {
                        "tool_result": result,
                        "tool_results": [result],
                        "retrieved_data": retrieved_data,
                        "error": None,
                    }

                # monthly trend - last 6 months
                cur.execute(
                    f"""
                    SELECT
                        TO_CHAR(DATE_TRUNC('month', r.due_date), 'YYYY-MM') AS month,
                        COUNT(*) AS total_emis,
                        ROUND(
                            100.0 *
                            SUM(COALESCE(r.amount_paid, 0))
                            /
                            NULLIF(SUM(COALESCE(r.amount_due, 0)), 0),
                            2
                        ) AS recovery_rate_pct
                    FROM repayments r
                    JOIN loans l ON r.loan_id = l.loan_id
                    JOIN customers c ON l.customer_id = c.customer_id
                    WHERE r.status != 'UPCOMING'
                    AND r.due_date >= CURRENT_DATE - INTERVAL '6 months'
                    {city_filter}
                    {loan_type_filter}
                    GROUP BY DATE_TRUNC('month', r.due_date)
                    ORDER BY month DESC
                    """,
                    values,
                )

                monthly_trend_rows = cur.fetchall()
                monthly_trend = [
                    {k: _serialize_value(v) for k, v in row.items()}
                    for row in monthly_trend_rows
                ]

        # trend insight
        if len(monthly_trend) >= 2:
            latest = float(monthly_trend[0].get("recovery_rate_pct") or 0)
            previous = float(monthly_trend[1].get("recovery_rate_pct") or 0)
            diff = round(latest - previous, 2)

            if diff > 2:
                trend = f"IMPROVING (+{diff}%)"
            elif diff < -2:
                trend = f"DECLINING ({diff}%)"
            else:
                trend = "STABLE"
        else:
            trend = "INSUFFICIENT_DATA"

        result = {
            "overall": overall,
            "monthly_trend": monthly_trend,
            "trend": trend,
        }

        entry = RetrievedDataEntry(
            intent="get_collection_efficiency",
            params=params.model_dump(exclude_none=True),
            result=result,
        )

        retrieved_data = {
            **state.get("retrieved_data", {}),
            cache_key: entry.model_dump(),
        }

        print("==========================================================")
        print("DEBUG: in get_collection_efficiency_node:")
        print(f"DEBUG: cache_key: {cache_key}")
        print(f"DEBUG: trend: {trend}")
        print("==========================================================")

        return {
            "tool_result": result,
            "tool_results": [result],
            "retrieved_data": retrieved_data,
            "error": None,
        }

    except Exception as e:
        print("==========================================================")
        print("DEBUG: in get_collection_efficiency_node exception occurred:")
        print(f"DEBUG: error: {e}")
        print("==========================================================")

        return {
            "error": f"get_collection_efficiency tool failed: {str(e)}",
        }
