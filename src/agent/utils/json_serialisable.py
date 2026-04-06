from datetime import date
from decimal import Decimal

def _rows(cur) -> list[dict]:
    """converts database query results into a JSON-friendly format.
    Note: Converts special types Decimal & date; as JSON can't serialize certain special types."""
    rows = cur.fetchall()
    result = []
    for row in rows:
        clean = {}
        for k, v in row.items():
            if isinstance(v, Decimal):
                clean[k] = float(v)        # JSON-serialisable
            elif isinstance(v, date):
                clean[k] = v.isoformat()   # "2024-03-15"
            else:
                clean[k] = v
        result.append(clean)
    return result

