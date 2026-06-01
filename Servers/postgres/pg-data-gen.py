'''"""
Banking / Loan Analyst Assistant - Data Generation Script
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


# CONFIG - update with your PostgreSQL credentials

DB_CONFIG = {
    "host": os.getenv("db_host"),
    "port": os.getenv("db_port"),
    "dbname": os.getenv("db_name"),
    "user": os.getenv("db_user"),
    "password": os.getenv("db_password"),
}


# GENERATION SETTINGS

NUM_EMPLOYEES = 5
NUM_CUSTOMERS = 25
NUM_LOANS = 50  # some customers will get multiple loans

fake = Faker("en_IN")  # Indian locale - realistic names, cities
random.seed(100)  # reproducible results


# STATIC REFERENCE DATA

# (branch_name, city)
BRANCHES = [
    ("Mumbai Main Branch", "Mumbai"),
    ("Mumbai Andheri Branch", "Mumbai"),
    ("Delhi Connaught Branch", "Delhi"),
    ("Delhi Dwarka Branch", "Delhi"),
    ("Pune Koregaon Branch", "Pune"),
    ("Bangalore MG Road Branch", "Bangalore"),
]

# (loan_type, base_interest_rate, max_tenure_months, max_amount)
LOAN_TYPES = [
    ("Personal", 14.50, 60, 1500000),
    ("Home", 8.75, 240, 10000000),
    ("Business", 16.00, 84, 5000000),
    ("Vehicle", 11.50, 84, 2000000),
    ("Education", 10.00, 120, 2000000),
    ("Gold", 9.50, 24, 500000),
]

LOAN_PURPOSES = {
    "Personal": [
        "Medical emergency",
        "Wedding expenses",
        "Home renovation",
        "Travel",
        "Debt consolidation",
    ],
    "Home": ["Property purchase", "Home construction", "Property renovation"],
    "Business": [
        "Working capital",
        "Equipment purchase",
        "Business expansion",
        "Inventory",
    ],
    "Vehicle": ["Car purchase", "Bike purchase", "Commercial vehicle"],
    "Education": ["Undergraduate abroad", "Postgraduate India", "Professional course"],
    "Gold": ["Emergency funds", "Business need", "Agricultural purpose"],
}

EMPLOYMENT_TYPES = [
    "Salaried",
    "Self-Employed",
    "Business Owner",
    "Government Employee",
]
EMPLOYEE_ROLES = [
    "Loan Officer",
    "Loan Officer",
    "Loan Officer",
    "Branch Manager",
    "Credit Analyst",
]


# HELPER FUNCTIONS


def calculate_emi(principal, annual_rate, tenure_months):
    """Standard EMI formula: P * r * (1+r)^n / ((1+r)^n - 1)"""
    if annual_rate == 0:
        return round(principal / tenure_months, 2)
    r = annual_rate / (12 * 100)
    emi = principal * r * ((1 + r) ** tenure_months) / (((1 + r) ** tenure_months) - 1)
    return round(emi, 2)


def random_date(start_year=2021, end_year=2023):
    start = date(start_year, 1, 1)
    end = date(end_year, 12, 31)
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
        # Check if all past dues are paid - could be CLOSED
        upcoming = [r for r in repayment_records if r["status"] == "UPCOMING"]
        if not upcoming:
            return "CLOSED"
        return "ACTIVE"


# def generate_repayment_pattern(emi_amount, disbursed_date, tenure_months):
#     """
#     Generate a full EMI repayment history for a loan.

#     Customer behavior profiles:
#       good           (50%) - mostly on time, rare late payment
#       occasional_late(25%) - pays but often late
#       struggling     (15%) - mix of late, missed, partial
#       defaulter      (10%) - multiple missed payments
#     """
#     today   = date.today()
#     profile = random.choices(
#         ["good", "occasional_late", "struggling", "defaulter"],
#         weights=[50, 25, 15, 10]
#     )[0]

#     repayments = []

#     for i in range(tenure_months):
#         due_date = disbursed_date + relativedelta(months=i + 1)

#         # Future EMI - not yet due
#         if due_date > today:
#             repayments.append({
#                 "due_date":     due_date,
#                 "paid_date":    None,
#                 "amount_due":   emi_amount,
#                 "amount_paid":  0,
#                 "dpd_days": 0,
#                 "status":       "UPCOMING"
#             })
#             continue

#         roll = random.random()

#         if profile == "good":
#             if roll < 0.90:
#                 repayments.append({
#                     "due_date":     due_date,
#                     "paid_date":    due_date - timedelta(days=random.randint(0, 2)),
#                     "amount_due":   emi_amount,
#                     "amount_paid":  emi_amount,
#                     "dpd_days": 0,
#                     "status":       "PAID_ONTIME"
#                 })
#             elif roll < 0.98:
#                 days_late = random.randint(1, 10)
#                 repayments.append({
#                     "due_date":     due_date,
#                     "paid_date":    due_date + timedelta(days=days_late),
#                     "amount_due":   emi_amount,
#                     "amount_paid":  emi_amount,
#                     "dpd_days": days_late,
#                     "status":       "PAID_LATE"
#                 })
#             else:
#                 repayments.append({
#                     "due_date":     due_date,
#                     "paid_date":    None,
#                     "amount_due":   emi_amount,
#                     "amount_paid":  0,
#                     "dpd_days": (today - due_date).days,
#                     "status":       "MISSED"
#                 })

#         elif profile == "occasional_late":
#             if roll < 0.50:
#                 repayments.append({
#                     "due_date":     due_date,
#                     "paid_date":    due_date,
#                     "amount_due":   emi_amount,
#                     "amount_paid":  emi_amount,
#                     "dpd_days": 0,
#                     "status":       "PAID_ONTIME"
#                 })
#             elif roll < 0.90:
#                 days_late = random.randint(5, 30)
#                 repayments.append({
#                     "due_date":     due_date,
#                     "paid_date":    due_date + timedelta(days=days_late),
#                     "amount_due":   emi_amount,
#                     "amount_paid":  emi_amount,
#                     "dpd_days": days_late,
#                     "status":       "PAID_LATE"
#                 })
#             else:
#                 repayments.append({
#                     "due_date":     due_date,
#                     "paid_date":    None,
#                     "amount_due":   emi_amount,
#                     "amount_paid":  0,
#                     "dpd_days": (today - due_date).days,
#                     "status":       "MISSED"
#                 })

#         elif profile == "struggling":
#             if roll < 0.30:
#                 repayments.append({
#                     "due_date":     due_date,
#                     "paid_date":    due_date,
#                     "amount_due":   emi_amount,
#                     "amount_paid":  emi_amount,
#                     "dpd_days": 0,
#                     "status":       "PAID_ONTIME"
#                 })
#             elif roll < 0.60:
#                 days_late = random.randint(10, 45)
#                 repayments.append({
#                     "due_date":     due_date,
#                     "paid_date":    due_date + timedelta(days=days_late),
#                     "amount_due":   emi_amount,
#                     "amount_paid":  emi_amount,
#                     "dpd_days": days_late,
#                     "status":       "PAID_LATE"
#                 })
#             elif roll < 0.85:
#                 repayments.append({
#                     "due_date":     due_date,
#                     "paid_date":    None,
#                     "amount_due":   emi_amount,
#                     "amount_paid":  0,
#                     "dpd_days": (today - due_date).days,
#                     "status":       "MISSED"
#                 })
#             else:
#                 partial = round(emi_amount * random.uniform(0.3, 0.7), 2)
#                 days_late = random.randint(5, 20)
#                 repayments.append({
#                     "due_date":     due_date,
#                     "paid_date":    due_date + timedelta(days=days_late),
#                     "amount_due":   emi_amount,
#                     "amount_paid":  partial,
#                     "dpd_days": days_late,
#                     "status":       "PARTIAL"
#                 })

#         else:  # defaulter
#             if roll < 0.20:
#                 repayments.append({
#                     "due_date":     due_date,
#                     "paid_date":    due_date,
#                     "amount_due":   emi_amount,
#                     "amount_paid":  emi_amount,
#                     "dpd_days": 0,
#                     "status":       "PAID_ONTIME"
#                 })
#             elif roll < 0.40:
#                 days_late = random.randint(15, 60)
#                 repayments.append({
#                     "due_date":     due_date,
#                     "paid_date":    due_date + timedelta(days=days_late),
#                     "amount_due":   emi_amount,
#                     "amount_paid":  emi_amount,
#                     "dpd_days": days_late,
#                     "status":       "PAID_LATE"
#                 })
#             else:
#                 repayments.append({
#                     "due_date":     due_date,
#                     "paid_date":    None,
#                     "amount_due":   emi_amount,
#                     "amount_paid":  0,
#                     "dpd_days": (today - due_date).days,
#                     "status":       "MISSED"
#                 })

#     return repayments


# def generate_repayment_pattern_fifo(
#     emi_amount,
#     disbursed_date,
#     tenure_months,
#     principal,
#     annual_interest_rate,
#     late_fee_flat=500,
#     grace_period_days=3,
#     penal_annual_rate=0.02,
#     seed=None,
# ):
#     rng = random.Random(seed)

#     monthly_rate = annual_interest_rate / (12 * 100)
#     penal_daily_rate = penal_annual_rate / 365

#     outstanding_balance = principal

#     profile = rng.choices(
#         ["good", "occasional_late", "struggling", "defaulter"], weights=[50, 25, 15, 10]
#     )[0]

#     risk = {
#         "good": 0.05,
#         "occasional_late": 0.20,
#         "struggling": 0.50,
#         "defaulter": 0.80,
#     }[profile]

#     # prob_full = 1 - risk
#     # prob_partial = risk * 0.5

#     repayments = []
#     dues_queue = []

#     max_extra_months = 12
#     total_months = tenure_months + max_extra_months
#     for i in range(total_months):
#         is_recovery_phase = i >= tenure_months
#         cycle_due_date = disbursed_date + relativedelta(months=i + 1)
#         prev_cycle_date = disbursed_date + relativedelta(months=i)
#         days_in_cycle = (cycle_due_date - prev_cycle_date).days

#         # Mark overdue_since only for EMI dues whose due date has passed
#         for due in dues_queue:
#             if (
#                 due["kind"] == "emi"
#                 and due["remaining"] > 0
#                 and due.get("overdue_since") is None
#             ):
#                 grace_deadline = due["due_date"] + timedelta(days=grace_period_days)
#                 if cycle_due_date > grace_deadline:
#                     due["overdue_since"] = grace_deadline + timedelta(days=1)

#         # Penal entries (buffered)
#         new_penal_entries = []
#         for due in dues_queue:
#             if (
#                 due["kind"] == "emi"
#                 and due["remaining"] > 0
#                 and due.get("overdue_since")
#             ):
#                 penal_charge = round(
#                     due["remaining"] * penal_daily_rate * days_in_cycle, 2
#                 )
#                 if penal_charge > 0:
#                     new_penal_entries.append(
#                         {
#                             "kind": "penal",
#                             "due_date": due["overdue_since"],
#                             "remaining": penal_charge,
#                             "linked_emi_date": due["due_date"],
#                         }
#                     )
#         dues_queue.extend(new_penal_entries)

#         # Late fee (one-time)
#         new_late_fees = []
#         for due in dues_queue:
#             if (
#                 due["kind"] == "emi"
#                 and due["remaining"] > 0
#                 and due.get("overdue_since")
#             ):

#                 already_exists = any(
#                     d["kind"] == "late_fee" and d["linked_emi_date"] == due["due_date"]
#                     for d in dues_queue
#                 )

#                 if not already_exists:
#                     new_late_fees.append(
#                         {
#                             "kind": "late_fee",
#                             "due_date": due["overdue_since"],
#                             "remaining": late_fee_flat,
#                             "linked_emi_date": due["due_date"],
#                         }
#                     )
#         dues_queue.extend(new_late_fees)

#         # Step 4: add EMI only within tenure
#         if not is_recovery_phase:
#             dues_queue.append(
#                 {
#                     "kind": "emi",
#                     "due_date": cycle_due_date,
#                     "remaining": emi_amount,
#                     "overdue_since": None,
#                 }
#             )

#         # Step 5: compute total obligation
#         total_emi_due = sum(d["remaining"] for d in dues_queue if d["kind"] == "emi")
#         total_fee_due = sum(
#             d["remaining"] for d in dues_queue if d["kind"] in ("late_fee", "penal")
#         )
#         total_obligation = total_emi_due + total_fee_due

#         # Step 6: payment behavior
#         roll = rng.random()

#         if is_recovery_phase:

#             total_due = outstanding_balance + open_fees

#             if total_due <= 0:
#                 payment = 0

#             else:
#                 if profile == "good":
#                     if total_due > emi_amount * 2:
#                         payment = total_due * rng.uniform(0.4, 0.9)
#                     else:
#                         payment = total_due

#                 elif profile == "occasional_late":
#                     payment = total_due * rng.uniform(0.2, 0.6)

#                 elif profile == "struggling":
#                     payment = emi_amount * rng.uniform(0.2, 0.6)

#                 else:  # defaulter
#                     payment = emi_amount * rng.uniform(0, 0.2)

#         else:
#             ratio = outstanding_balance / emi_amount if emi_amount > 0 else 0

#             if profile == "good":

#                 if ratio > 2:
#                     payment = emi_amount * rng.uniform(1.0, 1.5)

#                 else:
#                     payment = outstanding_balance  # clear fully

#             elif profile == "occasional_late":

#                 if ratio > 2:
#                     payment = emi_amount * rng.uniform(0.7, 1.0)
#                 else:
#                     payment = outstanding_balance * rng.uniform(0.8, 1.0)

#             elif profile == "struggling":

#                 if ratio > 2:
#                     payment = emi_amount * rng.uniform(0.3, 0.7)
#                 else:
#                     payment = emi_amount * rng.uniform(0.5, 1.0)

#             else:  # defaulter

#                 if ratio > 2:
#                     payment = emi_amount * rng.uniform(0.1, 0.4)
#                 else:
#                     payment = outstanding_balance * rng.uniform(0.3, 0.8)

#         payment = round(payment, 2)

#         # Generate realistic paid_date
#         if payment == 0:
#             paid_date = None
#         else:
#             roll_time = rng.random()

#             prob_on_time = {
#                 "good": 0.9,
#                 "occasional_late": 0.7,
#                 "struggling": 0.5,
#                 "defaulter": 0.3,
#             }[profile]

#             if roll_time < prob_on_time:
#                 earliest_paid = max(disbursed_date, cycle_due_date - timedelta(days=2))
#                 paid_date = earliest_paid + timedelta(
#                     days=rng.randint(0, (cycle_due_date - earliest_paid).days)
#                 )
#             else:
#                 # Late payment
#                 paid_date = cycle_due_date + timedelta(days=rng.randint(1, 30))

#         # Sort dues (correct priority)
#         kind_priority = {"late_fee": 0, "penal": 1, "emi": 2}
#         dues_queue.sort(key=lambda d: (d["due_date"], kind_priority[d["kind"]]))

#         # FIFO allocation
#         available_payment = payment

#         paid_emi = 0.0
#         paid_late_fee = 0.0
#         paid_penal = 0.0
#         allocated_to_current_emi = 0.0

#         for due in dues_queue:
#             if available_payment <= 0:
#                 break
#             if due["remaining"] <= 0:
#                 continue

#             allocation = min(available_payment, due["remaining"])

#             due["remaining"] = round(due["remaining"] - allocation, 2)
#             if abs(due["remaining"]) < 0.01:
#                 due["remaining"] = 0

#             available_payment = round(available_payment - allocation, 2)

#             if due["kind"] == "emi":
#                 paid_emi += allocation

#                 if due["due_date"] == cycle_due_date:
#                     allocated_to_current_emi += allocation

#             elif due["kind"] == "late_fee":
#                 paid_late_fee += allocation
#             elif due["kind"] == "penal":
#                 paid_penal += allocation

#         # Identify current EMI
#         current_emi = next(
#             (
#                 d
#                 for d in dues_queue
#                 if d["kind"] == "emi" and d["due_date"] == cycle_due_date
#             ),
#             None,
#         )

#         open_fees = sum(
#             d["remaining"]
#             for d in dues_queue
#             if d["kind"] in ("late_fee", "penal") and d["remaining"] > 0
#         )

#         # Status logic (improved with paid_date awareness)

#         if is_recovery_phase:

#             # Recovery phase = no structured EMI cycle anymore

#             if payment == 0:
#                 status = "MISSED"

#             else:
#                 # pure allocation-based classification
#                 if paid_emi > 0 and (paid_late_fee > 0 or paid_penal > 0):
#                     status = "PARTIAL_RECOVERY"

#                 elif paid_emi > 0:
#                     status = "RECOVERY_PAYMENT"

#                 elif paid_late_fee > 0 or paid_penal > 0:
#                     status = "FEES_ONLY_PAYMENT"

#                 else:
#                     status = "MISSED"

#         else:
#             # TENURE PHASE
#             if current_emi is None:
#                 raise f"logic error"

#             elif payment == 0:
#                 status = "MISSED"

#             elif current_emi["remaining"] == 0:
#                 if paid_date and paid_date > cycle_due_date:
#                     status = "PAID_LATE"
#                 else:
#                     status = "PAID" if open_fees == 0 else "PAID_FEES_PENDING"

#             elif current_emi["remaining"] < emi_amount:
#                 status = "PARTIAL"

#             elif allocated_to_current_emi == 0 and payment > 0:
#                 status = "PAID_PREVIOUS_DUES"

#             else:
#                 status = "MISSED"

#         # Interest update
#         interest = outstanding_balance * monthly_rate

#         if payment > 0:
#             interest_paid = min(paid_emi, interest)
#             principal_paid = paid_emi - interest_paid
#             outstanding_balance -= principal_paid
#         else:
#             outstanding_balance += interest

#         outstanding_balance = round(max(0, outstanding_balance), 2)

#         # Cleanup
#         dues_queue = [d for d in dues_queue if d["remaining"] > 0]

#         # Rolling DPD (based on cycle, not today)
#         dpd_days = max(
#             (
#                 (cycle_due_date - d["overdue_since"]).days
#                 for d in dues_queue
#                 if d["kind"] == "emi" and d["remaining"] > 0 and d.get("overdue_since")
#             ),
#             default=0,
#         )
#         dpd_days = max(0, dpd_days)

#         # Save record
#         repayments.append(
#             {
#                 "due_date": cycle_due_date,
#                 "paid_date": paid_date,
#                 "amount_due": emi_amount if i < tenure_months else 0,
#                 "amount_paid": payment,
#                 "amount_paid_emi": round(paid_emi, 2),
#                 "amount_paid_late_fee": round(paid_late_fee, 2),
#                 "amount_paid_penal": round(paid_penal, 2),
#                 "dpd_days": dpd_days,
#                 "outstanding_fees": round(open_fees, 2),
#                 "outstanding_balance": outstanding_balance,
#                 "status": status,
#                 #                "profile": profile,
#             }
#         )

#         # stop if fully closed
#         if is_recovery_phase:
#             if outstanding_balance <= emi_amount * 0.1:
#                 break

#     return repayments


def generate_repayment_pattern_fifo(
    emi_amount,
    disbursed_date,
    tenure_months,
    principal,
    annual_interest_rate,
    late_fee_flat=500,
    grace_period_days=3,
    penal_annual_rate=0.02,
    seed=None,
):
    rng = random.Random(seed)

    monthly_rate = annual_interest_rate / (12 * 100)
    penal_daily_rate = penal_annual_rate / 365

    outstanding_balance = principal

    profile = rng.choices(
        ["good", "occasional_late", "struggling", "defaulter"], weights=[50, 25, 15, 10]
    )[0]

    risk = {
        "good": 0.05,
        "occasional_late": 0.20,
        "struggling": 0.50,
        "defaulter": 0.80,
    }[profile]

    repayments = []
    dues_queue = []

    max_extra_months = 12
    total_months = tenure_months + max_extra_months

    # reference date for UPCOMING logic
    today = date.today()

    for i in range(total_months):

        is_recovery_phase = i >= tenure_months
        cycle_due_date = disbursed_date + relativedelta(months=i + 1)
        prev_cycle_date = disbursed_date + relativedelta(months=i)
        days_in_cycle = (cycle_due_date - prev_cycle_date).days

        # Mark overdue_since only for EMI dues whose due date has passed
        for due in dues_queue:
            if (
                due["kind"] == "emi"
                and due["remaining"] > 0
                and due.get("overdue_since") is None
            ):
                grace_deadline = due["due_date"] + timedelta(days=grace_period_days)
                if cycle_due_date > grace_deadline:
                    due["overdue_since"] = grace_deadline + timedelta(days=1)

        # Penal entries (buffered)
        new_penal_entries = []
        for due in dues_queue:
            if (
                due["kind"] == "emi"
                and due["remaining"] > 0
                and due.get("overdue_since")
            ):
                penal_charge = round(
                    due["remaining"] * penal_daily_rate * days_in_cycle, 2
                )
                if penal_charge > 0:
                    new_penal_entries.append(
                        {
                            "kind": "penal",
                            "due_date": due["overdue_since"],
                            "remaining": penal_charge,
                            "linked_emi_date": due["due_date"],
                        }
                    )
        dues_queue.extend(new_penal_entries)

        # Late fee (one-time)
        new_late_fees = []
        for due in dues_queue:
            if (
                due["kind"] == "emi"
                and due["remaining"] > 0
                and due.get("overdue_since")
            ):
                already_exists = any(
                    d["kind"] == "late_fee" and d["linked_emi_date"] == due["due_date"]
                    for d in dues_queue
                )

                if not already_exists:
                    new_late_fees.append(
                        {
                            "kind": "late_fee",
                            "due_date": due["overdue_since"],
                            "remaining": late_fee_flat,
                            "linked_emi_date": due["due_date"],
                        }
                    )
        dues_queue.extend(new_late_fees)

        # Step 4: add EMI only within tenure
        if not is_recovery_phase:
            dues_queue.append(
                {
                    "kind": "emi",
                    "due_date": cycle_due_date,
                    "remaining": emi_amount,
                    "overdue_since": None,
                }
            )

        # Step 5: compute total obligation
        total_emi_due = sum(d["remaining"] for d in dues_queue if d["kind"] == "emi")
        total_fee_due = sum(
            d["remaining"] for d in dues_queue if d["kind"] in ("late_fee", "penal")
        )
        total_obligation = total_emi_due + total_fee_due

        # Step 6: payment behavior
        roll = rng.random()

        if is_recovery_phase:

            total_due = outstanding_balance + open_fees

            if total_due <= 0:
                payment = 0

            else:
                if profile == "good":
                    if total_due > emi_amount * 2:
                        payment = total_due * rng.uniform(0.4, 0.9)
                    else:
                        payment = total_due

                elif profile == "occasional_late":
                    payment = total_due * rng.uniform(0.2, 0.6)

                elif profile == "struggling":
                    payment = emi_amount * rng.uniform(0.2, 0.6)

                else:
                    payment = emi_amount * rng.uniform(0, 0.2)

        else:
            ratio = outstanding_balance / emi_amount if emi_amount > 0 else 0

            if profile == "good":
                if ratio > 2:
                    payment = emi_amount * rng.uniform(1.0, 1.5)
                else:
                    payment = outstanding_balance

            elif profile == "occasional_late":
                if ratio > 2:
                    payment = emi_amount * rng.uniform(0.7, 1.0)
                else:
                    payment = outstanding_balance * rng.uniform(0.8, 1.0)

            elif profile == "struggling":
                if ratio > 2:
                    payment = emi_amount * rng.uniform(0.3, 0.7)
                else:
                    payment = emi_amount * rng.uniform(0.5, 1.0)

            else:
                if ratio > 2:
                    payment = emi_amount * rng.uniform(0.1, 0.4)
                else:
                    payment = outstanding_balance * rng.uniform(0.3, 0.8)

        payment = round(payment, 2)

        # Generate realistic paid_date
        if payment == 0:
            paid_date = None
        else:
            roll_time = rng.random()

            prob_on_time = {
                "good": 0.9,
                "occasional_late": 0.7,
                "struggling": 0.5,
                "defaulter": 0.3,
            }[profile]

            if roll_time < prob_on_time:
                earliest_paid = max(disbursed_date, cycle_due_date - timedelta(days=2))
                paid_date = earliest_paid + timedelta(
                    days=rng.randint(0, (cycle_due_date - earliest_paid).days)
                )
            else:
                paid_date = cycle_due_date + timedelta(days=rng.randint(1, 30))

        # Sort dues (correct priority)
        kind_priority = {"late_fee": 0, "penal": 1, "emi": 2}
        dues_queue.sort(key=lambda d: (d["due_date"], kind_priority[d["kind"]]))

        # FIFO allocation
        available_payment = payment

        paid_emi = 0.0
        paid_late_fee = 0.0
        paid_penal = 0.0
        allocated_to_current_emi = 0.0

        for due in dues_queue:
            if available_payment <= 0:
                break
            if due["remaining"] <= 0:
                continue

            allocation = min(available_payment, due["remaining"])

            due["remaining"] = round(due["remaining"] - allocation, 2)
            if abs(due["remaining"]) < 0.01:
                due["remaining"] = 0

            available_payment = round(available_payment - allocation, 2)

            if due["kind"] == "emi":
                paid_emi += allocation
                if due["due_date"] == cycle_due_date:
                    allocated_to_current_emi += allocation

            elif due["kind"] == "late_fee":
                paid_late_fee += allocation
            elif due["kind"] == "penal":
                paid_penal += allocation

        current_emi = next(
            (
                d
                for d in dues_queue
                if d["kind"] == "emi" and d["due_date"] == cycle_due_date
            ),
            None,
        )

        open_fees = sum(
            d["remaining"]
            for d in dues_queue
            if d["kind"] in ("late_fee", "penal") and d["remaining"] > 0
        )

        # -------------------------
        # STATUS LOGIC (WITH UPCOMING)
        # -------------------------

        if is_recovery_phase:

            if payment == 0:
                status = "MISSED"

            else:
                if paid_emi > 0 and (paid_late_fee > 0 or paid_penal > 0):
                    status = "PARTIAL_RECOVERY"
                elif paid_emi > 0:
                    status = "RECOVERY_PAYMENT"
                elif paid_late_fee > 0 or paid_penal > 0:
                    status = "FEES_ONLY_PAYMENT"
                else:
                    status = "MISSED"

        else:

            # UPCOMING LOGIC ADDED HERE
            if cycle_due_date > today:
                status = "UPCOMING"

            elif current_emi is None:
                raise Exception("logic error")

            elif payment == 0:
                status = "MISSED"

            elif current_emi["remaining"] == 0:
                if paid_date and paid_date > cycle_due_date:
                    status = "PAID_LATE"
                else:
                    status = "PAID" if open_fees == 0 else "PAID_FEES_PENDING"

            elif current_emi["remaining"] < emi_amount:
                status = "PARTIAL"

            elif allocated_to_current_emi == 0:
                status = "PAID_PREVIOUS_DUES"

            else:
                status = "MISSED"

        # Interest update
        interest = outstanding_balance * monthly_rate

        if payment > 0:
            interest_paid = min(paid_emi, interest)
            principal_paid = paid_emi - interest_paid
            outstanding_balance -= principal_paid
        else:
            outstanding_balance += interest

        outstanding_balance = round(max(0, outstanding_balance), 2)

        # Cleanup
        dues_queue = [d for d in dues_queue if d["remaining"] > 0]

        # DPD
        dpd_days = max(
            (
                (cycle_due_date - d["overdue_since"]).days
                for d in dues_queue
                if d["kind"] == "emi" and d["remaining"] > 0 and d.get("overdue_since")
            ),
            default=0,
        )

        repayments.append(
            {
                "due_date": cycle_due_date,
                "paid_date": paid_date,
                "amount_due": emi_amount if i < tenure_months else 0,
                "amount_paid": payment,
                "amount_paid_emi": round(paid_emi, 2),
                "amount_paid_late_fee": round(paid_late_fee, 2),
                "amount_paid_penal": round(paid_penal, 2),
                "dpd_days": dpd_days,
                "outstanding_fees": round(open_fees, 2),
                "outstanding_balance": outstanding_balance,
                "status": status,
            }
        )

        if is_recovery_phase and outstanding_balance <= emi_amount * 0.1:
            break

    return repayments


# MAIN


def generate_and_insert():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    print("Starting data generation...\n")

    # 1. Insert Employees
    print("Inserting employees...")
    employee_ids = []

    for _ in range(NUM_EMPLOYEES):
        branch_name, city = random.choice(BRANCHES)
        cur.execute(
            """
            INSERT INTO employees
                (full_name, email, phone, role, branch_name, city, joined_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING employee_id
        """,
            (
                fake.name(),
                fake.unique.email(),
                fake.phone_number()[:15],
                random.choice(EMPLOYEE_ROLES),
                branch_name,
                city,
                fake.date_between(start_date="-6y", end_date="-6m"),
            ),
        )
        employee_ids.append(cur.fetchone()[0])

    print(f"{len(employee_ids)} employees inserted")

    # 2. Insert Customers
    print("Inserting customers...")
    customer_ids = []

    for _ in range(NUM_CUSTOMERS):
        branch_name, city = random.choice(BRANCHES)
        employment_type = random.choice(EMPLOYMENT_TYPES)

        # Income varies by employment type
        income_ranges = {
            "Government Employee": (400000, 1200000),
            "Business Owner": (600000, 5000000),
            "Self-Employed": (300000, 2000000),
            "Salaried": (300000, 1500000),
        }
        lo, hi = income_ranges[employment_type]
        income = random.randint(lo, hi)

        # Credit score loosely correlates with income
        base_score = 600 + int((income / 5000000) * 200)
        credit_score = min(900, max(300, base_score + random.randint(-80, 80)))

        cur.execute(
            """
            INSERT INTO customers
                (full_name, age, gender, phone, email,
                 city, branch_name, annual_income,
                 employment_type, credit_score, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING customer_id
        """,
            (
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
                fake.date_between(start_date="-4y", end_date="-1y"),
            ),
        )
        customer_ids.append(cur.fetchone()[0])

    print(f"{len(customer_ids)} customers inserted")

    # 3. Insert Loans + Repayments + Loan Assignments
    print("Inserting loans, repayments, assignments...")
    loan_count = 0
    repayment_count = 0

    # Allow some customers to have multiple loans
    customer_sample = random.choices(customer_ids, k=NUM_LOANS)

    for customer_id in customer_sample:

        # Fetch customer info for realistic loan sizing
        cur.execute(
            """
            SELECT annual_income, credit_score, branch_name
            FROM customers WHERE customer_id = %s
        """,
            (customer_id,),
        )
        income, credit_score, branch_name = cur.fetchone()

        # Pick a loan type
        loan_type, base_rate, max_tenure, max_amount = random.choice(LOAN_TYPES)

        # Loan amount based on income
        income_multiplier = 3 if loan_type == "Home" else 1
        max_eligible = min(float(max_amount), float(income) * income_multiplier)
        principal = round(random.uniform(max_eligible * 0.2, max_eligible * 0.8), -3)
        principal = max(50000.0, principal)

        # Better credit score = lower interest rate
        rate_adj = (750 - credit_score) / 100 * 0.5
        interest_rate = round(max(base_rate - 1.5, base_rate + rate_adj), 2)

        # Pick a realistic tenure
        valid_tenures = [
            t for t in [12, 24, 36, 48, 60, 84, 120, 180, 240] if t <= max_tenure
        ]
        tenure_months = random.choice(valid_tenures)

        emi_amount = calculate_emi(principal, interest_rate, tenure_months)
        disbursed_date = random_date(start_year=2021, end_year=2023)
        maturity_date = disbursed_date + relativedelta(months=tenure_months)
        purpose = random.choice(LOAN_PURPOSES.get(loan_type, ["General purpose"]))

        # Generate repayment history
        repayments = generate_repayment_pattern_fifo(
            emi_amount,
            disbursed_date,
            tenure_months,
            principal=principal,
            annual_interest_rate=interest_rate,
            seed=43,
        )

        # Derive loan status from repayment pattern
        loan_status = derive_loan_status(repayments)

        # Outstanding = principal minus estimated principal repaid
        total_paid = sum(r["amount_paid"] for r in repayments)
        outstanding = round(max(0.0, float(principal) - total_paid * 0.6), 2)
        if loan_status == "CLOSED":
            outstanding = 0.0

        # Insert loan
        cur.execute(
            """
            INSERT INTO loans
                (customer_id, loan_type, principal_amount, interest_rate,
                 tenure_months, emi_amount, disbursed_date, maturity_date,
                 outstanding_amount, status, purpose)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING loan_id
        """,
            (
                customer_id,
                loan_type,
                principal,
                interest_rate,
                tenure_months,
                emi_amount,
                disbursed_date,
                maturity_date,
                outstanding,
                loan_status,
                purpose,
            ),
        )
        loan_id = cur.fetchone()[0]
        loan_count += 1

        # Insert repayment records
        # for r in repayments:
        #     cur.execute(
        #         """
        #         INSERT INTO repayments
        #             (loan_id, due_date, paid_date, amount_due,
        #              amount_paid, dpd_days, status)
        #         VALUES (%s,%s,%s,%s,%s,%s,%s)
        #     """,
        #         (
        #             loan_id,
        #             r["due_date"],
        #             r["paid_date"],
        #             r["amount_due"],
        #             r["amount_paid"],
        #             r["dpd_days"],
        #             r["status"],
        #         ),
        #     )
        #     repayment_count += 1

        # Insert repayment records
        for r in repayments:
            cur.execute(
                """
                INSERT INTO repayments
                    (loan_id,
                    due_date,
                    paid_date,
                    amount_due,
                    amount_paid,
                    amount_paid_emi,
                    amount_paid_late_fee,
                    amount_paid_penal,
                    dpd_days,
                    outstanding_fees,
                    outstanding_balance,
                    status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    loan_id,
                    r["due_date"],
                    r["paid_date"],
                    r["amount_due"],
                    r["amount_paid"],
                    r["amount_paid_emi"],
                    r["amount_paid_late_fee"],
                    r["amount_paid_penal"],
                    r["dpd_days"],
                    r["outstanding_fees"],
                    r["outstanding_balance"],
                    r["status"],
                ),
            )
            repayment_count += 1

        # Assign a loan officer from the same branch if possible
        cur.execute(
            """
            SELECT employee_id FROM employees
            WHERE branch_name = %s AND is_active = TRUE
            ORDER BY RANDOM() LIMIT 1
        """,
            (branch_name,),
        )
        row = cur.fetchone()
        assigned_employee = row[0] if row else random.choice(employee_ids)

        cur.execute(
            """
            INSERT INTO loan_assignments
                (loan_id, employee_id, assigned_date, is_active)
            VALUES (%s, %s, %s, TRUE)
        """,
            (loan_id, assigned_employee, disbursed_date),
        )

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
'''

