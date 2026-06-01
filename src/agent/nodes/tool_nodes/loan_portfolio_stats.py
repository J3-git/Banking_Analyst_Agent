from agent.utils import _serialize_value
from agent.agent_state import (
    AgentState,
    LoanPortfolioStatsParams,
    RetrievedDataEntry,
)
from langgraph.runtime import Runtime
from agent.runtime_context import AppContext

ALLOWED_GROUP_EXPRESSIONS = {
    "city": "c.city",
    "status": "l.status",
    "loan_type": "l.loan_type",
}


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

    Ownership rules:
      - This node writes ONLY to: tool_result, tool_results, retrieved_data, error
    """

    params: LoanPortfolioStatsParams = state.get("tool_params")

    if not isinstance(params, LoanPortfolioStatsParams):
        return {
            "error": "Required parameters to retrieve portfolio statistics are either missing, invalid or could not be extracted.",
        }

    # resolve group_by early - needed for cache_key in both empty and success paths
    group_col = (
        params.group_by.value
        if params.group_by and params.group_by.value in ALLOWED_GROUP_EXPRESSIONS
        else "loan_type"
    )

    cache_key = (
        f"portfolio_stats:"
        f"{group_col}:"
        f"{params.city.value if params.city else 'all'}:"
        f"{params.loan_type.value if params.loan_type else 'all'}"
    )

    try:
        db_client = runtime.context.db

        with db_client.conn() as conn:
            with db_client.cursor(conn, dict_cursor=True) as cur:

                # overall portfolio summary
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
                                CASE WHEN status IN ('DEFAULTED', 'NPA') THEN 1 ELSE 0 END
                            ) / NULLIF(COUNT(*), 0),
                            2
                        ) AS default_rate_pct
                    FROM loans l
                    JOIN customers c ON l.customer_id = c.customer_id
                    WHERE (%s IS NULL OR c.city = %s)
                    AND (%s IS NULL OR l.loan_type = %s)
                    """,
                    (
                        params.city.value if params.city else None,
                        params.city.value if params.city else None,
                        params.loan_type.value if params.loan_type else None,
                        params.loan_type.value if params.loan_type else None,
                    ),
                )

                overall_row = cur.fetchone()
                overall = {k: _serialize_value(v) for k, v in overall_row.items()}

                # empty result
                if not overall or (overall.get("total_loans") or 0) == 0:
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

                    entry = RetrievedDataEntry(
                        intent="get_loan_portfolio_stats",
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

                # breakdown analytics
                group_expr = ALLOWED_GROUP_EXPRESSIONS[group_col]

                cur.execute(
                    f"""
                    SELECT
                        {group_expr} AS group_name,
                        COUNT(*) AS total_loans,
                        SUM(l.principal_amount) AS total_disbursed,
                        SUM(l.outstanding_amount) AS total_outstanding,
                        ROUND(
                            100.0 * SUM(
                                CASE WHEN l.status IN ('DEFAULTED', 'NPA') THEN 1 ELSE 0 END
                            ) / NULLIF(COUNT(*), 0),
                            2
                        ) AS default_rate_pct
                    FROM loans l
                    JOIN customers c ON l.customer_id = c.customer_id
                    WHERE (%s IS NULL OR c.city = %s)
                    AND (%s IS NULL OR l.loan_type = %s)
                    GROUP BY {group_expr}
                    ORDER BY default_rate_pct DESC NULLS LAST
                    """,
                    (
                        params.city.value if params.city else None,
                        params.city.value if params.city else None,
                        params.loan_type.value if params.loan_type else None,
                        params.loan_type.value if params.loan_type else None,
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

        result = {
            "overall": overall,
            "grouped_by": group_col,
            "breakdown": breakdown,
        }

        entry = RetrievedDataEntry(
            intent="get_loan_portfolio_stats",
            params=params.model_dump(exclude_none=True),
            result=result,
        )

        retrieved_data = {
            **state.get("retrieved_data", {}),
            cache_key: entry.model_dump(),
        }

        print("==========================================================")
        print("DEBUG: in get_loan_portfolio_stats_node:")
        print(f"DEBUG: cache_key: {cache_key}")
        print(f"DEBUG: total_loans: {overall.get('total_loans')}")
        print(f"DEBUG: default_rate_pct: {overall.get('default_rate_pct')}")
        print("==========================================================")

        return {
            "tool_result": result,
            "tool_results": [result],
            "retrieved_data": retrieved_data,
            "error": None,
        }

    except Exception as e:
        print("==========================================================")
        print("DEBUG: in get_loan_portfolio_stats_node exception occurred:")
        print(f"DEBUG: error: {e}")
        print("==========================================================")

        return {
            "error": f"get_loan_portfolio_stats failed: {str(e)}",
        }
