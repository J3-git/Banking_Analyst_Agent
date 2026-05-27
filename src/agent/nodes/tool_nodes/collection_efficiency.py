from agent.utils import _serialize_value

from agent.agent_state import (
    AgentState,
    CollectionEfficiencyParams,
)

from langgraph.runtime import Runtime
from agent.runtime_context import AppContext

from datetime import datetime, timezone


# Tool node to get collection_efficiency:
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
    """
    params: CollectionEfficiencyParams = state.get("tool_params")
    if not isinstance(params, CollectionEfficiencyParams):
        return {
            "tool_result": None,
            "retrieved_data": state.get("retrieved_data", {}),
            "execution_context": state.get("execution_context", {}),
            "error": "Required parameters to process the collection efficiency are either missing, invalid or could not be extracted.",
        }

    try:
        db_client = runtime.context.db

        with db_client.conn() as conn:
            with db_client.cursor(conn, dict_cursor=True) as cur:

                # Period filter:
                period_map = {
                    "this_month": "DATE_TRUNC('month', CURRENT_DATE)",
                    "last_month": "DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')",
                    "this_quarter": "DATE_TRUNC('quarter', CURRENT_DATE)",
                    "this_year": "DATE_TRUNC('year', CURRENT_DATE)",
                }

                period_filter = ""
                values = []

                if params.period and params.period in period_map:
                    period_filter = "AND r.due_date >= " f"{period_map[params.period]}"

                city_filter = ""
                loan_type_filter = ""

                if params.city:
                    city_filter = "AND c.city = %s"
                    values.append(params.city)

                if params.loan_type:
                    loan_type_filter = "AND l.loan_type = %s"
                    values.append(params.loan_type)

                # =========================
                # OVERALL QUERY
                # =========================

                cur.execute(
                    f"""
                    SELECT
                        COUNT(*) AS total_emis_due,

                        ROUND(
                            100.0 *
                            SUM(COALESCE(r.amount_paid, 0))
                            /
                            NULLIF(
                                SUM(COALESCE(r.amount_due, 0)),
                                0
                            ),
                            2
                        ) AS recovery_rate_pct,

                        SUM(r.amount_due) AS total_amount_due,
                        SUM(r.amount_paid) AS total_amount_collected,

                        SUM(
                            CASE WHEN r.status = 'MISSED'
                            THEN 1 ELSE 0 END
                        ) AS still_missed,

                        SUM(
                            CASE WHEN r.status = 'PARTIAL'
                            THEN 1 ELSE 0 END
                        ) AS partial

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

                # EMPTY DATA HANDLING
                if total_emis == 0:

                    result = {
                        "overall": overall,
                        "monthly_trend": [],
                        "trend": "NO DATA AVAILABLE",
                        "message": "No repayment records found.",
                    }

                    execution_context = {
                        **state.get("execution_context", {}),
                        "last_tool": "get_collection_efficiency",
                        "last_result_empty": True,
                        **({"active_city": params.city} if params.city else {}),
                        **(
                            {"active_loan_type": params.loan_type}
                            if params.loan_type
                            else {}
                        ),
                        **({"selected_period": params.period} if params.period else {}),
                    }

                    cache_key = (
                        f"collection_efficiency:"
                        f"{params.city or 'all'}:"
                        f"{params.loan_type or 'all'}:"
                        f"{params.period or 'full'}"
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

                # Monthly trend — last 6 months
                cur.execute(
                    f"""
                    SELECT
                        TO_CHAR(
                            DATE_TRUNC('month', r.due_date),
                            'YYYY-MM'
                        ) AS month,

                        COUNT(*) AS total_emis,

                        ROUND(
                            100.0 *
                            SUM(
                                COALESCE(r.amount_paid, 0)
                            )
                            /
                            NULLIF(
                                SUM(
                                    COALESCE(r.amount_due, 0)
                                ),
                                0
                            ),
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

        # Build insight — is recovery improving or declining?
        if len(monthly_trend) >= 2:

            latest = monthly_trend[0].get("recovery_rate_pct") or 0

            previous = monthly_trend[1].get("recovery_rate_pct") or 0

            diff = round(
                float(latest) - float(previous),
                2,
            )

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

        execution_context = state.get("execution_context", {})
        execution_context.update(
            {
                "last_tool": "get_collection_efficiency",
                "overall": overall,
                "monthly_trend": monthly_trend,
                "trend": trend,
            }
        )

        execution_context = {
            **state.get("execution_context", {}),
            "last_tool": "get_collection_efficiency",
            "trend": trend,
            **({"active_city": params.city} if params.city else {}),
            **({"active_loan_type": params.loan_type} if params.loan_type else {}),
            **({"selected_period": params.period} if params.period else {}),
        }

        cache_key = (
            f"collection_efficiency:"
            f"{params.city or 'all'}:"
            f"{params.loan_type or 'all'}:"
            f"{params.period or 'full'}"
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
            "error": f"get_collection_efficiency tool failed: {str(e)}",
        }
