"""
Banking / Loan Analyst Assistant — Data Generation Script
==========================================================
Generates mock data and inserts into PostgreSQL.
Matches 5-table schema: customers, employees, loans, repayments, loan_assignments

Requirements:
    pip install faker psycopg2-binary python-dateutil

Usage:
    1. Start PostgreSQL via docker compose --env-file .env.server up -d
    2. Schema auto-runs on first start via docker-entrypoint-initdb.d
    3. Run this script: python generate_data.py

# Known simplification
# Partial payments do not carry forward shortfall to next month's due amount.
# In production, arrears would be tracked and added to subsequent EMI dues.
# This simplification does not affect agent tool logic or architecture.

"""

import random
import psycopg2
from faker import Faker
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

# from dotenv import load_dotenv
from pathlib import Path
import os

# env_path = Path(__file__).resolve().parent.parent/".env.server"

# load_dotenv(env_path)


# CONFIG — update with your PostgreSQL credentials

DB_CONFIG = {
    "host": os.getenv("db_host"),
    "port": os.getenv("db_port"),
    "dbname": os.getenv("db_name"),
    "user": os.getenv("db_user"),
    "password": os.getenv("db_password")
}


# GENERATION SETTINGS

NUM_EMPLOYEES = 20
NUM_CUSTOMERS = 80
NUM_LOANS     = 120   # some customers will get multiple loans

fake = Faker('en_IN')  # Indian locale — realistic names, cities
random.seed(100)        # reproducible results


# STATIC REFERENCE DATA

# (branch_name, city)
BRANCHES = [
    ("Mumbai Main Branch",      "Mumbai"),
    ("Mumbai Andheri Branch",   "Mumbai"),
    ("Delhi Connaught Branch",  "Delhi"),
    ("Delhi Dwarka Branch",     "Delhi"),
    ("Pune Koregaon Branch",    "Pune"),
    ("Bangalore MG Road Branch","Bangalore"),
]

# (loan_type, base_interest_rate, max_tenure_months, max_amount)
LOAN_TYPES = [
    ("Personal",  14.50,  60,  1500000),
    ("Home",       8.75, 240, 10000000),
    ("Business",  16.00,  84,  5000000),
    ("Vehicle",   11.50,  84,  2000000),
    ("Education", 10.00, 120,  2000000),
    ("Gold",       9.50,  24,   500000),
]

LOAN_PURPOSES = {
    "Personal":  ["Medical emergency", "Wedding expenses", "Home renovation", "Travel", "Debt consolidation"],
    "Home":      ["Property purchase", "Home construction", "Property renovation"],
    "Business":  ["Working capital", "Equipment purchase", "Business expansion", "Inventory"],
    "Vehicle":   ["Car purchase", "Bike purchase", "Commercial vehicle"],
    "Education": ["Undergraduate abroad", "Postgraduate India", "Professional course"],
    "Gold":      ["Emergency funds", "Business need", "Agricultural purpose"],
}

EMPLOYMENT_TYPES = ["Salaried", "Self-Employed", "Business Owner", "Government Employee"]
EMPLOYEE_ROLES   = ["Loan Officer", "Loan Officer", "Loan Officer", "Branch Manager", "Credit Analyst"]


# HELPER FUNCTIONS

def calculate_emi(principal, annual_rate, tenure_months):
    """Standard EMI formula: P * r * (1+r)^n / ((1+r)^n - 1)"""
    if annual_rate == 0:
        return round(principal / tenure_months, 2)
    r   = annual_rate / (12 * 100)
    emi = principal * r * ((1 + r) ** tenure_months) / (((1 + r) ** tenure_months) - 1)
    return round(emi, 2)


def random_date(start_year=2021, end_year=2023):
    start = date(start_year, 1, 1)
    end   = date(end_year, 12, 31)
    return start + timedelta(days=random.randint(0, (end - start).days))


