from agent.utils import _serialize_value
from agent.agent_state import (
    AgentState,
    LoanPortfolioStatsParams,
)

from langgraph.runtime import Runtime
from agent.runtime_context import AppContext

from datetime import datetime, timezone

ALLOWED_GROUP_EXPRESSIONS = {
    "city": "c.city",
    "status": "l.status",
    "loan_type": "l.loan_type",
}


# Tool node to get ovloan_portfolio_stats:
def get_loan_portfolio_stats_node(
    state: AgentState,
    runtime: Runtime[AppContext],
) -> dict:
    """
    Returns aggregate portfolio analytics.

    Supports:
    - grouping by city / loan_type / status
    - filtering by city / loan_type
    - default rate analytics
    - risk flagging
    """

    params: LoanPortfolioStatsParams = state.get("tool_params")

    if not isinstance(params, LoanPortfolioStatsParams):
        return {
            "tool_result": None,
            "retrieved_data": state.get("retrieved_data", {}),
            "execution_context": state.get("execution_context", {}),
            "error": "Required parameters to retrieve portfolio statistics are either missing, invalid or could not be extracted.",
        }

    try:
        db_client = runtime.context.db

        with db_client.conn() as conn:
            with db_client.cursor(conn, dict_cursor=True) as cur:

                # Overall portfolio summary:
                # Overall portfolio summary
                cur.execute(
                    """
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
                            100.0 * SUM(
                                CASE
                                    WHEN status IN ('DEFAULTED', 'NPA')
                                    THEN 1
                                    ELSE 0
                                END
                            ) / NULLIF(COUNT(*), 0),
                            2
                        ) AS default_rate_pct
                    FROM loans l
                    JOIN customers c
                        ON l.customer_id = c.customer_id
                    WHERE (%s IS NULL OR c.city = %s)  --If given city, filter by it. If provided NULL, don't filter at all."
                    AND (%s IS NULL OR l.loan_type = %s)
                    """,
                    (
                        params.city,
                        params.city,
                        params.loan_type,
                        params.loan_type,
                    ),
                )

                overall_row = cur.fetchone()

                overall = {k: _serialize_value(v) for k, v in overall_row.items()}

                # EMPTY DATA HANDLING
                if not overall or (overall.get("total_loans") or 0) == 0:

                    group_col = params.group_by or "loan_type"

                    result = {
                        "overall": {
                            "total_loans": 0,
                            "total_disbursed": 0,
                            "total_outstanding": 0,
                            "default_rate_pct": None,
                        },
                        "grouped_by": group_col,
                        "breakdown": [],
                        "message": "No loan portfolio data found for given filters.",
                    }

                    # update context
                    execution_context = {
                        **state.get("execution_context", {}),
                        "last_tool": "get_loan_portfolio_stats",
                        "active_group_by": group_col,
                        "last_result_empty": True,
                        **({"active_city": params.city} if params.city else {}),
                        **(
                            {"active_loan_type": params.loan_type}
                            if params.loan_type
                            else {}
                        ),
                    }

                    cache_key = (
                        f"portfolio_stats:"
                        f"{group_col}:"
                        f"{params.city or 'all'}:"
                        f"{params.loan_type or 'all'}"
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

                # GROUP BY CONFIGURATION
                group_col = (
                    params.group_by
                    if params.group_by in ALLOWED_GROUP_EXPRESSIONS
                    else "loan_type"
                )
                group_expr = ALLOWED_GROUP_EXPRESSIONS[group_col]

                # BREAKDOWN ANALYTICS
                cur.execute(
                    f"""
                    SELECT
                        {group_expr} AS group_name,
                        COUNT(*) AS total_loans,
                        SUM(l.principal_amount) AS total_disbursed,
                        SUM(l.outstanding_amount) AS total_outstanding,
                        ROUND(
                            100.0 * SUM(
                                CASE
                                    WHEN l.status IN ('DEFAULTED', 'NPA')
                                    THEN 1
                                    ELSE 0
                                END
                            ) / NULLIF(COUNT(*), 0),
                            2
                        ) AS default_rate_pct
                    FROM loans l
                    JOIN customers c
                        ON l.customer_id = c.customer_id
                    WHERE (%s IS NULL OR c.city = %s)
                    AND (%s IS NULL OR l.loan_type = %s)
                    GROUP BY {group_expr}
                    ORDER BY default_rate_pct DESC NULLS LAST
                    """,
                    (
                        params.city,
                        params.city,
                        params.loan_type,
                        params.loan_type,
                    ),
                )

                breakdown = []

                for row in cur.fetchall():

                    group = {k: _serialize_value(v) for k, v in row.items()}

                    rate = group.get("default_rate_pct") or 0

                    if rate >= 15:
                        group["risk_flag"] = "HIGH default rate"

                    elif rate >= 8:
                        group["risk_flag"] = "MODERATE default rate"

                    else:
                        group["risk_flag"] = "Healthy"

                    breakdown.append(group)

        # FINAL RESULT
        result = {
            "overall": overall,
            "grouped_by": group_col,
            "breakdown": breakdown,
        }

        # EXECUTION CONTEXT UPDATE
        execution_context = {
            **state.get("execution_context", {}),
            "last_tool": "get_loan_portfolio_stats",
            "active_group_by": group_col,
            **({"active_city": params.city} if params.city else {}),
            **({"active_loan_type": params.loan_type} if params.loan_type else {}),
        }

        # RETRIEVED DATA CACHE
        cache_key = (
            f"portfolio_stats:"
            f"{group_col}:"
            f"{params.city or 'all'}:"
            f"{params.loan_type or 'all'}"
        )

        retrieved_data = {
            **state.get("retrieved_data", {}),
            cache_key: result,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

        # RETURN STATE UPDATE
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
            "error": f"get_loan_portfolio_stats failed: {str(e)}",
        }
