from agent.utils import _serialize_value

from agent.agent_state import (
    AgentState,
    CustomerProfileParams,
)

from langgraph.runtime import Runtime
from agent.runtime_context import AppContext

from datetime import datetime, timezone


# Helper function only specific to 'get_customer_profile_node' tool node:
def _compute_risk_level(max_dpd: int, loan_status: str) -> str:
    """
    Classifies loan risk on the basis of DPD(Days Past DueDate).

    DPD thresholds:
        0  - 30  days  --> LOW
        31 - 60  days  --> MEDIUM
        61 - 90  days  --> HIGH
        90+ days       --> CRITICAL

    Loan status overrides DPD-based classification when already formally classified:
        NPA / DEFAULTED -> always CRITICAL regardless of DPD
        OVERDUE         -> at least MEDIUM regardless of DPD
    """
    # Status-based override:
    if loan_status in ("NPA", "DEFAULTED"):
        return "CRITICAL"

    # DPD-based classification — RBI SMA buckets
    if max_dpd > 90:
        return "CRITICAL"
    elif max_dpd > 60:
        return "HIGH"
    elif max_dpd > 30:
        return "MEDIUM"
    elif loan_status == "OVERDUE":
        return "MEDIUM"
    else:
        return "LOW"


# Tool node to get customer_profile:
def get_customer_profile_node(
    state: AgentState,
    runtime: Runtime[AppContext],
) -> dict:
    """
    Returns full profile of a customer including:
      - Personal details
      - All their loans with current status
      - Repayment summary per loan
      - Risk flag
    """
    params: CustomerProfileParams = state.get("tool_params")

    if not isinstance(params, CustomerProfileParams):
        return {
            "tool_result": None,
            "retrieved_data": state.get("retrieved_data", {}),
            "execution_context": state.get("execution_context", {}),
            "error": "Missing a customer id or unable to extract it. Please mention the customer id explicitly.",
        }

    try:
        db_client = runtime.context.db

        with db_client.conn() as conn:
            with db_client.cursor(conn, dict_cursor=True) as cur:

                # Customer basic info:
                cur.execute(
                    """
                    SELECT
                        customer_id,
                        full_name,
                        age,
                        gender,
                        phone,
                        email,
                        city,
                        branch_name,
                        annual_income,
                        employment_type,
                        credit_score,
                        created_at
                    FROM customers
                    WHERE customer_id = %s
                """,
                    (params.customer_id,),
                )  # The trailing comma in (params.customer_id,) makes it a tuple — required by psycopg2 even for a single value.

                customer = cur.fetchone()
                if not customer:
                    result = {
                        "customer_profile": None,
                        "loan_summaries": [],
                        "portfolio_risk_level": None,
                        "message": f"Customer {params.customer_id} not found",
                    }

                    # update context
                    execution_context = {
                        **state.get("execution_context", {}),
                        "last_tool": "get_customer_profile",
                        "last_result_empty": True,
                    }

                    cache_key = f"customer_profile:{params.customer_id}"

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

                customer = {k: _serialize_value(v) for k, v in customer.items()}

                # All loans for this customer:
                cur.execute(
                    """
                    SELECT
                        l.loan_id,
                        l.loan_type,
                        l.principal_amount,
                        l.interest_rate,
                        l.tenure_months,
                        l.emi_amount,
                        l.disbursed_date,
                        l.maturity_date,
                        l.outstanding_amount,
                        l.status,
                        l.purpose,
                        COUNT(r.repayment_id) AS total_emis,
                        SUM(CASE WHEN r.status = 'MISSED' THEN 1 ELSE 0 END) AS missed_count,
                        SUM(CASE WHEN r.status = 'PAID_LATE' THEN 1 ELSE 0 END) AS late_count,
                        SUM(CASE WHEN r.status = 'PARTIAL' THEN 1 ELSE 0 END) AS partial_count,
                        MAX(r.dpd_days) AS max_dpd
                    FROM loans l
                    LEFT JOIN repayments r ON l.loan_id = r.loan_id
                    WHERE l.customer_id = %s
                    GROUP BY l.loan_id
                    ORDER BY l.disbursed_date DESC
                    """,
                    (params.customer_id,),
                )

                loans = []
                risk_levels = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
                final_risk = "LOW"

                # Insight — risk level
                # Considering worst risk level across all loans for this customer
                # i.e. A customer is as risky as their worst loan.

                for row in cur.fetchall():
                    loan = {k: _serialize_value(v) for k, v in row.items()}

                    level = _compute_risk_level(
                        max_dpd=loan.get("max_dpd") or 0,
                        loan_status=loan["status"],
                    )

                    loan["risk_level"] = (
                        level  # annotate each loan with its own risk level
                    )

                    loans.append(loan)

                    if risk_levels[level] > risk_levels[final_risk]:
                        final_risk = level  # escalate customer risk to worst loan"

        # FINAL RESULT
        result = {
            "customer_profile": customer,
            "loan_summaries": loans,
            "portfolio_risk_level": final_risk,
        }

        # UPDATE EXECUTION CONTEXT
        execution_context = {
            **state.get("execution_context", {}),
            "last_tool": "get_customer_profile",
            "current_customer_id": params.customer_id,
            "current_customer_name": customer.get("full_name"),
            "portfolio_risk_level": final_risk,
            "loan_count": len(loans),  # also applying the earlier fix here
        }

        # UPDATE RETRIEVED DATA CACHE
        cache_key = f"customer_profile:" f"{params.customer_id}"

        retrieved_data = {
            **state.get("retrieved_data", {}),
            cache_key: result,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

        # RETURN PARTIAL STATE UPDATE
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
            "error": f"get_customer_profile failed: {str(e)}",
        }
