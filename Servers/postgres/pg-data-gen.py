# """
# Banking / Loan Analyst Assistant - Data Generation Script
# ==========================================================
# Generates mock data and inserts into PostgreSQL.
# Matches 5-table schema: customers, employees, loans, repayments, loan_assignments

# Requirements:
#     pip install faker psycopg2-binary python-dateutil

# Usage:
#     1. Start PostgreSQL via docker compose --env-file .env.server up -d
#     2. Schema auto-runs on first start via docker-entrypoint-initdb.d
#     3. Run this script: python generate_data.py

# Known simplification:
#     Partial payments do not carry forward shortfall to next month's due amount.
#     In production, arrears would be tracked and added to subsequent EMI dues.
#     This simplification does not affect agent tool logic or architecture.
# """

# import random
# import psycopg2
# from faker import Faker
# from datetime import date, timedelta
# from dateutil.relativedelta import relativedelta
# import os

# DB_CONFIG = {
#     "host": os.getenv("db_host"),
#     "port": os.getenv("db_port"),
#     "dbname": os.getenv("db_name"),
#     "user": os.getenv("db_user"),
#     "password": os.getenv("db_password"),
# }

# NUM_EMPLOYEES = 5
# NUM_CUSTOMERS = 25
# NUM_LOANS = 50

# fake = Faker("en_IN")
# random.seed(100)

# BRANCHES = [
#     ("Mumbai Main Branch", "Mumbai"),
#     ("Mumbai Andheri Branch", "Mumbai"),
#     ("Delhi Connaught Branch", "Delhi"),
#     ("Delhi Dwarka Branch", "Delhi"),
#     ("Pune Koregaon Branch", "Pune"),
#     ("Bangalore MG Road Branch", "Bangalore"),
# ]

# LOAN_TYPES = [
#     ("Personal", 14.50, 60, 1500000),
#     ("Home", 8.75, 240, 10000000),
#     ("Business", 16.00, 84, 5000000),
#     ("Vehicle", 11.50, 84, 2000000),
#     ("Education", 10.00, 120, 2000000),
#     ("Gold", 9.50, 24, 500000),
# ]

# LOAN_PURPOSES = {
#     "Personal": [
#         "Medical emergency",
#         "Wedding expenses",
#         "Home renovation",
#         "Travel",
#         "Debt consolidation",
#     ],
#     "Home": ["Property purchase", "Home construction", "Property renovation"],
#     "Business": [
#         "Working capital",
#         "Equipment purchase",
#         "Business expansion",
#         "Inventory",
#     ],
#     "Vehicle": ["Car purchase", "Bike purchase", "Commercial vehicle"],
#     "Education": ["Undergraduate abroad", "Postgraduate India", "Professional course"],
#     "Gold": ["Emergency funds", "Business need", "Agricultural purpose"],
# }

# EMPLOYMENT_TYPES = [
#     "Salaried",
#     "Self-Employed",
#     "Business Owner",
#     "Government Employee",
# ]

# EMPLOYEE_ROLES = [
#     "Loan Officer",
#     "Loan Officer",
#     "Loan Officer",
#     "Branch Manager",
#     "Credit Analyst",
# ]


# def calculate_emi(principal, annual_rate, tenure_months):
#     """Standard EMI formula: P * r * (1+r)^n / ((1+r)^n - 1)"""
#     if annual_rate == 0:
#         return round(principal / tenure_months, 2)
#     r = annual_rate / (12 * 100)
#     emi = principal * r * ((1 + r) ** tenure_months) / (((1 + r) ** tenure_months) - 1)
#     return round(emi, 2)


# def random_date(start_year=2021, end_year=2023):
#     start = date(start_year, 1, 1)
#     end = date(end_year, 12, 31)
#     return start + timedelta(days=random.randint(0, (end - start).days))


# def derive_loan_status(repayment_records):
#     """
#     Derive loan status from repayment history.

#     Uses final outstanding_balance as the primary CLOSED signal.
#     Only MISSED records count toward delinquency — PARTIAL, PARTIAL_RECOVERY,
#     PAID_FEES_PENDING etc. are not treated as missed.
#     """
#     if not repayment_records:
#         return "ACTIVE"

#     final_balance = repayment_records[-1]["outstanding_balance"]
#     has_upcoming = any(r["status"] == "UPCOMING" for r in repayment_records)

#     if final_balance == 0.0 and not has_upcoming:
#         return "CLOSED"

#     missed_count = sum(1 for r in repayment_records if r["status"] == "MISSED")

#     if missed_count >= 4:
#         return "NPA"
#     elif missed_count >= 2:
#         return random.choice(["DEFAULTED", "OVERDUE"])
#     elif missed_count == 1:
#         return "OVERDUE"
#     else:
#         return "ACTIVE" if has_upcoming else "CLOSED"


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
#     """
#     Generate a month-by-month repayment history for a loan.

