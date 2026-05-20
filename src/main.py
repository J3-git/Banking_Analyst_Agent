import os
from psycopg2 import pool as pg_pool
from openai import OpenAI

# from dotenv import load_dotenv
from agent import run_query, build_graph
from pathlib import Path
import os

# env_path = Path(__file__).resolve().parent/".env.app"
# load_dotenv(env_path)


def main():
    """
    Initialises all dependencies and runs the interactive CLI loop.
    """
    # Config
    DB_CONFIG = {
        "host": os.getenv("db_host"),
        "port": int(os.getenv("db_port")),
        "dbname": os.getenv("db_name"),
        "user": os.getenv("db_user"),
        "password": os.getenv("db_password"),
    }

    VLLM_URL = os.getenv("VLLM_URL")
    MODEL_NAME = os.getenv("model_name")

    # Initialise connection pool
    try:
        print("Connecting to PostgreSQL...")
        db_pool = pg_pool.SimpleConnectionPool(minconn=1, maxconn=5, **DB_CONFIG)
        print("Database connected")

    except Exception as e:
        print(f"Failed to connect to DB: {e}")
        return

    # Initialise LLM client
    try:
        print(f"Connecting to vLLM...")
        llm_client = OpenAI(base_url=VLLM_URL, api_key=os.getenv("VLLM_API_KEY"))
        print(f"LLM client ready -- model: {MODEL_NAME}")

    except Exception as e:
        print(f"Failed to initialise LLM client: {e}")
        print(f"closing DB connection...")
        db_pool.closeall()
        print(f"DB connections closed.")
        return

    # Build graph once
    print("Building agent graph...")
    graph = build_graph(
        db_pool=db_pool,
        llm_client=llm_client,
        model_name=MODEL_NAME,
    )
    print("Graph compiled")

    # To create flowchart image
    os.makedirs("./exports", exist_ok=True)
    graph_visual = graph.get_graph()
    graph_visual_png = graph_visual.draw_mermaid_png()
    with open("./exports/graph.png", "wb") as f:
        f.write(graph_visual_png)
    print("Graph image saved in exports directory.")

    print("-" * 60)
    print("Banking Loan Analyst Assistant")
    print("Type 'help' to see available queries")
    print("Type 'quit' or 'exit' to stop")
    print("-" * 60)

    # Interactive CLI loop
    while True:
        try:
            user_input = input("\nQuery: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ("quit", "exit", "q"):
                print("Goodbye.")
                break

            print("\nProcessing...\n")
            response = run_query(graph, user_input)
            print(f"Response:\n{response}")

        except KeyboardInterrupt:
            print("\nGoodbye.")
            break

    # Cleanup
    db_pool.closeall()
    print("Database connections closed.")
    llm_client.close()
    print(f"LLM client closed")


if __name__ == "__main__":
    main()