"""
Banking / Loan Analyst Assistant - Data Generation Script
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

from pathlib import Path
import os

DB_CONFIG = {
    "host": os.getenv("db_host"),
    "port": os.getenv("db_port"),
    "dbname": os.getenv("db_name"),
    "user": os.getenv("db_user"),
    "password": os.getenv("db_password"),
}


NUM_EMPLOYEES = 5
NUM_CUSTOMERS = 25
NUM_LOANS = 50

fake = Faker("en_IN")
random.seed(100)


BRANCHES = [
    ("Mumbai Main Branch", "Mumbai"),
    ("Mumbai Andheri Branch", "Mumbai"),
    ("Delhi Connaught Branch", "Delhi"),
    ("Delhi Dwarka Branch", "Delhi"),
    ("Pune Koregaon Branch", "Pune"),
    ("Bangalore MG Road Branch", "Bangalore"),
]

LOAN_TYPES = [
    ("Personal", 14.50, 60, 1500000),
    ("Home", 8.75, 240, 10000000),
    ("Business", 16.00, 84, 5000000),
    ("Vehicle", 11.50, 84, 2000000),
    ("Education", 10.00, 120, 2000000),
    ("Gold", 9.50, 24, 500000),
]

LOAN_PURPOSES = {
    "Personal": [
        "Medical emergency",
        "Wedding expenses",
        "Home renovation",
        "Travel",
        "Debt consolidation",
    ],
    "Home": ["Property purchase", "Home construction", "Property renovation"],
    "Business": [
        "Working capital",
        "Equipment purchase",
        "Business expansion",
        "Inventory",
    ],
    "Vehicle": ["Car purchase", "Bike purchase", "Commercial vehicle"],
    "Education": ["Undergraduate abroad", "Postgraduate India", "Professional course"],
    "Gold": ["Emergency funds", "Business need", "Agricultural purpose"],
}

EMPLOYMENT_TYPES = [
    "Salaried",
    "Self-Employed",
    "Business Owner",
    "Government Employee",
]
EMPLOYEE_ROLES = [
    "Loan Officer",
    "Loan Officer",
    "Loan Officer",
    "Branch Manager",
    "Credit Analyst",
]


def calculate_emi(principal, annual_rate, tenure_months):
    """Standard EMI formula: P * r * (1+r)^n / ((1+r)^n - 1)"""
    if annual_rate == 0:
        return round(principal / tenure_months, 2)
    r = annual_rate / (12 * 100)
    emi = principal * r * ((1 + r) ** tenure_months) / (((1 + r) ** tenure_months) - 1)
    return round(emi, 2)


def random_date(start_year=2021, end_year=2023):
    start = date(start_year, 1, 1)
    end = date(end_year, 12, 31)
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
        upcoming = [r for r in repayment_records if r["status"] == "UPCOMING"]
        if not upcoming:
            return "CLOSED"
        return "ACTIVE"


def generate_repayment_pattern_fifo(
    emi_amount,
    disbursed_date,
    tenure_months,
    principal,
    annual_interest_rate,
    late_fee_flat=500,
    grace_period_days=3,
    penal_annual_rate=0.02,
    seed=None,
):
    rng = random.Random(seed)

    monthly_rate = annual_interest_rate / (12 * 100)
    penal_daily_rate = penal_annual_rate / 365

    outstanding_balance = principal

    profile = rng.choices(
        ["good", "occasional_late", "struggling", "defaulter"],
        weights=[60, 25, 10, 5],
    )[0]

    # Probability of MISSING a payment entirely, per cycle
    miss_probability = {
        "good": 0.02,
        "occasional_late": 0.10,
        "struggling": 0.28,
        "defaulter": 0.55,
    }[profile]

    repayments = []
    dues_queue = []

    max_extra_months = 12
    total_months = tenure_months + max_extra_months

    today = date.today()

    for i in range(total_months):

        is_recovery_phase = i >= tenure_months
        cycle_due_date = disbursed_date + relativedelta(months=i + 1)
        prev_cycle_date = disbursed_date + relativedelta(months=i)
        days_in_cycle = (cycle_due_date - prev_cycle_date).days

        # Step 1: add EMI for current cycle (within tenure only)
        if not is_recovery_phase:
            dues_queue.append(
                {
                    "kind": "emi",
                    "due_date": cycle_due_date,
                    "remaining": emi_amount,
                    "overdue_since": None,
                }
            )

        # Step 2: mark overdue_since on past unpaid EMIs
        # Only past dues (not the one just added for this cycle) are eligible
        for due in dues_queue:
            if (
                due["kind"] == "emi"
                and due["remaining"] > 0
                and due.get("overdue_since") is None
                and due["due_date"] < cycle_due_date
            ):
                grace_deadline = due["due_date"] + timedelta(days=grace_period_days)
                if cycle_due_date > grace_deadline:
                    due["overdue_since"] = grace_deadline + timedelta(days=1)

        # Step 3: accrue penal charges on overdue EMIs
        new_penal_entries = []
        for due in dues_queue:
            if (
                due["kind"] == "emi"
                and due["remaining"] > 0
                and due.get("overdue_since")
            ):
                penal_charge = round(
                    due["remaining"] * penal_daily_rate * days_in_cycle, 2
                )
                if penal_charge > 0:
                    new_penal_entries.append(
                        {
                            "kind": "penal",
                            "due_date": due["overdue_since"],
                            "remaining": penal_charge,
                            "linked_emi_date": due["due_date"],
                        }
                    )
        dues_queue.extend(new_penal_entries)

        # Step 4: add one-time late fee per overdue EMI (if not already present)
        new_late_fees = []
        for due in dues_queue:
            if (
                due["kind"] == "emi"
                and due["remaining"] > 0
                and due.get("overdue_since")
            ):
                already_exists = any(
                    d["kind"] == "late_fee"
                    and d.get("linked_emi_date") == due["due_date"]
                    for d in dues_queue
                )
                if not already_exists:
                    new_late_fees.append(
                        {
                            "kind": "late_fee",
                            "due_date": due["overdue_since"],
                            "remaining": late_fee_flat,
                            "linked_emi_date": due["due_date"],
                        }
                    )
        dues_queue.extend(new_late_fees)

        # Step 5: compute open fees for recovery phase reference
        open_fees = sum(
            d["remaining"]
            for d in dues_queue
            if d["kind"] in ("late_fee", "penal") and d["remaining"] > 0
        )

        # Step 6: determine payment amount
        roll = rng.random()

        if is_recovery_phase:
            total_due = outstanding_balance + open_fees

            if total_due <= 0:
                payment = 0.0
            elif roll < miss_probability:
                payment = 0.0
            else:
                if profile == "good":
                    payment = total_due * rng.uniform(0.6, 1.0)
                elif profile == "occasional_late":
                    payment = total_due * rng.uniform(0.3, 0.8)
                elif profile == "struggling":
                    payment = emi_amount * rng.uniform(0.2, 0.6)
                else:
                    payment = emi_amount * rng.uniform(0.05, 0.3)

        else:
            # roll < miss_probability → full miss for this cycle
            if roll < miss_probability:
                payment = 0.0
            else:
                ratio = outstanding_balance / emi_amount if emi_amount > 0 else 0

                if profile == "good":
                    if ratio > 2:
                        payment = emi_amount * rng.uniform(1.0, 1.5)
                    else:
                        payment = outstanding_balance

                elif profile == "occasional_late":
                    if ratio > 2:
                        payment = emi_amount * rng.uniform(0.7, 1.0)
                    else:
                        payment = outstanding_balance * rng.uniform(0.8, 1.0)

                elif profile == "struggling":
                    if ratio > 2:
                        payment = emi_amount * rng.uniform(0.3, 0.7)
                    else:
                        payment = emi_amount * rng.uniform(0.5, 1.0)

                else:
                    if ratio > 2:
                        payment = emi_amount * rng.uniform(0.1, 0.4)
                    else:
                        payment = outstanding_balance * rng.uniform(0.3, 0.8)

        payment = round(payment, 2)

        # Step 7: generate realistic paid_date
        if payment == 0:
            paid_date = None
        else:
            prob_on_time = {
                "good": 0.90,
                "occasional_late": 0.65,
                "struggling": 0.45,
                "defaulter": 0.25,
            }[profile]

            roll_time = rng.random()
            if roll_time < prob_on_time:
                earliest_paid = max(disbursed_date, cycle_due_date - timedelta(days=2))
                delta = (cycle_due_date - earliest_paid).days
                paid_date = earliest_paid + timedelta(
                    days=rng.randint(0, max(0, delta))
                )
            else:
                paid_date = cycle_due_date + timedelta(days=rng.randint(1, 30))

        # Step 8: FIFO allocation (fees first, then oldest EMI)
        kind_priority = {"late_fee": 0, "penal": 1, "emi": 2}
        dues_queue.sort(key=lambda d: (d["due_date"], kind_priority[d["kind"]]))

        available_payment = payment

        paid_emi = 0.0
        paid_late_fee = 0.0
        paid_penal = 0.0
        allocated_to_current_emi = 0.0

        for due in dues_queue:
            if available_payment <= 0:
                break
            if due["remaining"] <= 0:
                continue

            allocation = min(available_payment, due["remaining"])
            due["remaining"] = round(due["remaining"] - allocation, 2)
            if abs(due["remaining"]) < 0.01:
                due["remaining"] = 0.0

            available_payment = round(available_payment - allocation, 2)

            if due["kind"] == "emi":
                paid_emi += allocation
                if due["due_date"] == cycle_due_date:
                    allocated_to_current_emi += allocation
            elif due["kind"] == "late_fee":
                paid_late_fee += allocation
            elif due["kind"] == "penal":
                paid_penal += allocation

        # Step 9: resolve current EMI entry and recompute open fees
        current_emi = next(
            (
                d
                for d in dues_queue
                if d["kind"] == "emi" and d["due_date"] == cycle_due_date
            ),
            None,
        )

        open_fees = sum(
            d["remaining"]
            for d in dues_queue
            if d["kind"] in ("late_fee", "penal") and d["remaining"] > 0
        )

        # Step 10: determine repayment status
        if is_recovery_phase:
            if payment == 0:
                status = "MISSED"
            elif paid_emi > 0 and (paid_late_fee > 0 or paid_penal > 0):
                status = "PARTIAL_RECOVERY"
            elif paid_emi > 0:
                status = "RECOVERY_PAYMENT"
            elif paid_late_fee > 0 or paid_penal > 0:
                status = "FEES_ONLY_PAYMENT"
            else:
                status = "MISSED"

        else:
            if cycle_due_date > today:
                status = "UPCOMING"

            elif current_emi is None:
                raise Exception(
                    "Logic error: current EMI entry missing from dues_queue"
                )

            elif payment == 0:
                status = "MISSED"

            elif current_emi["remaining"] == 0:
                if paid_date and paid_date > cycle_due_date:
                    status = "PAID_LATE"
                else:
                    status = "PAID" if open_fees == 0 else "PAID_FEES_PENDING"

            elif current_emi["remaining"] < emi_amount:
                status = "PARTIAL"

            elif allocated_to_current_emi == 0:
                status = "PAID_PREVIOUS_DUES"

            else:
                status = "MISSED"

        # Step 11: update outstanding balance
        interest = outstanding_balance * monthly_rate

        if payment > 0:
            interest_paid = min(paid_emi, interest)
            principal_paid = paid_emi - interest_paid
            outstanding_balance -= principal_paid
        else:
            outstanding_balance += interest

        outstanding_balance = round(max(0.0, outstanding_balance), 2)

        # Step 12: cleanup fully settled dues
        dues_queue = [d for d in dues_queue if d["remaining"] > 0]

        # Step 13: compute DPD
        dpd_days = max(
            (
                (cycle_due_date - d["overdue_since"]).days
                for d in dues_queue
                if d["kind"] == "emi" and d["remaining"] > 0 and d.get("overdue_since")
            ),
            default=0,
        )

        repayments.append(
            {
                "due_date": cycle_due_date,
                "paid_date": paid_date,
                "amount_due": emi_amount if i < tenure_months else 0,
                "amount_paid": payment,
                "amount_paid_emi": round(paid_emi, 2),
                "amount_paid_late_fee": round(paid_late_fee, 2),
                "amount_paid_penal": round(paid_penal, 2),
                "dpd_days": dpd_days,
                "outstanding_fees": round(open_fees, 2),
                "outstanding_balance": outstanding_balance,
                "status": status,
            }
        )

        # Exit recovery phase early if balance is negligible
        if is_recovery_phase and outstanding_balance <= emi_amount * 0.1:
            break

    return repayments


def generate_and_insert():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    print("Starting data generation...\n")

    # 1. Insert Employees
    print("Inserting employees...")
    employee_ids = []

    for _ in range(NUM_EMPLOYEES):
        branch_name, city = random.choice(BRANCHES)
        cur.execute(
            """
            INSERT INTO employees
                (full_name, email, phone, role, branch_name, city, joined_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING employee_id
            """,
            (
                fake.name(),
                fake.unique.email(),
                fake.phone_number()[:15],
                random.choice(EMPLOYEE_ROLES),
                branch_name,
                city,
                fake.date_between(start_date="-6y", end_date="-6m"),
            ),
        )
        employee_ids.append(cur.fetchone()[0])

    print(f"  {len(employee_ids)} employees inserted")

    # 2. Insert Customers
    print("Inserting customers...")
    customer_ids = []

    for _ in range(NUM_CUSTOMERS):
        branch_name, city = random.choice(BRANCHES)
        employment_type = random.choice(EMPLOYMENT_TYPES)

        income_ranges = {
            "Government Employee": (400000, 1200000),
            "Business Owner": (600000, 5000000),
            "Self-Employed": (300000, 2000000),
            "Salaried": (300000, 1500000),
        }
        lo, hi = income_ranges[employment_type]
        income = random.randint(lo, hi)

        base_score = 600 + int((income / 5000000) * 200)
        credit_score = min(900, max(300, base_score + random.randint(-80, 80)))

        cur.execute(
            """
            INSERT INTO customers
                (full_name, age, gender, phone, email,
                 city, branch_name, annual_income,
                 employment_type, credit_score, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING customer_id
            """,
            (
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
                fake.date_between(start_date="-4y", end_date="-1y"),
            ),
        )
        customer_ids.append(cur.fetchone()[0])

    print(f"  {len(customer_ids)} customers inserted")

    # 3. Insert Loans + Repayments + Loan Assignments
    print("Inserting loans, repayments, assignments...")
    loan_count = 0
    repayment_count = 0

    customer_sample = random.choices(customer_ids, k=NUM_LOANS)

    for customer_id in customer_sample:

        cur.execute(
            """
            SELECT annual_income, credit_score, branch_name
            FROM customers WHERE customer_id = %s
            """,
            (customer_id,),
        )
        income, credit_score, branch_name = cur.fetchone()

        loan_type, base_rate, max_tenure, max_amount = random.choice(LOAN_TYPES)

        income_multiplier = 3 if loan_type == "Home" else 1
        max_eligible = min(float(max_amount), float(income) * income_multiplier)
        principal = round(random.uniform(max_eligible * 0.2, max_eligible * 0.8), -3)
        principal = max(50000.0, principal)

        rate_adj = (750 - credit_score) / 100 * 0.5
        interest_rate = round(max(base_rate - 1.5, base_rate + rate_adj), 2)

        valid_tenures = [
            t for t in [12, 24, 36, 48, 60, 84, 120, 180, 240] if t <= max_tenure
        ]
        tenure_months = random.choice(valid_tenures)

        emi_amount = calculate_emi(principal, interest_rate, tenure_months)
        disbursed_date = random_date(start_year=2021, end_year=2023)
        maturity_date = disbursed_date + relativedelta(months=tenure_months)
        purpose = random.choice(LOAN_PURPOSES.get(loan_type, ["General purpose"]))

        repayments = generate_repayment_pattern_fifo(
            emi_amount,
            disbursed_date,
            tenure_months,
            principal=principal,
            annual_interest_rate=interest_rate,
            seed=random.randint(1, 99999),  # unique seed per loan for variety
        )

        loan_status = derive_loan_status(repayments)

        total_paid = sum(r["amount_paid"] for r in repayments)
        outstanding = round(max(0.0, float(principal) - total_paid * 0.6), 2)
        if loan_status == "CLOSED":
            outstanding = 0.0

        cur.execute(
            """
            INSERT INTO loans
                (customer_id, loan_type, principal_amount, interest_rate,
                 tenure_months, emi_amount, disbursed_date, maturity_date,
                 outstanding_amount, status, purpose)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING loan_id
            """,
            (
                customer_id,
                loan_type,
                principal,
                interest_rate,
                tenure_months,
                emi_amount,
                disbursed_date,
                maturity_date,
                outstanding,
                loan_status,
                purpose,
            ),
        )
        loan_id = cur.fetchone()[0]
        loan_count += 1

        for r in repayments:
            cur.execute(
                """
                INSERT INTO repayments
                    (loan_id,
                    due_date,
                    paid_date,
                    amount_due,
                    amount_paid,
                    amount_paid_emi,
                    amount_paid_late_fee,
                    amount_paid_penal,
                    dpd_days,
                    outstanding_fees,
                    outstanding_balance,
                    status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    loan_id,
                    r["due_date"],
                    r["paid_date"],
                    r["amount_due"],
                    r["amount_paid"],
                    r["amount_paid_emi"],
                    r["amount_paid_late_fee"],
                    r["amount_paid_penal"],
                    r["dpd_days"],
                    r["outstanding_fees"],
                    r["outstanding_balance"],
                    r["status"],
                ),
            )
            repayment_count += 1

        cur.execute(
            """
            SELECT employee_id FROM employees
            WHERE branch_name = %s AND is_active = TRUE
            ORDER BY RANDOM() LIMIT 1
            """,
            (branch_name,),
        )
        row = cur.fetchone()
        assigned_employee = row[0] if row else random.choice(employee_ids)

        cur.execute(
            """
            INSERT INTO loan_assignments
                (loan_id, employee_id, assigned_date, is_active)
            VALUES (%s, %s, %s, TRUE)
            """,
            (loan_id, assigned_employee, disbursed_date),
        )

    print(f"  {loan_count} loans inserted")
    print(f"  {repayment_count} repayment records inserted")
    print(f"  {loan_count} loan assignments inserted")

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
