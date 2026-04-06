## Hardware Requirements

- **RAM:** 16 GB minimum  
- **GPU:** 6 GB VRAM (RTX 2060 or equivalent)

------------------------------------------------------------------

## Clone Repository

```bash
git clone https://github.com/J3-git/Banking_Analyst_Agent.git
```

## Go to Project Root Directory

```bash
cd BankingAnalyst_v1
```

------------------------------------------------------------------

## If you are on Linux

1. **Configure environment files**

   Run the following in the bash of the root directory:

   ```bash
   cp Servers/.env.server.example Servers/.env.server
   cp src/.env.app.example src/.env.app
   ```

2. **Run the Docker engine**

3. **Start server and app containers**

   Run the following in the bash of the root directory:

   ```bash
   make up
   ```

4. **Stop server and app containers**

   Run the following in the bash of the root directory:

   ```bash
   make down    # Stops and removes containers, networks
   make clean   # Stops and removes containers, networks, volumes, and orphaned containers
   ```

5. **Quit the Docker engine**

------------------------------------------------------------------

## If you are on Windows

1. **Configure environment files**

   Run the following in the shell of the root directory:

   ```powershell
   Copy-Item Servers/.env.server.example Servers/.env.server
   Copy-Item src/.env.app.example src/.env.app
   ```

2. **Run the Docker engine**

3. **Start server and app containers**

   Run the following in the shell of the root directory:

   ```powershell
   python make.py up
   ```

4. **Stop server and app containers**

   Run the following in the shell of the root directory:

   ```powershell
   python make.py down    # Stops and removes containers, networks
   python make.py clean   # Stops and removes containers, networks, volumes, and orphaned containers
   ```

5. **Quit the Docker engine**

------------------------------------------------------------------

# Agent Components

- **Intent Classification:** Two-stage LLM classification with schema enforcement  
- **Tool Nodes:** Seven SQL-based tools with dynamic WHERE clause construction  
- **Summarizer:** Aggregates + top 3 worst cases (no raw row dumps)  
- **Error Handler:** Graceful fallback for failures  
- **CSV Export:** Auto-export for results > 10 rows  

------------------------------------------------------------------

# Tools Available

- get_overdue_loans  
- get_repayment_summary  
- get_customer_profile  
- get_loan_portfolio_stats  
- get_collection_efficiency  
- get_help  

------------------------------------------------------------------