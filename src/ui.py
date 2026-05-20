import os
from psycopg2 import pool as pg_pool
from openai import OpenAI
import gradio as gr
from agent import run_query, build_graph

graph = None
db_pool = None
llm_client = None
init_error = None


def init_app():
    DB_CONFIG = {
        "host": os.getenv("db_host"),
        "port": int(os.getenv("db_port")),
        "dbname": os.getenv("db_name"),
        "user": os.getenv("db_user"),
        "password": os.getenv("db_password"),
    }
    VLLM_URL = os.getenv("VLLM_URL")
    MODEL_NAME = os.getenv("model_name")

    print("Connecting to PostgreSQL...")
    db_pool = pg_pool.SimpleConnectionPool(minconn=1, maxconn=5, **DB_CONFIG)

    print("Connecting to vLLM...")
    llm_client = OpenAI(
        base_url=VLLM_URL,
        api_key=os.getenv("VLLM_API_KEY"),
    )

    print("Building LangGraph...")
    graph = build_graph(
        db_pool=db_pool,
        llm_client=llm_client,
        model_name=MODEL_NAME,
    )

    print("Initialization complete.")
    return graph, db_pool, llm_client


def ensure_init():
    global graph, db_pool, llm_client, init_error
    if graph is None:
        try:
            graph, db_pool, llm_client = init_app()
            init_error = None
        except Exception as e:
            graph = db_pool = llm_client = None
            init_error = str(e)


def system_status():
    ensure_init()
    if init_error:
        return f"Not Ready: {init_error}"
    return "System Ready"


def refresh_status():
    return system_status()


def chat_stream(message, history):
    ensure_init()
    if init_error:
        yield f"System initialization failed:\n\n{init_error}"
        return
    try:
        result = run_query(graph, message)
        partial = ""
        for line in str(result).split("\n"):
            partial += line + "\n"
            yield partial
    except Exception as e:
        yield f"Runtime error: {str(e)}"


with gr.Blocks(
    title="Banking Loan Analyst",
    css=""".gradio-container { height: 95vh !important; }""",
) as demo:
    gr.Markdown("# Banking Loan Analyst Assistant")

    status_box = gr.Markdown(system_status())
    refresh_btn = gr.Button("Refresh Status", size="sm")
    refresh_btn.click(fn=refresh_status, outputs=status_box)

    gr.ChatInterface(
        fn=chat_stream,
        type="messages",
        chatbot=gr.Chatbot(height=800),
        examples=[
            "Show me the loan portfolio stats",
            "Get customer profile for customer ID 1001",
            "List all overdue loans",
            "What is the collection efficiency?",
        ],
    )


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)
