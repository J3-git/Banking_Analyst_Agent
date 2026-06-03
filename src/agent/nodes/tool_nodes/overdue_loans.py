from datetime import datetime, timezone
from langgraph.runtime import Runtime
from agent.runtime_context import AppContext
from agent.agent_state import AgentState, OverdueLoansParams, RetrievedDataEntry
from agent.utils import export_csv, _serialize_value

# for debuging
import inspect


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

    Ownership rules:
    - This node writes ONLY to: tool_result, tool_results, retrieved_data, error
    - execution_context is NOT touched here - owned by summarize_node / merge_node
    """

    # Debug start
    frame = inspect.currentframe()
    print("===========================================================")
    print(f"DEBUG: Entered function: {frame.f_code.co_name}")

    # Debug end

    params: OverdueLoansParams = state.get("tool_params")

    if not isinstance(params, OverdueLoansParams):
        print("Debug overdue_loans: parameters issue, returning error")
        print("===========================================================")
        return {
            "error": "Required parameters to retrieve overdue loans are either missing, invalid or could not be extracted.",
        }

    # cache key - deterministic, param-scoped
    cache_key = (
        f"overdue_loans:"
        f"{params.city if params.city else 'City.all'}:"
        f"{params.loan_type if params.loan_type else 'LoanType.all'}:"
        f"{params.min_days_overdue or 1}"
    )

    try:
        db_client = runtime.context.db

        with db_client.conn() as conn:
            with db_client.cursor(conn, dict_cursor=True) as cur:

                conditions = ["l.status IN ('OVERDUE', 'DEFAULTED', 'NPA')"]
                values = []

                if params.city:
                    conditions.append("c.city = %s")
                    values.append(params.city.value)

                if params.loan_type:
                    conditions.append("l.loan_type = %s")
                    values.append(params.loan_type.value)

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
                        MAX(CASE WHEN r.status IN ('MISSED','PARTIAL') THEN r.dpd_days END) AS max_dpd,
                        COUNT(CASE WHEN r.status = 'MISSED' THEN 1 END) AS missed_payments
                    FROM loans l
                    JOIN customers c ON l.customer_id = c.customer_id
                    LEFT JOIN repayments r ON l.loan_id = r.loan_id
                    WHERE {where_clause}
                    GROUP BY
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

        # empty result
        if not loans:
            result = {
                "overall": {"total_overdue": 0},
                "dpd_buckets": {},
                "message": "No overdue loans found for the given filters.",
                "csv_path": None,
                "dataset_id": None,
            }

            entry = RetrievedDataEntry(
                intent="get_overdue_loans",
                params=params.model_dump(exclude_none=True),
                result=result,
                csv_path=None,
                dataset_id=None,
            )

            retrieved_data = {
                **state.get("retrieved_data", {}),
                cache_key: entry.model_dump(),
            }

            print("DEBUG overdue_loans: empty result handling")
            print(f"DEBUG overdue_loans: cache_key: {cache_key}")
            print(f"DEBUG overdue_loans: result overall: {result['overall']}")
            print(
                f"DEBUG overdue_loans: total_overdue: {result['overall']['total_overdue']}"
            )
            print("==========================================================")

            return {
                "tool_result": result,
                "tool_results": [result],
                "retrieved_data": retrieved_data,
                "error": None,
            }

        # DPD bucketing
        buckets: dict[str, list] = {
            "1_to_30": [],
            "31_to_60": [],
            "61_to_90": [],
            "above_90": [],
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

        dataset_id, export_path = export_csv(rows=loans, prefix="overdue_loans")

        result = {
            "overall": {"total_overdue": len(loans)},
            "dpd_buckets": {
                "early_1_to_30_days": len(buckets["1_to_30"]),
                "moderate_31_to_60_days": len(buckets["31_to_60"]),
                "serious_61_to_90_days": len(buckets["61_to_90"]),
                "critical_above_90_days": len(buckets["above_90"]),
            },
            "top_critical": loans[:3],
            "csv_path": export_path,
            "dataset_id": dataset_id,
        }

        entry = RetrievedDataEntry(
            intent="get_overdue_loans",
            params=params.model_dump(exclude_none=True),
            result=result,
            csv_path=export_path,
            dataset_id=dataset_id,
        )

        retrieved_data = {
            **state.get("retrieved_data", {}),
            cache_key: entry.model_dump(),
        }

        print("DEBUG overdue_loans: overdue loans present.")
        print(f"DEBUG overdue_loans: cache_key: {cache_key}")
        print(f"DEBUG overdue_loans: result overall: {result['overall']}")
        print(
            f"DEBUG overdue_loans: total_overdue: {result['overall']['total_overdue']}"
        )
        print("==========================================================")

        return {
            "tool_result": result,
            "tool_results": [result],  # list for merge_node compatibility
            "retrieved_data": retrieved_data,
            "error": None,
        }

    except Exception as e:
        print("DEBUG overdue_loans: in get_overdue_loans_node exception occurred:")
        print(f"DEBUG overdue_loans: error: {e}")
        print("Debug overdue_loans: returning error")
        print("==========================================================")

        return {
            "error": f"get_overdue_loans tool failed: {str(e)}",
        }
