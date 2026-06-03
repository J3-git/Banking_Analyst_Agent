import os
from google import genai
from agent.agent_state import AgentState
from agent.runtime_context import AppContext
from langgraph.runtime import Runtime

EMBED_MODEL = os.getenv("embed_model_name")
LLM_MODEL = os.getenv("model_name")
TOP_K = 3
SIMILARITY_THRESHOLD = 0.75

# from pgvector.psycopg2 import register_vector


def _embed_query(client: genai.Client, query: str) -> list[float]:
    """Embed user query using retrieval_query task type."""
    result = client.models.embed_content(
        model=EMBED_MODEL,
        contents=[query],
        config={"task_type": "retrieval_query", "output_dimensionality": 1536},
    )
    return result.embeddings[0].values


def _retrieve_chunks(cur, query_embedding: list[float], top_k: int) -> list[dict]:
    """Fetch top-k similar chunks from pgvector."""
    cur.execute(
        """
        SELECT
            chunk_text,
            source,
            section,
            question,
            1 - (embedding <=> %s::vector) AS similarity
        FROM policy_documents
        ORDER BY embedding <=> %s::vector
        LIMIT %s
        """,
        (query_embedding, query_embedding, top_k),
    )
    rows = cur.fetchall()
    return [
        {
            "chunk_text": row["chunk_text"],
            "source": row["source"],
            "section": row["section"],
            "question": row["question"],
            "similarity": round(float(row["similarity"]), 4),
        }
        for row in rows
    ]


def _build_prompt(user_query: str, chunks: list[dict]) -> str:
    context_block = "\n\n".join(
        f"[Chunk {i+1}]:\n{c['chunk_text']}" for i, c in enumerate(chunks)
    )
    return f"""You are a banking policy assistant. Answer the user's question strictly based on the provided policy document excerpts.
If the answer is not found in the context, say "I could not find relevant information in the policy documents."
Do not make up information. 

Policy Context:
{context_block}

User Question: {user_query}

Answer:"""


def retrieve_policy_node(
    state: AgentState,
    runtime: Runtime[AppContext],
) -> dict:
    """
    RAG node -- retrieves relevant policy chunks from pgvector
    and generates a grounded answer using Gemini.

    Ownership rules:
      - This node writes ONLY to: final_response, error
    """

    user_query = state.get("enriched_query") or state.get("user_query")

    try:
        google_client = genai.Client(api_key=os.getenv("LLM_API_KEY"))
        db_client = runtime.context.db

        # embed query
        query_embedding = _embed_query(google_client, user_query)

        # retrieve chunks
        with db_client.conn() as conn:
            # register_vector(conn)
            with db_client.cursor(conn, dict_cursor=True) as cur:
                chunks = _retrieve_chunks(cur, query_embedding, TOP_K)

        print("==========================================================")
        print("DEBUG: in retrieve_policy_node:")
        print(f"DEBUG: user_query: {user_query}")
        print(f"DEBUG: chunks_retrieved: {len(chunks)}")
        for i, c in enumerate(chunks):
            print(f"DEBUG: chunk_{i+1}_similarity: {c['similarity']}")
        print("==========================================================")

        # check if best chunk meets threshold
        if not chunks or chunks[0]["similarity"] < SIMILARITY_THRESHOLD:
            return {
                "final_response": "I could not find relevant information in the policy documents for your query.",
                "error": None,
            }

        # generate answer
        prompt = _build_prompt(user_query, chunks)
        response = google_client.models.generate_content(
            model=LLM_MODEL,
            contents=prompt,
        )
        answer = response.text.strip()

        # append best reference
        best = chunks[0]
        reference_parts = ["**Reference:** IRAC FAQ"]
        if best.get("section"):
            reference_parts.append(f"→ {best['section']}")
        if best.get("question"):
            reference_parts.append(f"→ {best['question']}")
        reference_parts.append(f"(confidence: {best['similarity']})")
        reference = " ".join(reference_parts)

        final_response = f"{answer}\n\n{reference}"

        return {
            "final_response": final_response,
            "error": None,
        }

    except Exception as e:
        print("==========================================================")
        print("DEBUG: in retrieve_policy_node exception occurred:")
        print(f"DEBUG: error: {e}")
        print("==========================================================")

        return {
            "error": f"retrieve_policy failed: {str(e)}",
        }