def derive_loan_status(repayment_records):
    """Derive loan status from repayment history."""
    missed = [r for r in repayment_records if r["status"] == "MISSED"]
    if len(missed) >= 4:
        return "NPA"
    elif len(missed) >= 2:
        return random.choice(["DEFAULTED", "OVERDUE"])
    elif len(missed) == 1:
        return "OVERDUE"
    else:
        # Check if all past dues are paid — could be CLOSED
        upcoming = [r for r in repayment_records if r["status"] == "UPCOMING"]
        if not upcoming:
            return "CLOSED"
        return "ACTIVE"


def generate_repayment_pattern(emi_amount, disbursed_date, tenure_months):
    """
    Generate a full EMI repayment history for a loan.

    Customer behavior profiles:
      good           (50%) — mostly on time, rare late payment
      occasional_late(25%) — pays but often late
      struggling     (15%) — mix of late, missed, partial
      defaulter      (10%) — multiple missed payments
    """
    today   = date.today()
    profile = random.choices(
        ["good", "occasional_late", "struggling", "defaulter"],
        weights=[50, 25, 15, 10]
    )[0]

    repayments = []

    for i in range(tenure_months):
        due_date = disbursed_date + relativedelta(months=i + 1)

        # Future EMI — not yet due
        if due_date > today:
            repayments.append({
                "due_date":     due_date,
                "paid_date":    None,
                "amount_due":   emi_amount,
                "amount_paid":  0,
                "days_past_due": 0,
                "status":       "UPCOMING"
            })
            continue

        roll = random.random()

        if profile == "good":
            if roll < 0.90:
                repayments.append({
                    "due_date":     due_date,
                    "paid_date":    due_date - timedelta(days=random.randint(0, 2)),
                    "amount_due":   emi_amount,
                    "amount_paid":  emi_amount,
                    "days_past_due": 0,
                    "status":       "PAID_ONTIME"
                })
            elif roll < 0.98:
                days_late = random.randint(1, 10)
                repayments.append({
                    "due_date":     due_date,
                    "paid_date":    due_date + timedelta(days=days_late),
                    "amount_due":   emi_amount,
                    "amount_paid":  emi_amount,
                    "days_past_due": days_late,
                    "status":       "PAID_LATE"
                })
            else:
                repayments.append({
                    "due_date":     due_date,
                    "paid_date":    None,
                    "amount_due":   emi_amount,
                    "amount_paid":  0,
                    "days_past_due": (today - due_date).days,
                    "status":       "MISSED"
                })

        elif profile == "occasional_late":
            if roll < 0.50:
                repayments.append({
                    "due_date":     due_date,
                    "paid_date":    due_date,
                    "amount_due":   emi_amount,
                    "amount_paid":  emi_amount,
                    "days_past_due": 0,
                    "status":       "PAID_ONTIME"
                })
            elif roll < 0.90:
                days_late = random.randint(5, 30)
                repayments.append({
                    "due_date":     due_date,
                    "paid_date":    due_date + timedelta(days=days_late),
                    "amount_due":   emi_amount,
                    "amount_paid":  emi_amount,
                    "days_past_due": days_late,
                    "status":       "PAID_LATE"
                })
            else:
                repayments.append({
                    "due_date":     due_date,
                    "paid_date":    None,
                    "amount_due":   emi_amount,
                    "amount_paid":  0,
                    "days_past_due": (today - due_date).days,
                    "status":       "MISSED"
                })

        elif profile == "struggling":
            if roll < 0.30:
                repayments.append({
                    "due_date":     due_date,
                    "paid_date":    due_date,
                    "amount_due":   emi_amount,
                    "amount_paid":  emi_amount,
                    "days_past_due": 0,
                    "status":       "PAID_ONTIME"
                })
            elif roll < 0.60:
                days_late = random.randint(10, 45)
                repayments.append({
                    "due_date":     due_date,
                    "paid_date":    due_date + timedelta(days=days_late),
                    "amount_due":   emi_amount,
                    "amount_paid":  emi_amount,
                    "days_past_due": days_late,
                    "status":       "PAID_LATE"
                })
            elif roll < 0.85:
                repayments.append({
                    "due_date":     due_date,
                    "paid_date":    None,
                    "amount_due":   emi_amount,
                    "amount_paid":  0,
                    "days_past_due": (today - due_date).days,
                    "status":       "MISSED"
                })
            else:
                partial = round(emi_amount * random.uniform(0.3, 0.7), 2)
                days_late = random.randint(5, 20)
                repayments.append({
                    "due_date":     due_date,
                    "paid_date":    due_date + timedelta(days=days_late),
                    "amount_due":   emi_amount,
                    "amount_paid":  partial,
                    "days_past_due": days_late,
                    "status":       "PARTIAL"
                })

        else:  # defaulter
            if roll < 0.20:
                repayments.append({
                    "due_date":     due_date,
                    "paid_date":    due_date,
                    "amount_due":   emi_amount,
                    "amount_paid":  emi_amount,
                    "days_past_due": 0,
                    "status":       "PAID_ONTIME"
                })
            elif roll < 0.40:
                days_late = random.randint(15, 60)
                repayments.append({
                    "due_date":     due_date,
                    "paid_date":    due_date + timedelta(days=days_late),
                    "amount_due":   emi_amount,
                    "amount_paid":  emi_amount,
                    "days_past_due": days_late,
                    "status":       "PAID_LATE"
                })
            else:
                repayments.append({
                    "due_date":     due_date,
                    "paid_date":    None,
                    "amount_due":   emi_amount,
                    "amount_paid":  0,
                    "days_past_due": (today - due_date).days,
                    "status":       "MISSED"
                })

    return repayments



