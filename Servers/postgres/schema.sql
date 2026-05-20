-- ============================================================
-- Banking / Loan Analyst Assistant — PostgreSQL Schema
-- 5 tables: customers, employees, loans, repayments, loan_assignments
-- ============================================================

DROP TABLE IF EXISTS loan_assignments CASCADE;
DROP TABLE IF EXISTS repayments CASCADE;
DROP TABLE IF EXISTS loans CASCADE;
DROP TABLE IF EXISTS employees CASCADE;
DROP TABLE IF EXISTS customers CASCADE;

-- ------------------------------------------------------------
-- 1. CUSTOMERS
-- ------------------------------------------------------------
CREATE TABLE customers (
    customer_id         SERIAL PRIMARY KEY,
    full_name           VARCHAR(100)  NOT NULL,
    age                 INT           NOT NULL,
    gender              VARCHAR(10),
    phone               VARCHAR(15)   NOT NULL,
    email               VARCHAR(100),
    city                VARCHAR(50)   NOT NULL,
    branch_name         VARCHAR(100)  NOT NULL,
    annual_income       NUMERIC(15,2) NOT NULL,
    employment_type     VARCHAR(50)   NOT NULL,  -- 'Salaried', 'Self-Employed', 'Business Owner', 'Government Employee'
    credit_score        INT           NOT NULL,  -- 300 to 900
    created_at          DATE          NOT NULL DEFAULT CURRENT_DATE
);

-- ------------------------------------------------------------
-- 2. EMPLOYEES (Loan Officers)
-- ------------------------------------------------------------
CREATE TABLE employees (
    employee_id     SERIAL PRIMARY KEY,
    full_name       VARCHAR(100) NOT NULL,
    email           VARCHAR(100) UNIQUE NOT NULL,
    phone           VARCHAR(15)  NOT NULL,
    role            VARCHAR(50)  NOT NULL,   -- 'Loan Officer', 'Branch Manager', 'Credit Analyst'
    branch_name     VARCHAR(100) NOT NULL,   -- simplified, no separate branches table
    city            VARCHAR(50)  NOT NULL,
    joined_date     DATE         NOT NULL,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE
);

-- ------------------------------------------------------------
-- 3. LOANS
-- ------------------------------------------------------------
CREATE TABLE loans (
    loan_id             SERIAL PRIMARY KEY,
    customer_id         INT           NOT NULL REFERENCES customers(customer_id),
    loan_type           VARCHAR(50)   NOT NULL,   -- 'Personal', 'Home', 'Business', 'Vehicle', 'Education', 'Gold'
    principal_amount    NUMERIC(15,2) NOT NULL,
    interest_rate       NUMERIC(5,2)  NOT NULL,
    tenure_months       INT           NOT NULL,
    emi_amount          NUMERIC(10,2) NOT NULL,
    disbursed_date      DATE          NOT NULL,
    maturity_date       DATE          NOT NULL,
    outstanding_amount  NUMERIC(15,2) NOT NULL,
    status              VARCHAR(20)   NOT NULL
        CHECK (status IN ('ACTIVE', 'OVERDUE', 'CLOSED', 'DEFAULTED', 'NPA')),
    purpose             TEXT,
    created_at          DATE          NOT NULL DEFAULT CURRENT_DATE
);

-- ------------------------------------------------------------
-- 4. REPAYMENTS
-- ------------------------------------------------------------
-- CREATE TABLE repayments (
--     repayment_id    SERIAL PRIMARY KEY,
--     loan_id         INT           NOT NULL REFERENCES loans(loan_id),
--     due_date        DATE          NOT NULL,
--     paid_date       DATE,                         -- NULL if unpaid
--     amount_due      NUMERIC(10,2) NOT NULL,
--     amount_paid     NUMERIC(10,2) NOT NULL DEFAULT 0,
--     dpd_days   INT           NOT NULL DEFAULT 0,
--     status          VARCHAR(20)   NOT NULL
--         CHECK (status IN ('PAID_ONTIME', 'PAID_LATE', 'MISSED', 'UPCOMING', 'PARTIAL'))
-- );


CREATE TABLE repayments (
    repayment_id    SERIAL PRIMARY KEY,
    loan_id         INT NOT NULL REFERENCES loans(loan_id),

    due_date        DATE NOT NULL,
    paid_date       DATE,

    amount_due      NUMERIC(10,2) NOT NULL,
    amount_paid     NUMERIC(10,2) NOT NULL DEFAULT 0,

    -- breakdown of payment allocation (FIFO ledger model)
    amount_paid_emi       NUMERIC(10,2) NOT NULL DEFAULT 0,
    amount_paid_late_fee  NUMERIC(10,2) NOT NULL DEFAULT 0,
    amount_paid_penal     NUMERIC(10,2) NOT NULL DEFAULT 0,

    -- delinquency tracking
    dpd_days        INT NOT NULL DEFAULT 0,

    -- live outstanding snapshot
    outstanding_fees      NUMERIC(10,2) NOT NULL DEFAULT 0,
    outstanding_balance   NUMERIC(10,2) NOT NULL DEFAULT 0,

    status          VARCHAR(30) NOT NULL,

    CHECK (status IN (
        'PAID',
        'PAID_LATE',
        'PARTIAL',
        'MISSED',
        'UPCOMING',
        'DEFAULTED',
        'OVERDUE',
        'PAID_PREVIOUS_DUES',
        'PAID_FEES_PENDING',
        'PARTIAL_RECOVERY',
        'RECOVERY_PAYMENT',
        'FEES_ONLY_PAYMENT'
    ))
);

-- ------------------------------------------------------------
-- 5. LOAN_ASSIGNMENTS
-- ------------------------------------------------------------
CREATE TABLE loan_assignments (
    assignment_id   SERIAL PRIMARY KEY,
    loan_id         INT     NOT NULL REFERENCES loans(loan_id),
    employee_id     INT     NOT NULL REFERENCES employees(employee_id),
    assigned_date   DATE    NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE  -- FALSE when reassigned to someone else
);

-- ------------------------------------------------------------
-- INDEXES
-- ------------------------------------------------------------
CREATE INDEX idx_customers_city          ON customers(city);
CREATE INDEX idx_customers_credit        ON customers(credit_score);

CREATE INDEX idx_loans_customer_id       ON loans(customer_id);
CREATE INDEX idx_loans_status            ON loans(status);
CREATE INDEX idx_loans_type              ON loans(loan_type);

CREATE INDEX idx_repayments_loan_id      ON repayments(loan_id);
CREATE INDEX idx_repayments_status       ON repayments(status);
CREATE INDEX idx_repayments_due_date     ON repayments(due_date);

CREATE INDEX idx_loan_assignments_loan   ON loan_assignments(loan_id);
CREATE INDEX idx_loan_assignments_emp    ON loan_assignments(employee_id);
CREATE INDEX idx_loan_assignments_active ON loan_assignments(is_active);