#     Design principles:
#     - Each cycle processes only past-due dates (cycle_due_date <= today).
#       Future cycles: one UPCOMING record is appended then the loop stops.
#     - Payment amount is decided per-cycle based on profile behaviour.
#     - FIFO allocation: oldest late_fee -> oldest penal -> oldest EMI.
#     - Outstanding balance follows standard amortisation: each cycle accrues
#       interest on the current balance; paid_emi is split into interest and
#       principal components and the principal portion reduces the balance.
#     - DPD = (cycle_due_date - oldest_unpaid_emi_due_date).days, only for
#       EMIs that have crossed the grace window. Resets to 0 once the cycle's
#       own EMI is fully cleared.
#     """
#     rng = random.Random(seed)

#     monthly_rate = annual_interest_rate / (12 * 100)
#     penal_daily_rate = penal_annual_rate / 365

#     outstanding_balance = float(principal)

#     profile = rng.choices(
#         ["good", "occasional_late", "struggling", "defaulter"],
#         weights=[60, 25, 10, 5],
#     )[0]

#     # Per-cycle probability of making zero payment
#     miss_prob = {
#         "good": 0.02,
#         "occasional_late": 0.10,
#         "struggling": 0.28,
#         "defaulter": 0.55,
#     }[profile]

#     # Probability that a non-zero payment arrives on or before due_date
#     on_time_prob = {
#         "good": 0.90,
#         "occasional_late": 0.65,
#         "struggling": 0.45,
#         "defaulter": 0.25,
#     }[profile]

#     repayments = []

#     # dues_queue entries:
#     #   kind          : "emi" | "late_fee" | "penal"
#     #   due_date      : date the charge was raised
#     #   remaining     : float amount still unpaid
#     #   overdue_since : date grace period ended (EMIs only; None until set)
#     #   linked_emi_date: due_date of the parent EMI (late_fee / penal only)
#     dues_queue = []

#     today = date.today()
#     max_extra_months = 12

#     for i in range(tenure_months + max_extra_months):

#         is_recovery_phase = i >= tenure_months
#         cycle_due_date = disbursed_date + relativedelta(months=i + 1)
#         prev_cycle_date = disbursed_date + relativedelta(months=i)
#         days_in_cycle = (cycle_due_date - prev_cycle_date).days

#         # ── Future cycle ────────────────────────────────────────────────────
#         # Tenure cycles in the future get a single UPCOMING record; the loop
#         # then stops. Recovery cycles in the future are simply skipped (break).
#         if cycle_due_date > today:
#             if not is_recovery_phase:
#                 open_fees_now = sum(
#                     d["remaining"]
#                     for d in dues_queue
#                     if d["kind"] in ("late_fee", "penal") and d["remaining"] > 0
#                 )
#                 repayments.append(
#                     {
#                         "due_date": cycle_due_date,
#                         "paid_date": None,
#                         "amount_due": emi_amount,
#                         "amount_paid": 0.0,
#                         "amount_paid_emi": 0.0,
#                         "amount_paid_late_fee": 0.0,
#                         "amount_paid_penal": 0.0,
#                         "dpd_days": 0,
#                         "outstanding_fees": round(open_fees_now, 2),
#                         "outstanding_balance": round(outstanding_balance, 2),
#                         "status": "UPCOMING",
#                     }
#                 )
#             break

#         # ── Nothing left to recover ─────────────────────────────────────────
#         if is_recovery_phase and outstanding_balance == 0.0 and not dues_queue:
#             break

#         # ── Step 1: add this cycle's EMI to the queue (tenure only) ─────────
#         if not is_recovery_phase:
#             dues_queue.append(
#                 {
#                     "kind": "emi",
#                     "due_date": cycle_due_date,
#                     "remaining": emi_amount,
#                     "overdue_since": None,
#                 }
#             )

#         # ── Step 2: mark overdue_since on unpaid EMIs from previous cycles ──
#         # An EMI is overdue once the grace window of its own due_date has
#         # passed as of the current cycle date.
#         for due in dues_queue:
#             if (
#                 due["kind"] == "emi"
#                 and due["remaining"] > 0
#                 and due["overdue_since"] is None
#                 and due["due_date"] < cycle_due_date
#             ):
#                 grace_end = due["due_date"] + timedelta(days=grace_period_days)
#                 if cycle_due_date > grace_end:
#                     due["overdue_since"] = grace_end + timedelta(days=1)

#         # ── Step 3: accrue penal interest on each overdue EMI ───────────────
#         new_penals = []
#         for due in dues_queue:
#             if due["kind"] == "emi" and due["remaining"] > 0 and due["overdue_since"]:
#                 charge = round(due["remaining"] * penal_daily_rate * days_in_cycle, 2)
#                 if charge > 0:
#                     new_penals.append(
#                         {
#                             "kind": "penal",
#                             "due_date": due["overdue_since"],
#                             "remaining": charge,
#                             "linked_emi_date": due["due_date"],
#                         }
#                     )
#         dues_queue.extend(new_penals)

