from agent.utils import _rows
from psycopg2 import pool as pg_pool
from psycopg2.extras import RealDictCursor
from datetime import date
from decimal import Decimal
from agent.agent_state import (
    AgentState,
    CustomerProfileParams,
)


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
    state: AgentState, db_pool: pg_pool.SimpleConnectionPool
) -> dict:
    """
    Returns full profile of a customer including:
      - Personal details
      - All their loans with current status
      - Repayment summary per loan
      - Risk flag
    """
    params: CustomerProfileParams = state["tool_params"]

    if not params.customer_id:
        return {
            "tool_result": None,
            "excel_path": None,
            "error": "Please provide a customer ID.",
        }

    conn = db_pool.getconn()

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)  # Row -> dict instead of tuple

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
            return {
                "tool_result": None,
                "excel_path": None,
                "error": f"Customer ID {params.customer_id} not found",
            }
        customer = dict(customer)
        # Serialise date/Decimal
        for k, v in customer.items():
            if isinstance(v, Decimal):
                customer[k] = float(v)
            elif isinstance(v, date):
                customer[k] = v.isoformat()

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

        loans = _rows(cur)

        # Insight — risk level
        # Considering worst risk level across all loans for this customer
        # i.e. A customer is as risky as their worst loan.
        risk_level = "LOW"
        priority = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}

        for loan in loans:
            level = _compute_risk_level(
                max_dpd=loan.get("max_dpd") or 0, loan_status=loan["status"]
            )
            loan["risk_level"] = level  # annotate each loan with its own risk level
            if priority[level] > priority[risk_level]:
                risk_level = level  # escalate customer risk to worst loan"

        cur.close()
        return {
            "tool_result": {
                "customer": customer,
                "loans": loans,
                "risk_level": risk_level,  # worst risk level across all loans
            },
            "excel_path": None,
            "error": None,
        }

    except Exception as e:
        return {
            "tool_result": None,
            "excel_path": None,
            "error": f"get_customer_profile tool failed: {str(e)}",
        }
    finally:
        db_pool.putconn(conn)
