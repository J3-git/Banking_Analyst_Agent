from contextlib import contextmanager
from psycopg2.extras import RealDictCursor


class DBClient:
    def __init__(self, pool):
        self.pool = pool

    @contextmanager
    def conn(self):
        conn = self.pool.getconn()
        try:
            yield conn
        except Exception:
            # optional: mark bad connection
            self.pool.putconn(conn, close=True)
            raise
        else:
            self.pool.putconn(conn)

    @contextmanager
    def cursor(self, conn, dict_cursor=True):
        cur = conn.cursor(
            cursor_factory=RealDictCursor if dict_cursor else None
        )  # Row -> dict instead of tuple if dict_cursor
        try:
            yield cur
        except Exception:
            raise
        finally:
            cur.close()

    def fetch_one(self, query, params=None):
        with self.conn() as conn:
            with self.cursor(conn) as cur:
                cur.execute(query, params)
                return cur.fetchone()

    def fetch_all(self, query, params=None):
        with self.conn() as conn:
            with self.cursor(conn) as cur:
                cur.execute(query, params)
                return cur.fetchall()
