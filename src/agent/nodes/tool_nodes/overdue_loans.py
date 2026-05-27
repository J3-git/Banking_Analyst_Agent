from agent.utils import _serialize_value

from agent.agent_state import (
    AgentState,
    OverdueLoansParams,
)

from langgraph.runtime import Runtime
from agent.runtime_context import AppContext

from agent.utils import export_csv

from datetime import datetime, timezone


# Tool node to get overdue_loans:
def get_overdue_loans_node(
    state: AgentState,
    runtime: Runtime[AppContext],
) -> dict:
    """
    Fetch overdue/defaulted/NPA loans with optional filters.

     DPD Buckets:
         1-30   -> Early overdue
         31-60  -> Moderate
         61-90  -> Serious
         90+    -> Critical / NPA territory
    """
    params: OverdueLoansParams = state.get("tool_params")
    if not isinstance(params, OverdueLoansParams):
        return {
            "tool_result": None,
            "retrieved_data": state.get("retrieved_data", {}),
            "execution_context": state.get("execution_context", {}),
            "error": "Required parameters to retrieve overdue loans are either missing, invalid or could not be extracted.",
        }

    try:
        db_client = runtime.context.db

        with db_client.conn() as conn:
            with db_client.cursor(conn, dict_cursor=True) as cur:

                # dynamic WHERE clause based on provided params
                conditions = ["l.status IN ('OVERDUE', 'DEFAULTED', 'NPA')"]

                values = []

                if params.city:
                    conditions.append("c.city = %s")
                    values.append(params.city)

                if params.loan_type:
                    conditions.append("l.loan_type = %s")
                    values.append(params.loan_type)

                if params.min_days_overdue:
                    conditions.append("""
                        (
                            SELECT MAX(r2.dpd_days)
                            FROM repayments r2
                            WHERE r2.loan_id = l.loan_id
                            AND r2.status IN ('MISSED', 'PARTIAL')
                        ) >= %s
                    """)
                    values.append(params.min_days_overdue)

                where_clause = " AND ".join(conditions)

                cur.execute(
                    f"""
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
                        MAX(CASE WHEN r.status IN ('MISSED','PARTIAL') THEN r.dpd_days END) AS max_dpd,
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
                """,
                    values,
                )

                rows = cur.fetchall()

        loans = [{k: _serialize_value(v) for k, v in row.items()} for row in rows]

        if not loans:

            result = {
                "overall": {
                    "total_overdue": 0,
                    # "loans": [],
                },
                "dpd_buckets": {},
                "message": "No overdue loans found for the given filters.",
                "export_path": None,
                "dataset_id": None,
            }

            # update context
            execution_context = {
                **state.get("execution_context", {}),
                "last_tool": "get_overdue_loans",
                "last_result_empty": True,
                **({"active_city": params.city} if params.city else {}),
                **({"active_loan_type": params.loan_type} if params.loan_type else {}),
                **(
                    {"selected_min_days_overdue": params.min_days_overdue}
                    if params.min_days_overdue
                    else {}
                ),
                "export_path": None,
                "dataset_id": None,
            }

            cache_key = (
                f"overdue_loans:"
                f"{params.city or 'all'}:"
                f"{params.loan_type or 'all'}:"
                f"{params.min_days_overdue or 1}"
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

        # Insight: DPD bucketing:
        buckets = {
            "1_to_30": [],  # Early overdue
            "31_to_60": [],  # Moderate
            "61_to_90": [],  # Serious
            "above_90": [],  # Critical
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

        dataset_id, export_path = export_csv(
            rows=loans,
            prefix="overdue_loans",
        )

        # RESULT
        result = {
            "overall": {
                "total_overdue": len(loans),
                # "loans": loans,
            },
            "dpd_buckets": {
                "early_1_to_30_days": len(buckets["1_to_30"]),
                "moderate_31_to_60_days": len(buckets["31_to_60"]),
                "serious_61_to_90_days": len(buckets["61_to_90"]),
                "critical_above_90_days": len(buckets["above_90"]),
            },
            "top_critical": loans[:10],
            "export_path": export_path,
            "dataset_id": dataset_id,
        }

        # EXECUTION CONTEXT UPDATE
        execution_context = {
            **state.get("execution_context", {}),
            "last_tool": "get_overdue_loans",
            **({"active_city": params.city} if params.city else {}),
            **({"active_loan_type": params.loan_type} if params.loan_type else {}),
            **(
                {"selected_min_days_overdue": params.min_days_overdue}
                if params.min_days_overdue
                else {}
            ),
            "export_path": export_path,
            "dataset_id": dataset_id,
        }

        # RETRIEVED DATA CACHE
        cache_key = (
            f"overdue_loans:"
            f"{params.city or 'all'}:"
            f"{params.loan_type or 'all'}:"
            f"{params.min_days_overdue or 1}"
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
            "error": f"get_overdue_loans tool failed: {str(e)}",
        }
