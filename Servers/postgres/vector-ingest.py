"""
ingest.py -- One-time RAG ingestion script.
Reads irac_faq.txt, chunks it, embeds it,
and stores chunks + embeddings in pgvector (policy_documents table).

Run once:
    python postgres/ingest.py
"""

import os
import time
import psycopg2
from google import genai
from langchain_text_splitters import RecursiveCharacterTextSplitter

from pathlib import Path

# Config

DB_CONFIG = {
    "host": os.getenv("db_host"),
    "port": os.getenv("db_port"),
    "dbname": os.getenv("db_name"),
    "user": os.getenv("db_user"),
    "password": os.getenv("db_password"),
}


FAQ_PATH = Path("./data/irac_faq.txt")
SOURCE_NAME = "irac_faq"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
EMBED_MODEL = os.getenv("embed_model_name")

# Google client

client = genai.Client(api_key=os.getenv("LLM_API_KEY"))


def embed_texts(
    texts: list[str], task_type: str = "retrieval_document"
) -> list[list[float]]:
    """Embed a list of texts using Google text-embedding-004."""
    result = client.models.embed_content(
        model=EMBED_MODEL,
        contents=texts,
        config={"task_type": task_type, "output_dimensionality": 1536},
    )
    return [e.values for e in result.embeddings]


# Load text

print(f"Loading document: {FAQ_PATH}")
text = FAQ_PATH.read_text(encoding="utf-8")
print(f"Document loaded. Total characters: {len(text)}")

# Chunk

splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
)
chunks = splitter.split_text(text)
print(f"Total chunks created: {len(chunks)}")

# Embed

BATCH_SIZE = 10  # Google API batch limit for embeddings
embeddings = []

print("Generating embeddings...")
for i in range(0, len(chunks), BATCH_SIZE):
    batch = chunks[i : i + BATCH_SIZE]
    batch_embeddings = embed_texts(batch, task_type="retrieval_document")
    embeddings.extend(batch_embeddings)
    print(f"  Embedded {min(i + BATCH_SIZE, len(chunks))}/{len(chunks)} chunks")
    time.sleep(0.9)  # avoid hitting rate limits

print(f"Embeddings generated. Total: {len(embeddings)}")

# Store

print("Connecting to Postgres...")
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

# Clear existing data from this source to avoid duplicates on re-run
cur.execute("DELETE FROM policy_documents WHERE source = %s", (SOURCE_NAME,))
print(f"Cleared existing rows for source: {SOURCE_NAME}")

print("Inserting chunks...")
for chunk, embedding in zip(chunks, embeddings):
    cur.execute(
        """
        INSERT INTO policy_documents (chunk_text, embedding, source)
        VALUES (%s, %s, %s)
        """,
        (chunk, embedding, SOURCE_NAME),
    )

conn.commit()
cur.close()
conn.close()

print(f"Done. {len(chunks)} chunks inserted into policy_documents.")