#         # ── Step 4: add one-time late fee per overdue EMI ───────────────────
#         new_late_fees = []
#         for due in dues_queue:
#             if due["kind"] == "emi" and due["remaining"] > 0 and due["overdue_since"]:
#                 already = any(
#                     d["kind"] == "late_fee"
#                     and d.get("linked_emi_date") == due["due_date"]
#                     for d in dues_queue
#                 )
#                 if not already:
#                     new_late_fees.append(
#                         {
#                             "kind": "late_fee",
#                             "due_date": due["overdue_since"],
#                             "remaining": late_fee_flat,
#                             "linked_emi_date": due["due_date"],
#                         }
#                     )
#         dues_queue.extend(new_late_fees)

#         # ── Step 5: compute open fees before this cycle's payment ───────────
#         open_fees = sum(
#             d["remaining"]
#             for d in dues_queue
#             if d["kind"] in ("late_fee", "penal") and d["remaining"] > 0
#         )

#         # ── Step 6: decide payment amount ───────────────────────────────────
#         # Payment is always sized relative to emi_amount so it stays realistic
#         # regardless of the cumulative outstanding_balance magnitude.
#         roll = rng.random()

#         if roll < miss_prob:
#             payment = 0.0
#         else:
#             if is_recovery_phase:
#                 # In recovery the customer tries to chip away at remaining debt.
#                 total_due = outstanding_balance + open_fees
#                 if total_due <= 0:
#                     payment = 0.0
#                 else:
#                     small_threshold = max(emi_amount * 1.5, 5000.0)
#                     if total_due <= small_threshold:
#                         payment = total_due
#                     elif profile == "good":
#                         payment = total_due * rng.uniform(0.6, 1.0)
#                     elif profile == "occasional_late":
#                         payment = total_due * rng.uniform(0.3, 0.7)
#                     elif profile == "struggling":
#                         payment = emi_amount * rng.uniform(0.2, 0.5)
#                     else:
#                         payment = emi_amount * rng.uniform(0.05, 0.25)
#                     payment = min(payment, total_due)
#             else:
#                 if profile == "good":
#                     payment = emi_amount * rng.uniform(1.0, 1.2)
#                 elif profile == "occasional_late":
#                     payment = emi_amount * rng.uniform(0.8, 1.0)
#                 elif profile == "struggling":
#                     payment = emi_amount * rng.uniform(0.4, 0.9)
#                 else:
#                     payment = emi_amount * rng.uniform(0.1, 0.5)

#         payment = round(payment, 2)

#         # ── Step 7: generate paid_date ───────────────────────────────────────
#         if payment == 0.0:
#             paid_date = None
#         else:
#             if rng.random() < on_time_prob:
#                 earliest = max(disbursed_date, cycle_due_date - timedelta(days=2))
#                 delta = max(0, (cycle_due_date - earliest).days)
#                 paid_date = earliest + timedelta(days=rng.randint(0, delta))
#             else:
#                 paid_date = cycle_due_date + timedelta(days=rng.randint(1, 30))

#         # ── Step 8: FIFO allocation ──────────────────────────────────────────
#         # Priority order within the same due_date: late_fee -> penal -> emi.
#         # Across due_dates: oldest first.
#         kind_priority = {"late_fee": 0, "penal": 1, "emi": 2}
#         dues_queue.sort(key=lambda d: (d["due_date"], kind_priority[d["kind"]]))

#         available = payment
#         paid_emi = 0.0
#         paid_late_fee = 0.0
#         paid_penal = 0.0
#         allocated_to_current_emi = 0.0

#         for due in dues_queue:
#             if available <= 0:
#                 break
#             if due["remaining"] <= 0:
#                 continue
#             alloc = min(available, due["remaining"])
#             due["remaining"] = round(due["remaining"] - alloc, 2)
#             if due["remaining"] < 0.01:
#                 due["remaining"] = 0.0
#             available = round(available - alloc, 2)

#             if due["kind"] == "emi":
#                 paid_emi += alloc
#                 if due["due_date"] == cycle_due_date:
#                     allocated_to_current_emi += alloc
#             elif due["kind"] == "late_fee":
#                 paid_late_fee += alloc
#             elif due["kind"] == "penal":
#                 paid_penal += alloc

#         # ── Step 9: locate current EMI entry; recompute open fees ───────────
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

