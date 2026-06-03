-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Policy documents table for RAG
CREATE TABLE IF NOT EXISTS policy_documents (
    id          SERIAL PRIMARY KEY,
    chunk_text  TEXT        NOT NULL,
    embedding   vector(1536) NOT NULL,
    source      TEXT        NOT NULL,  -- e.g. "irac_faq"
    section     TEXT,                  -- e.g. "NPA Classification"
    question    TEXT                   -- e.g. "When is a loan treated as NPA?"
);

-- Index for fast cosine similarity search
CREATE INDEX IF NOT EXISTS policy_documents_embedding_idx
    ON policy_documents
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);