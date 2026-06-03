# import os
# import gradio as gr

# from psycopg2 import pool as pg_pool
# from openai import OpenAI

# from agent import run_query, build_graph
# from agent import DBClient
# from langgraph.runtime import Runtime
# from agent import AppContext

# import uuid


# def new_chat() -> str:
#     """Generate a fresh thread_id for a new conversation."""
#     return str(uuid.uuid4())


# # App container


# class AppState:
#     def __init__(self):
#         self.graph = None
#         self.db_pool = None
#         self.llm_client = None
#         self.app_context = None
#         self.init_error = None

#     def init(self):
#         try:
#             DB_CONFIG = {
#                 "host": os.getenv("db_host"),
#                 "port": int(os.getenv("db_port")),
#                 "dbname": os.getenv("db_name"),
#                 "user": os.getenv("db_user"),
#                 "password": os.getenv("db_password"),
#             }

#             LLM_URL = os.getenv("LLM_URL")
#             MODEL_NAME = os.getenv("model_name")

#             print("Connecting to PostgreSQL...")
#             self.db_pool = pg_pool.SimpleConnectionPool(
#                 minconn=1, maxconn=5, **DB_CONFIG
#             )

#             print("Connecting to vLLM...")
#             self.llm_client = OpenAI(
#                 base_url=LLM_URL,
#                 api_key=os.getenv("LLM_API_KEY"),
#             )

#             print("Building runtime context...")
#             db_client = DBClient(self.db_pool)

#             self.app_context = AppContext(
#                 user_id=DB_CONFIG.get("user", "guest"),
#                 model_name=MODEL_NAME,
#                 client=self.llm_client,
#                 db=db_client,
#             )

#             print("Building LangGraph...")
#             self.graph = build_graph()

#             self.init_error = None
#             print("Initialization complete.")

#         except Exception as e:
#             self.init_error = str(e)
#             self.graph = None
#             self.runtime = None
#             self.db_pool = None
#             self.llm_client = None


# # Single app instance
# app = AppState()


# def ensure_init():
#     if app.graph is None and app.init_error is None:
#         app.init()


# def system_status():
#     ensure_init()
#     return "System Ready" if not app.init_error else f"Not Ready: {app.init_error}"


# def refresh_status():
#     app.init()
#     return system_status()

# # chat_stream:
# def chat_stream(message: str, history: list, thread_id: str):
#     ensure_init()

#     if app.init_error:
#         yield f"System initialization failed:\n\n{app.init_error}"
#         return

#     try:
#         # Added history=history here
#         result = run_query(
#             graph=app.graph,
#             user_query=message,
#             context=app.app_context,
#             history=history,
#             thread_id=thread_id,
#         )

#         partial = ""
#         for line in str(result).split("\n"):
#             partial += line + "\n"
#             yield partial

#     except Exception as e:
#         yield f"Runtime error: {str(e)}"


# with gr.Blocks(
#     title="Banking Loan Analyst",
#     css=".gradio-container { height: 95vh !important; }",
# ) as demo:

#     gr.Markdown("# Banking Loan Analyst Assistant")

#     status_box = gr.Markdown(system_status())
#     refresh_btn = gr.Button("Refresh Status", size="sm")
#     refresh_btn.click(fn=refresh_status, outputs=status_box)

#     # thread_id persists across turns, resets on new chat
#     thread_state = gr.State(value=lambda: str(uuid.uuid4()))

#     new_chat_btn = gr.Button("New Chat", size="sm")

#     custom_chatbot = gr.Chatbot(height=800, type="messages")

#     gr.ChatInterface(
#         fn=chat_stream,
#         type="messages",
#         chatbot=custom_chatbot,
#         additional_inputs=[thread_state],
#         examples=[
#             ["Show me the loan portfolio stats"],
#             ["Get customer profile for customer ID 1001"],
#             ["List all overdue loans"],
#             ["What is the collection efficiency?"],
#         ],
#     )

#     new_chat_btn.click(
#         fn=new_chat,
#         outputs=thread_state,
#     )


# # Entry

# if __name__ == "__main__":
#     demo.launch(server_name="0.0.0.0", server_port=7860, share=False, debug=True)

import os
import uuid

import gradio as gr

from psycopg2 import pool as pg_pool
from openai import OpenAI

from google import genai
from google.genai import types

from agent import run_query, build_graph
from agent import DBClient
from agent import AppContext

# APP STATE


class AppState:
    def __init__(self):
        self.graph = None
        self.db_pool = None
        self.llm_client = None
        self.gemini_client = None
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

            LLM_URL = os.getenv("LLM_URL")
            MODEL_NAME = os.getenv("model_name")
            LLM_API_KEY = os.getenv("LLM_API_KEY")

            print("Connecting to PostgreSQL...")
            self.db_pool = pg_pool.SimpleConnectionPool(
                minconn=1,
                maxconn=5,
                **DB_CONFIG,
            )

            print("Connecting to vLLM...")
            self.llm_client = OpenAI(
                base_url=LLM_URL,
                api_key=LLM_API_KEY,
            )

            print("Connecting to Gemini...")
            self.gemini_client = genai.Client(api_key=LLM_API_KEY)

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
            self.db_pool = None
            self.llm_client = None
            self.gemini_client = None


app = AppState()


def _new_chat():
    return [], str(uuid.uuid4())


def _ensure_init():
    if app.graph is None and app.init_error is None:
        app.init()


def _system_status() -> str:
    _ensure_init()
    return "System Ready" if not app.init_error else f"Not Ready: {app.init_error}"


