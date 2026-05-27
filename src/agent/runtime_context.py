from dataclasses import dataclass
from openai import OpenAI

# from psycopg2.pool import SimpleConnectionPool
from agent.db_client import DBClient


@dataclass
class AppContext:
    user_id: str
    model_name: str

    # shared infra clients
    client: OpenAI
    db: DBClient
