## Hardware Requirements:

RAM: 16GB minimum
GPU: 6GB VRAM (RTX 2060 or equivalent)

==============================================================================================================

## clone repo:
git clone <repo-url>

## go to the project's root directory:
cd BankingAnalyst_v1

---------------------------------------------------------------------------------------------------

## if you are on linux:

1. Configuire environment files.
    Run following in the bash of the root directory:
        cp Servers/.env.server.example Servers/.env.server
        cp src/.env.app.example src/.env.app
2. Run the docker engine.
3. Start server and app containers.
    Run following in the bash of the root directory:
        make up
4. Stop server and app containers.
    Run following in the bash of the root directory:
        make down    # Stops and removes containers, networks.
        make clean   # Stops and removes containers, networks, volumes and orphaned conatiners.
5. Quit the docker engine.

--------------------------------------------------------------------------------------------------

## if you are on windows:

1. Configuire environment files.
    Run following in the shell of the root directory:
        Copy-Item Servers/.env.server.example Servers/.env.server
        Copy-Item src/.env.app.example src/.env.app
2. Run the docker engine.
3. Start server and app containers.
    Run following in the shell of the root directory:
        python make.py up
4. Stop server and app containers.
    Run following in the shell of the root directory:
        python make.py down    # Stops and removes containers, networks.
        python make.py clean   # Stops and removes containers, networks, volumes and orphaned conatiners.
5. Quit the docker engine.

==============================================================================================================

# Agent Components

Intent Classification: Two-stage LLM classification with schema enforcement
Tool Nodes: Seven SQL-based tools with dynamic WHERE clause construction
Summarizer: Aggregates + top 3 worst cases (no raw row dumps)
Error Handler: Graceful fallback for failures
CSV Export: Auto-export for results >10 rows

--------------------------------------------------------------------------------------------------

# Tools Available

get_overdue_loans
get_repayment_summary
get_customer_profile
get_loan_portfolio_stats
get_collection_efficiency
get_help
==============================================================================================================