#         # ── Step 10: determine record status ────────────────────────────────
#         if is_recovery_phase:
#             if payment == 0.0:
#                 status = "MISSED"
#             elif paid_emi > 0 and (paid_late_fee > 0 or paid_penal > 0):
#                 status = "PARTIAL_RECOVERY"
#             elif paid_emi > 0:
#                 status = "RECOVERY_PAYMENT"
#             elif paid_late_fee > 0 or paid_penal > 0:
#                 status = "FEES_ONLY_PAYMENT"
#             else:
#                 status = "MISSED"
#         else:
#             if current_emi is None:
#                 raise Exception("Logic error: current EMI missing from dues_queue")
#             if payment == 0.0:
#                 status = "MISSED"
#             elif current_emi["remaining"] == 0.0:
#                 if paid_date and paid_date > cycle_due_date:
#                     status = "PAID_LATE"
#                 elif open_fees > 0:
#                     status = "PAID_FEES_PENDING"
#                 else:
#                     status = "PAID"
#             elif current_emi["remaining"] < emi_amount:
#                 status = "PARTIAL"
#             elif allocated_to_current_emi == 0.0 and paid_emi > 0:
#                 status = "PAID_PREVIOUS_DUES"
#             else:
#                 status = "MISSED"

#         # ── Step 11: update outstanding balance via amortisation ─────────────
#         # Interest accrues on the current balance each cycle. Paid EMI amount
#         # is first applied to interest; any remainder reduces principal.
#         # On a missed cycle the unpaid interest is capitalised (added back).
#         interest_this_cycle = round(outstanding_balance * monthly_rate, 2)

#         if payment > 0 and paid_emi > 0:
#             interest_covered = min(paid_emi, interest_this_cycle)
#             principal_paid = max(0.0, paid_emi - interest_covered)
#             outstanding_balance = outstanding_balance - principal_paid
#         else:
#             # Missed or fees-only: capitalise interest
#             outstanding_balance = outstanding_balance + interest_this_cycle

#         outstanding_balance = round(max(0.0, outstanding_balance), 2)

#         # ── Step 12: clean up fully settled dues ────────────────────────────
#         dues_queue = [d for d in dues_queue if d["remaining"] > 0]

#         # ── Step 13: compute DPD ─────────────────────────────────────────────
#         # DPD = (this cycle's due_date) - (oldest still-unpaid EMI's due_date).
#         # Only EMIs that have crossed the grace window (overdue_since is set)
#         # contribute. Resets to 0 the moment the current cycle's EMI is cleared.
#         if status in ("UPCOMING", "PAID", "PAID_LATE", "PAID_FEES_PENDING"):
#             dpd_days = 0
#         else:
#             overdue_emi_dates = [
#                 d["due_date"]
#                 for d in dues_queue
#                 if d["kind"] == "emi"
#                 and d["remaining"] > 0
#                 and d["overdue_since"] is not None
#             ]
#             if overdue_emi_dates:
#                 dpd_days = max(0, (cycle_due_date - min(overdue_emi_dates)).days)
#             else:
#                 dpd_days = 0

#         repayments.append(
#             {
#                 "due_date": cycle_due_date,
#                 "paid_date": paid_date,
#                 "amount_due": emi_amount if not is_recovery_phase else 0,
#                 "amount_paid": payment,
#                 "amount_paid_emi": round(paid_emi, 2),
#                 "amount_paid_late_fee": round(paid_late_fee, 2),
#                 "amount_paid_penal": round(paid_penal, 2),
#                 "dpd_days": dpd_days,
#                 "outstanding_fees": round(open_fees, 2),
#                 "outstanding_balance": outstanding_balance,
#                 "status": status,
#             }
#         )

#         if is_recovery_phase and outstanding_balance == 0.0 and not dues_queue:
#             break

#     return repayments


# def generate_and_insert():
#     conn = psycopg2.connect(**DB_CONFIG)
#     cur = conn.cursor()
#     print("Starting data generation...\n")

#     print("Inserting employees...")
#     employee_ids = []

#     for _ in range(NUM_EMPLOYEES):
#         branch_name, city = random.choice(BRANCHES)
#         cur.execute(
#             """
#             INSERT INTO employees
#                 (full_name, email, phone, role, branch_name, city, joined_date)
#             VALUES (%s, %s, %s, %s, %s, %s, %s)
#             RETURNING employee_id
#             """,
#             (
#                 fake.name(),
#                 fake.unique.email(),
#                 fake.phone_number()[:15],
#                 random.choice(EMPLOYEE_ROLES),
#                 branch_name,
#                 city,
#                 fake.date_between(start_date="-6y", end_date="-6m"),
#             ),
#         )
#         employee_ids.append(cur.fetchone()[0])

#     print(f"  {len(employee_ids)} employees inserted")

#     print("Inserting customers...")
#     customer_ids = []

#     for _ in range(NUM_CUSTOMERS):
#         branch_name, city = random.choice(BRANCHES)
#         employment_type = random.choice(EMPLOYMENT_TYPES)

#         income_ranges = {
#             "Government Employee": (400000, 1200000),
#             "Business Owner": (600000, 5000000),
#             "Self-Employed": (300000, 2000000),
#             "Salaried": (300000, 1500000),
#         }
#         lo, hi = income_ranges[employment_type]
#         income = random.randint(lo, hi)

