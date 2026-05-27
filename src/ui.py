# import os
# from psycopg2 import pool as pg_pool
# from openai import OpenAI
# import gradio as gr
# from agent import run_query, build_graph

# graph = None
# db_pool = None
# llm_client = None
# init_error = None


# def init_app():
#     DB_CONFIG = {
#         "host": os.getenv("db_host"),
#         "port": int(os.getenv("db_port")),
#         "dbname": os.getenv("db_name"),
#         "user": os.getenv("db_user"),
#         "password": os.getenv("db_password"),
#     }
#     VLLM_URL = os.getenv("VLLM_URL")
#     MODEL_NAME = os.getenv("model_name")

#     print("Connecting to PostgreSQL...")
#     db_pool = pg_pool.SimpleConnectionPool(minconn=1, maxconn=5, **DB_CONFIG)

#     print("Connecting to vLLM...")
#     llm_client = OpenAI(
#         base_url=VLLM_URL,
#         api_key=os.getenv("VLLM_API_KEY"),
#     )

#     print("Building LangGraph...")
#     graph = build_graph(
#         db_pool=db_pool,
#         llm_client=llm_client,
#         model_name=MODEL_NAME,
#     )

#     print("Initialization complete.")
#     return graph, db_pool, llm_client


# def ensure_init():
#     global graph, db_pool, llm_client, init_error
#     if graph is None:
#         try:
#             graph, db_pool, llm_client = init_app()
#             init_error = None
#         except Exception as e:
#             graph = db_pool = llm_client = None
#             init_error = str(e)


# def system_status():
#     ensure_init()
#     if init_error:
#         return f"Not Ready: {init_error}"
#     return "System Ready"


# def refresh_status():
#     return system_status()


# def chat_stream(message, history):
#     ensure_init()
#     if init_error:
#         yield f"System initialization failed:\n\n{init_error}"
#         return
#     try:
#         result = run_query(graph, message)
#         partial = ""
#         for line in str(result).split("\n"):
#             partial += line + "\n"
#             yield partial
#     except Exception as e:
#         yield f"Runtime error: {str(e)}"


# with gr.Blocks(
#     title="Banking Loan Analyst",
#     css=""".gradio-container { height: 95vh !important; }""",
# ) as demo:
#     gr.Markdown("# Banking Loan Analyst Assistant")

#     status_box = gr.Markdown(system_status())
#     refresh_btn = gr.Button("Refresh Status", size="sm")
#     refresh_btn.click(fn=refresh_status, outputs=status_box)

#     gr.ChatInterface(
#         fn=chat_stream,
#         type="messages",
#         chatbot=gr.Chatbot(height=800),
#         examples=[
#             "Show me the loan portfolio stats",
#             "Get customer profile for customer ID 1001",
#             "List all overdue loans",
#             "What is the collection efficiency?",
#         ],
#     )


# if __name__ == "__main__":
#     demo.launch(server_name="0.0.0.0", server_port=7860, share=False)


import os
import gradio as gr

from psycopg2 import pool as pg_pool
from openai import OpenAI

from agent import run_query, build_graph
from agent import DBClient
from langgraph.runtime import Runtime
from agent import AppContext

# App container


class AppState:
    def __init__(self):
        self.graph = None
        self.db_pool = None
        self.llm_client = None
        self.app_context = None
        self.init_error = None

    def init(self):
        try:
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
            self.db_pool = pg_pool.SimpleConnectionPool(
                minconn=1, maxconn=5, **DB_CONFIG
            )

            print("Connecting to vLLM...")
            self.llm_client = OpenAI(
                base_url=VLLM_URL,
                api_key=os.getenv("VLLM_API_KEY"),
            )

            print("Building runtime context...")
            db_client = DBClient(self.db_pool)

            self.app_context = AppContext(
                user_id=DB_CONFIG.get("user", "guest"),
                model_name=MODEL_NAME,
                client=self.llm_client,
                db=db_client,
            )

            print("Building LangGraph...")
            self.graph = build_graph()

            self.init_error = None
            print("Initialization complete.")

        except Exception as e:
            self.init_error = str(e)
            self.graph = None
            self.runtime = None
            self.db_pool = None
            self.llm_client = None


# Single app instance
app = AppState()


def ensure_init():
    if app.graph is None and app.init_error is None:
        app.init()


def system_status():
    ensure_init()
    return "System Ready" if not app.init_error else f"Not Ready: {app.init_error}"


def refresh_status():
    app.init()
    return system_status()


# # Chat function
# def chat_stream(message, history):
#     ensure_init()

#     if app.init_error:
#         yield f"System initialization failed:\n\n{app.init_error}"
#         return

#     try:
#         result = run_query(
#             graph=app.graph,
#             user_query=message,
#             runtime=app.runtime,
#         )

#         partial = ""
#         for line in str(result).split("\n"):
#             partial += line + "\n"
#             yield partial

#     except Exception as e:
#         yield f"Runtime error: {str(e)}"


# UI

# with gr.Blocks(
#     title="Banking Loan Analyst",
#     css=""".gradio-container { height: 95vh !important; }""",
# ) as demo:

#     gr.Markdown("# Banking Loan Analyst Assistant")

#     status_box = gr.Markdown(system_status())
#     refresh_btn = gr.Button("Refresh Status", size="sm")
#     refresh_btn.click(fn=refresh_status, outputs=status_box)

#     gr.ChatInterface(
#         fn=chat_stream,
#         type="messages",
#         chatbot=gr.Chatbot(height=800),
#         examples=[
#             "Show me the loan portfolio stats",
#             "Get customer profile for customer ID 1001",
#             "List all overdue loans",
#             "What is the collection efficiency?",
#         ],
#     )


# chat_stream:
def chat_stream(message, history):
    ensure_init()

    if app.init_error:
        yield f"System initialization failed:\n\n{app.init_error}"
        return

    try:
        # Added history=history here
        result = run_query(
            graph=app.graph,
            user_query=message,
            context=app.app_context,
            history=history,
        )

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

    # Move gr.Chatbot outside and pass it to the chatbot parameter
    # Set type="messages" on BOTH the Chatbot and ChatInterface for full compatibility
    custom_chatbot = gr.Chatbot(height=800, type="messages")

    gr.ChatInterface(
        fn=chat_stream,
        type="messages",
        chatbot=custom_chatbot,
        examples=[
            "Show me the loan portfolio stats",
            "Get customer profile for customer ID 1001",
            "List all overdue loans",
            "What is the collection efficiency?",
        ],
    )


# Entry

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False, debug=True)