# MAIN

def generate_and_insert():
    conn = psycopg2.connect(**DB_CONFIG)
    cur  = conn.cursor()
    print("Starting data generation...\n")

    
    # 1. Insert Employees    
    print("Inserting employees...")
    employee_ids = []

    for _ in range(NUM_EMPLOYEES):
        branch_name, city = random.choice(BRANCHES)
        cur.execute("""
            INSERT INTO employees
                (full_name, email, phone, role, branch_name, city, joined_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING employee_id
        """, (
            fake.name(),
            fake.unique.email(),
            fake.phone_number()[:15],
            random.choice(EMPLOYEE_ROLES),
            branch_name,
            city,
            fake.date_between(start_date='-6y', end_date='-6m')
        ))
        employee_ids.append(cur.fetchone()[0])

    print(f"{len(employee_ids)} employees inserted")

    
    # 2. Insert Customers
    print("Inserting customers...")
    customer_ids = []

    for _ in range(NUM_CUSTOMERS):
        branch_name, city = random.choice(BRANCHES)
        employment_type   = random.choice(EMPLOYMENT_TYPES)

        # Income varies by employment type
        income_ranges = {
            "Government Employee": (400000,  1200000),
            "Business Owner":      (600000,  5000000),
            "Self-Employed":       (300000,  2000000),
            "Salaried":            (300000,  1500000),
        }
        lo, hi = income_ranges[employment_type]
        income = random.randint(lo, hi)

        # Credit score loosely correlates with income
        base_score   = 600 + int((income / 5000000) * 200)
        credit_score = min(900, max(300, base_score + random.randint(-80, 80)))

        cur.execute("""
            INSERT INTO customers
                (full_name, age, gender, phone, email,
                 city, branch_name, annual_income,
                 employment_type, credit_score, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING customer_id
        """, (
            fake.name(),
            random.randint(22, 62),
            random.choice(["Male", "Female"]),
            fake.phone_number()[:15],
            fake.email(),
            city,
            branch_name,
            income,
            employment_type,
            credit_score,
            fake.date_between(start_date='-4y', end_date='-1y')
        ))
        customer_ids.append(cur.fetchone()[0])

    print(f"{len(customer_ids)} customers inserted")

    
    # 3. Insert Loans + Repayments + Loan Assignments
    print("Inserting loans, repayments, assignments...")
    loan_count      = 0
    repayment_count = 0

    # Allow some customers to have multiple loans
    customer_sample = random.choices(customer_ids, k=NUM_LOANS)

    for customer_id in customer_sample:

        # Fetch customer info for realistic loan sizing
        cur.execute("""
            SELECT annual_income, credit_score, branch_name
            FROM customers WHERE customer_id = %s
        """, (customer_id,))
        income, credit_score, branch_name = cur.fetchone()

        # Pick a loan type
        loan_type, base_rate, max_tenure, max_amount = random.choice(LOAN_TYPES)

        # Loan amount based on income
        income_multiplier = 3 if loan_type == "Home" else 1
        max_eligible = min(float(max_amount), float(income) * income_multiplier)
        principal    = round(random.uniform(max_eligible * 0.2, max_eligible * 0.8), -3)
        principal    = max(50000.0, principal)

        # Better credit score = lower interest rate
        rate_adj      = (750 - credit_score) / 100 * 0.5
        interest_rate = round(max(base_rate - 1.5, base_rate + rate_adj), 2)

        # Pick a realistic tenure
        valid_tenures = [t for t in [12, 24, 36, 48, 60, 84, 120, 180, 240] if t <= max_tenure]
        tenure_months = random.choice(valid_tenures)

        emi_amount     = calculate_emi(principal, interest_rate, tenure_months)
        disbursed_date = random_date(start_year=2021, end_year=2023)
        maturity_date  = disbursed_date + relativedelta(months=tenure_months)
        purpose        = random.choice(LOAN_PURPOSES.get(loan_type, ["General purpose"]))

        # Generate repayment history
        repayments = generate_repayment_pattern(emi_amount, disbursed_date, tenure_months)

        # Derive loan status from repayment pattern
        loan_status = derive_loan_status(repayments)

        # Outstanding = principal minus estimated principal repaid
        total_paid  = sum(r["amount_paid"] for r in repayments)
        outstanding = round(max(0.0, float(principal) - total_paid * 0.6), 2)
        if loan_status == "CLOSED":
            outstanding = 0.0

        # Insert loan
        cur.execute("""
            INSERT INTO loans
                (customer_id, loan_type, principal_amount, interest_rate,
                 tenure_months, emi_amount, disbursed_date, maturity_date,
                 outstanding_amount, status, purpose)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING loan_id
        """, (
            customer_id, loan_type, principal, interest_rate,
            tenure_months, emi_amount, disbursed_date, maturity_date,
            outstanding, loan_status, purpose
        ))
        loan_id = cur.fetchone()[0]
        loan_count += 1

        # Insert repayment records
        for r in repayments:
            cur.execute("""
                INSERT INTO repayments
                    (loan_id, due_date, paid_date, amount_due,
                     amount_paid, days_past_due, status)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (
                loan_id,
                r["due_date"], r["paid_date"],
                r["amount_due"], r["amount_paid"],
                r["days_past_due"], r["status"]
            ))
            repayment_count += 1

        # Assign a loan officer from the same branch if possible
        cur.execute("""
            SELECT employee_id FROM employees
            WHERE branch_name = %s AND is_active = TRUE
            ORDER BY RANDOM() LIMIT 1
        """, (branch_name,))
        row = cur.fetchone()
        assigned_employee = row[0] if row else random.choice(employee_ids)

        cur.execute("""
            INSERT INTO loan_assignments
                (loan_id, employee_id, assigned_date, is_active)
            VALUES (%s, %s, %s, TRUE)
        """, (loan_id, assigned_employee, disbursed_date))

    print(f"{loan_count} loans inserted")
    print(f"{repayment_count} repayment records inserted")
    print(f"{loan_count} loan assignments inserted")

    conn.commit()
    cur.close()
    conn.close()

    print(f"""
Data generation complete!

Summary:
  Employees:        {NUM_EMPLOYEES}
  Customers:        {NUM_CUSTOMERS}
  Loans:            {loan_count}
  Repayments:       {repayment_count}
  Loan Assignments: {loan_count}
    """)


if __name__ == "__main__":
    generate_and_insert()