#         base_score = 600 + int((income / 5000000) * 200)
#         credit_score = min(900, max(300, base_score + random.randint(-80, 80)))

#         cur.execute(
#             """
#             INSERT INTO customers
#                 (full_name, age, gender, phone, email,
#                  city, branch_name, annual_income,
#                  employment_type, credit_score, created_at)
#             VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
#             RETURNING customer_id
#             """,
#             (
#                 fake.name(),
#                 random.randint(22, 62),
#                 random.choice(["Male", "Female"]),
#                 fake.phone_number()[:15],
#                 fake.email(),
#                 city,
#                 branch_name,
#                 income,
#                 employment_type,
#                 credit_score,
#                 fake.date_between(start_date="-4y", end_date="-1y"),
#             ),
#         )
#         customer_ids.append(cur.fetchone()[0])

#     print(f"  {len(customer_ids)} customers inserted")

#     print("Inserting loans, repayments, assignments...")
#     loan_count = 0
#     repayment_count = 0

#     # Draw all loan seeds upfront so Faker/random calls inside the loop do
#     # not shift which seed each loan gets — prevents profile clustering by city.
#     customer_sample = random.choices(customer_ids, k=NUM_LOANS)
#     loan_seeds = [random.randint(1, 9_999_999) for _ in range(NUM_LOANS)]

#     for customer_id, loan_seed in zip(customer_sample, loan_seeds):

#         cur.execute(
#             """
#             SELECT annual_income, credit_score, branch_name
#             FROM customers WHERE customer_id = %s
#             """,
#             (customer_id,),
#         )
#         income, credit_score, branch_name = cur.fetchone()

#         loan_type, base_rate, max_tenure, max_amount = random.choice(LOAN_TYPES)

#         income_multiplier = 3 if loan_type == "Home" else 1
#         max_eligible = min(float(max_amount), float(income) * income_multiplier)
#         principal = round(random.uniform(max_eligible * 0.2, max_eligible * 0.8), -3)
#         principal = max(50000.0, principal)

#         rate_adj = (750 - credit_score) / 100 * 0.5
#         interest_rate = round(max(base_rate - 1.5, base_rate + rate_adj), 2)

#         valid_tenures = [
#             t for t in [12, 24, 36, 48, 60, 84, 120, 180, 240] if t <= max_tenure
#         ]
#         tenure_months = random.choice(valid_tenures)

#         emi_amount = calculate_emi(principal, interest_rate, tenure_months)
#         disbursed_date = random_date(start_year=2021, end_year=2023)
#         maturity_date = disbursed_date + relativedelta(months=tenure_months)
#         purpose = random.choice(LOAN_PURPOSES.get(loan_type, ["General purpose"]))

#         repayments = generate_repayment_pattern_fifo(
#             emi_amount,
#             disbursed_date,
#             tenure_months,
#             principal=principal,
#             annual_interest_rate=interest_rate,
#             seed=loan_seed,
#         )

#         outstanding = repayments[-1]["outstanding_balance"] if repayments else principal

#         if outstanding <= 0.0:
#             outstanding = 0.0
#             loan_status = "CLOSED"
#         else:
#             loan_status = derive_loan_status(repayments)

#         cur.execute(
#             """
#             INSERT INTO loans
#                 (customer_id, loan_type, principal_amount, interest_rate,
#                  tenure_months, emi_amount, disbursed_date, maturity_date,
#                  outstanding_amount, status, purpose)
#             VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
#             RETURNING loan_id
#             """,
#             (
#                 customer_id,
#                 loan_type,
#                 principal,
#                 interest_rate,
#                 tenure_months,
#                 emi_amount,
#                 disbursed_date,
#                 maturity_date,
#                 outstanding,
#                 loan_status,
#                 purpose,
#             ),
#         )
#         loan_id = cur.fetchone()[0]
#         loan_count += 1

#         for r in repayments:
#             cur.execute(
#                 """
#                 INSERT INTO repayments
#                     (loan_id,
#                      due_date,
#                      paid_date,
#                      amount_due,
#                      amount_paid,
#                      amount_paid_emi,
#                      amount_paid_late_fee,
#                      amount_paid_penal,
#                      dpd_days,
#                      outstanding_fees,
#                      outstanding_balance,
#                      status)
#                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
#                 """,
#                 (
#                     loan_id,
#                     r["due_date"],
#                     r["paid_date"],
#                     r["amount_due"],
#                     r["amount_paid"],
#                     r["amount_paid_emi"],
#                     r["amount_paid_late_fee"],
#                     r["amount_paid_penal"],
#                     r["dpd_days"],
#                     r["outstanding_fees"],
#                     r["outstanding_balance"],
#                     r["status"],
#                 ),
#             )
#             repayment_count += 1

#         cur.execute(
#             """
#             SELECT employee_id FROM employees
#             WHERE branch_name = %s AND is_active = TRUE
#             ORDER BY RANDOM() LIMIT 1
#             """,
#             (branch_name,),
#         )
#         row = cur.fetchone()
#         assigned_employee = row[0] if row else random.choice(employee_ids)