def refresh_status() -> str:
    app.init()
    return _system_status()


# AUDIO TRANSCRIPTION


def transcribe_audio(audio_path: str) -> str:
    if not audio_path:
        return ""

    try:
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        response = app.gemini_client.models.generate_content(
            model=os.getenv("model_name"),
            contents=[
                types.Part.from_bytes(
                    data=audio_bytes,
                    mime_type="audio/wav",
                ),
                "Transcribe this audio. Return only the spoken text. Remove fillers and noise.",
            ],
        )

        return response.text.strip()

    except Exception as e:
        return f"[Transcription Error: {str(e)}]"


# AGENT RUNNER


def run_agent_stream(
    user_query: str,
    history: list,
    thread_id: str,
):
    _ensure_init()

    if app.init_error:
        yield f"System initialization failed:\n\n{app.init_error}"
        return

    try:
        result = run_query(
            graph=app.graph,
            user_query=user_query,
            app_context=app.app_context,
            history=history,
            thread_id=thread_id,
        )

        final_text = result.get("final_response") or "No response generated."
        csv_paths = result.get("csv_paths") or []
        chart_paths = result.get("chart_paths") or []

        # append export info to response
        if csv_paths:
            final_text += "\n\n**Exports:**"
            for path in csv_paths:
                final_text += f"\n- `{path}`"

        if chart_paths:
            final_text += "\n\n**Charts:**"
            for path in chart_paths:
                final_text += f"\n- `{path}`"

        # stream line by line
        partial = ""
        for line in final_text.split("\n"):
            partial += line + "\n"
            yield partial

    except Exception as e:
        yield f"Runtime error: {str(e)}"


# INTERACTION HANDLERS


def user_submit(
    message: str,
    audio_file: str,
    history: list,
):
    query = (message or "").strip()

    if not query and audio_file:
        query = transcribe_audio(audio_file)

    if not query:
        return "", None, history

    if query.startswith("[Transcription Error:"):
        history = history + [
            {"role": "user", "content": "[Audio Input]"},
            {"role": "assistant", "content": query},
        ]
        return "", None, history

    history = history + [{"role": "user", "content": query}]
    return "", None, history


def bot_response(history, thread_id):
    if not history or history[-1]["role"] != "user":
        yield history
        return

    user_query = history[-1]["content"]
    _ensure_init()

    try:
        result = run_query(
            graph=app.graph,
            user_query=user_query,
            app_context=app.app_context,
            history=history[:-1],
            thread_id=thread_id,
        )

        final_text = result.get("final_response") or "No response generated."
        csv_paths = result.get("csv_paths") or []
        chart_paths = result.get("chart_paths") or []

        # append csv paths to text
        if csv_paths:
            final_text += "\n\n**Exports:**"
            for path in csv_paths:
                final_text += f"\n- `{path}`"

        # stream text
        partial = ""
        updated_history = history + [{"role": "assistant", "content": ""}]
        for line in final_text.split("\n"):
            partial += line + "\n"
            updated_history[-1]["content"] = partial
            yield updated_history

        # append chart images as separate messages
        for path in chart_paths:
            updated_history = updated_history + [
                {"role": "assistant", "content": gr.Image(path)}
            ]
            yield updated_history

    except Exception as e:
        yield history + [{"role": "assistant", "content": f"Runtime error: {str(e)}"}]


# GRADIO UI


with gr.Blocks(
    title="Banking Loan Analyst",
    css=".gradio-container { height: 95vh !important; }",
) as demo:

    gr.Markdown("# Banking Loan Analyst Assistant")

    with gr.Row():
        status_box = gr.Markdown(_system_status())
        refresh_btn = gr.Button("Refresh Status", size="sm")

    refresh_btn.click(fn=refresh_status, outputs=status_box)

    # lambda ensures each new session gets a fresh UUID
    thread_state = gr.State(value=lambda: str(uuid.uuid4()))

    chatbot = gr.Chatbot(height=600, type="messages")

    with gr.Row():
        text_input = gr.Textbox(
            label="Message",
            placeholder="Ask a question about loans, customers, portfolio...",
            scale=4,
            lines=1,
        )
        audio_input = gr.Audio(
            sources=["microphone"],
            type="filepath",
            label="Voice Input",
            scale=2,
        )

    with gr.Row():
        send_btn = gr.Button("Send", variant="primary")
        new_chat_btn = gr.Button("New Chat", variant="secondary")

    gr.Examples(
        examples=[
            ["Show me the loan portfolio stats"],
            ["Get customer profile for customer ID 1001"],
            ["List all overdue loans"],
            ["What is the collection efficiency?"],
            ["Compare portfolio stats for Mumbai vs Delhi"],
        ],
        inputs=text_input,
    )

    submit_inputs = [text_input, audio_input, chatbot]
    submit_outputs = [text_input, audio_input, chatbot]

    # send button
    send_btn.click(
        fn=user_submit,
        inputs=submit_inputs,
        outputs=submit_outputs,
    ).then(
        fn=bot_response,
        inputs=[chatbot, thread_state],
        outputs=chatbot,
    )

    # Enter key on textbox
    text_input.submit(
        fn=user_submit,
        inputs=submit_inputs,
        outputs=submit_outputs,
    ).then(
        fn=bot_response,
        inputs=[chatbot, thread_state],
        outputs=chatbot,
    )

    new_chat_btn.click(
        fn=_new_chat,
        outputs=[chatbot, thread_state],
    )


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        debug=True,
        show_api=False,
    )