#         cur.execute(
#             """
#             INSERT INTO loan_assignments
#                 (loan_id, employee_id, assigned_date, is_active)
#             VALUES (%s, %s, %s, TRUE)
#             """,
#             (loan_id, assigned_employee, disbursed_date),
#         )

#     print(f"  {loan_count} loans inserted")
#     print(f"  {repayment_count} repayment records inserted")
#     print(f"  {loan_count} loan assignments inserted")

#     conn.commit()
#     cur.close()
#     conn.close()

#     print(f"""
# Data generation complete!

# Summary:
#   Employees:        {NUM_EMPLOYEES}
#   Customers:        {NUM_CUSTOMERS}
#   Loans:            {loan_count}
#   Repayments:       {repayment_count}
#   Loan Assignments: {loan_count}
#     """)


# if __name__ == "__main__":
#     generate_and_insert()


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

Known simplification:
    Partial payments do not carry forward shortfall to next month's due amount.
    In production, arrears would be tracked and added to subsequent EMI dues.
    This simplification does not affect agent tool logic or architecture.
"""

import random
import psycopg2
from faker import Faker
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
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
    """
    Derive loan status from repayment history.

    Uses final outstanding_balance as the primary CLOSED signal.
    Only MISSED records count toward delinquency.
    """
    if not repayment_records:
        return "ACTIVE"

    final_balance = repayment_records[-1]["outstanding_balance"]
    has_upcoming = any(r["status"] == "UPCOMING" for r in repayment_records)

    if final_balance == 0.0 and not has_upcoming:
        return "CLOSED"

    missed_count = sum(1 for r in repayment_records if r["status"] == "MISSED")

    if missed_count >= 4:
        return "NPA"
    elif missed_count >= 2:
        return random.choice(["DEFAULTED", "OVERDUE"])
    elif missed_count == 1:
        return "OVERDUE"
    else:
        return "ACTIVE" if has_upcoming else "CLOSED"


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
    """
    Generate a month-by-month repayment history for a loan.

    Payment behaviour per profile:
      good            - always pays full queue (prev arrears + fees + current EMI)
      occasional_late - always pays full queue but may pay late
      struggling      - pays 40-85% of emi_amount; backlog grows
      defaulter       - pays 10-45% of emi_amount; severe backlog

    FIFO allocation order: late_fee -> penal -> emi (oldest first within each).
    Since good/occasional_late pay >= full queue, FIFO order does not affect
    whether the current EMI gets cleared — everything gets cleared regardless.
    For struggling/defaulter, fees eat first so current EMI is often left partial.

    Status rules (tenure phase):
      UPCOMING          - cycle_due_date > today
      MISSED            - payment == 0
      PAID              - current EMI fully cleared, no open fees, paid on time
      PAID_LATE         - current EMI fully cleared, no open fees, paid late
      PAID_FEES_PENDING - current EMI fully cleared, fees still open
      PARTIAL           - current EMI partially cleared (remaining < emi_amount)
      PAID_PREVIOUS_DUES- payment > 0 but went entirely to arrears, current EMI untouched
      FEES_ONLY_PAYMENT - payment > 0 but went entirely to fees, no EMI cleared
    """
    rng = random.Random(seed)

    monthly_rate = annual_interest_rate / (12 * 100)
    penal_daily_rate = penal_annual_rate / 365

    outstanding_balance = float(principal)

    profile = rng.choices(
        ["good", "occasional_late", "struggling", "defaulter"],
        weights=[60, 25, 10, 5],
    )[0]

    miss_prob = {
        "good": 0.02,
        "occasional_late": 0.08,
        "struggling": 0.28,
        "defaulter": 0.55,
    }[profile]

    on_time_prob = {
        "good": 0.90,
        "occasional_late": 0.55,
        "struggling": 0.40,
        "defaulter": 0.20,
    }[profile]

    repayments = []
    dues_queue = []
    today = date.today()

    for i in range(tenure_months + 12):

        is_recovery_phase = i >= tenure_months
        cycle_due_date = disbursed_date + relativedelta(months=i + 1)
        prev_cycle_date = disbursed_date + relativedelta(months=i)
        days_in_cycle = (cycle_due_date - prev_cycle_date).days

        # Future cycles: append one UPCOMING record then stop.
        # Recovery phase future cycles just stop.
        if cycle_due_date > today:
            if not is_recovery_phase:
                open_fees_now = sum(
                    d["remaining"]
                    for d in dues_queue
                    if d["kind"] in ("late_fee", "penal") and d["remaining"] > 0
                )
                repayments.append(
                    {
                        "due_date": cycle_due_date,
                        "paid_date": None,
                        "amount_due": round(emi_amount + open_fees_now, 2),
                        "amount_paid": 0.0,
                        "amount_paid_emi": 0.0,
                        "amount_paid_late_fee": 0.0,
                        "amount_paid_penal": 0.0,
                        "dpd_days": 0,
                        "outstanding_fees": round(open_fees_now, 2),
                        "outstanding_balance": round(outstanding_balance, 2),
                        "status": "UPCOMING",
                    }
                )
            break

        if is_recovery_phase and outstanding_balance == 0.0 and not dues_queue:
            break

        # Step 1: add current cycle EMI (tenure only)
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
        for due in dues_queue:
            if (
                due["kind"] == "emi"
                and due["remaining"] > 0
                and due["overdue_since"] is None
                and due["due_date"] < cycle_due_date
            ):
                grace_end = due["due_date"] + timedelta(days=grace_period_days)
                if cycle_due_date > grace_end:
                    due["overdue_since"] = grace_end + timedelta(days=1)

        # Step 3: accrue penal interest on overdue EMIs
        new_penals = []
        for due in dues_queue:
            if due["kind"] == "emi" and due["remaining"] > 0 and due["overdue_since"]:
                charge = round(due["remaining"] * penal_daily_rate * days_in_cycle, 2)
                if charge > 0:
                    new_penals.append(
                        {
                            "kind": "penal",
                            "due_date": due["overdue_since"],
                            "remaining": charge,
                            "linked_emi_date": due["due_date"],
                        }
                    )
        dues_queue.extend(new_penals)

        # Step 4: add one-time late fee per overdue EMI
        new_late_fees = []
        for due in dues_queue:
            if due["kind"] == "emi" and due["remaining"] > 0 and due["overdue_since"]:
                already = any(
                    d["kind"] == "late_fee"
                    and d.get("linked_emi_date") == due["due_date"]
                    for d in dues_queue
                )
                if not already:
                    new_late_fees.append(
                        {
                            "kind": "late_fee",
                            "due_date": due["overdue_since"],
                            "remaining": late_fee_flat,
                            "linked_emi_date": due["due_date"],
                        }
                    )
        dues_queue.extend(new_late_fees)

        # Step 5: total obligation before payment
        # amount_due_pre_alloc is the full queue: arrears + fees + current EMI.
        # Used for payment sizing and stored as amount_due on the record.
        amount_due_pre_alloc = round(
            sum(d["remaining"] for d in dues_queue if d["remaining"] > 0), 2
        )

        open_fees = sum(
            d["remaining"]
            for d in dues_queue
            if d["kind"] in ("late_fee", "penal") and d["remaining"] > 0
        )

        # Step 6: decide payment amount
        roll = rng.random()

        if roll < miss_prob:
            payment = 0.0
        else:
            if is_recovery_phase:
                total_due = outstanding_balance + open_fees
                if total_due <= 0:
                    payment = 0.0
                else:
                    small_threshold = max(emi_amount * 1.5, 5000.0)
                    if total_due <= small_threshold:
                        payment = total_due
                    elif profile == "good":
                        payment = total_due * rng.uniform(0.6, 1.0)
                    elif profile == "occasional_late":
                        payment = total_due * rng.uniform(0.3, 0.7)
                    elif profile == "struggling":
                        payment = emi_amount * rng.uniform(0.2, 0.5)
                    else:
                        payment = emi_amount * rng.uniform(0.05, 0.25)
                    payment = min(payment, total_due)
            else:
                if profile == "good":
                    # Pays entire queue: arrears + fees + current EMI.
                    # Since payment >= amount_due_pre_alloc, FIFO clears
                    # everything, current_emi["remaining"] becomes 0 -> PAID.
                    payment = amount_due_pre_alloc

                elif profile == "occasional_late":
                    # Same as good — clears the full queue.
                    # Lateness is captured via paid_date, not underpayment.
                    payment = amount_due_pre_alloc

                elif profile == "struggling":
                    # Pays a fraction of one EMI. Fees eat first via FIFO so
                    # current EMI often stays partially or fully unpaid.
                    payment = emi_amount * rng.uniform(0.4, 0.85)

                else:  # defaulter
                    payment = emi_amount * rng.uniform(0.1, 0.45)

        payment = round(payment, 2)

        # Step 7: generate paid_date
        if payment == 0.0:
            paid_date = None
        else:
            if rng.random() < on_time_prob:
                earliest = max(disbursed_date, cycle_due_date - timedelta(days=2))
                delta = max(0, (cycle_due_date - earliest).days)
                paid_date = earliest + timedelta(days=rng.randint(0, delta))
            else:
                paid_date = cycle_due_date + timedelta(days=rng.randint(1, 30))

        # Step 8: FIFO allocation — oldest late_fee -> oldest penal -> oldest EMI
        kind_priority = {"late_fee": 0, "penal": 1, "emi": 2}
        dues_queue.sort(key=lambda d: (d["due_date"], kind_priority[d["kind"]]))

        available = payment
        paid_emi = 0.0
        paid_late_fee = 0.0
        paid_penal = 0.0
        allocated_to_current_emi = 0.0

        for due in dues_queue:
            if available <= 0:
                break
            if due["remaining"] <= 0:
                continue
            alloc = min(available, due["remaining"])
            due["remaining"] = round(due["remaining"] - alloc, 2)
            if due["remaining"] < 0.01:
                due["remaining"] = 0.0
            available = round(available - alloc, 2)

            if due["kind"] == "emi":
                paid_emi += alloc
                if due["due_date"] == cycle_due_date:
                    allocated_to_current_emi += alloc
            elif due["kind"] == "late_fee":
                paid_late_fee += alloc
            elif due["kind"] == "penal":
                paid_penal += alloc

        # Step 9: locate current EMI; recompute open fees post-payment
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

        # Step 10: determine status
        if is_recovery_phase:
            if payment == 0.0:
                status = "MISSED"
            elif paid_emi > 0 and (paid_late_fee > 0 or paid_penal > 0):
                status = "PARTIAL_RECOVERY"
            elif paid_emi > 0:
                status = "RECOVERY_PAYMENT"
            elif paid_late_fee > 0 or paid_penal > 0:
                status = "FEES_ONLY_PAYMENT"
            elif payment > 0:
                # dues_queue was empty; payment reduces balance directly
                status = "RECOVERY_PAYMENT"
            else:
                status = "MISSED"
        else:
            if current_emi is None:
                raise Exception("Logic error: current EMI missing from dues_queue")

            if payment == 0.0:
                status = "MISSED"

            elif current_emi["remaining"] == 0.0:
                # Current EMI fully cleared
                if paid_date and paid_date > cycle_due_date:
                    status = "PAID_LATE"
                elif open_fees > 0:
                    status = "PAID_FEES_PENDING"
                else:
                    status = "PAID"

            elif current_emi["remaining"] < emi_amount:
                # Current EMI partially cleared
                status = "PARTIAL"

            elif paid_emi > 0 and allocated_to_current_emi == 0.0:
                # Payment went to older arrear EMIs, current EMI untouched
                status = "PAID_PREVIOUS_DUES"

            elif paid_emi == 0.0 and (paid_late_fee > 0 or paid_penal > 0):
                # Payment went entirely to fees, current EMI untouched
                status = "FEES_ONLY_PAYMENT"

            else:
                # payment > 0 but nothing was allocated (should not happen)
                status = "MISSED"

        # Step 11: update outstanding balance via amortisation
        interest_this_cycle = round(outstanding_balance * monthly_rate, 2)

        if is_recovery_phase and paid_emi == 0.0 and payment > 0:
            # dues_queue was empty; apply payment directly to balance
            outstanding_balance = outstanding_balance - payment
        elif payment > 0 and paid_emi > 0:
            interest_covered = min(paid_emi, interest_this_cycle)
            principal_paid = max(0.0, paid_emi - interest_covered)
            outstanding_balance = outstanding_balance - principal_paid
        else:
            outstanding_balance = outstanding_balance + interest_this_cycle

        outstanding_balance = round(max(0.0, outstanding_balance), 2)

        # Step 12: clean up fully settled dues
        dues_queue = [d for d in dues_queue if d["remaining"] > 0]

        # Step 13: compute DPD
        # DPD = (cycle_due_date - oldest unpaid EMI due_date) in days.
        # Only EMIs that have crossed the grace window contribute.
        # Zero for PAID, PAID_LATE, PAID_FEES_PENDING, UPCOMING.
        if status in ("UPCOMING", "PAID", "PAID_LATE", "PAID_FEES_PENDING"):
            dpd_days = 0
        else:
            overdue_emi_dates = [
                d["due_date"]
                for d in dues_queue
                if d["kind"] == "emi"
                and d["remaining"] > 0
                and d["overdue_since"] is not None
            ]
            dpd_days = (
                max(0, (cycle_due_date - min(overdue_emi_dates)).days)
                if overdue_emi_dates
                else 0
            )

        repayments.append(
            {
                "due_date": cycle_due_date,
                "paid_date": paid_date,
                "amount_due": amount_due_pre_alloc,
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

        if is_recovery_phase and outstanding_balance == 0.0 and not dues_queue:
            break

    return repayments


def generate_and_insert():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    print("Starting data generation...\n")

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

    print("Inserting loans, repayments, assignments...")
    loan_count = 0
    repayment_count = 0

    customer_sample = random.choices(customer_ids, k=NUM_LOANS)
    loan_seeds = [random.randint(1, 9_999_999) for _ in range(NUM_LOANS)]

    for customer_id, loan_seed in zip(customer_sample, loan_seeds):

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
            seed=loan_seed,
        )

        outstanding = repayments[-1]["outstanding_balance"] if repayments else principal

        if outstanding <= 0.0:
            outstanding = 0.0
            loan_status = "CLOSED"
        else:
            loan_status = derive_loan_status(repayments)

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
