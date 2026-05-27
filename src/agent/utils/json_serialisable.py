from datetime import date
from decimal import Decimal


# Helper function: SERIALIZER
# Converts special types Decimal & date; as JSON can't serialize certain special types.
def _serialize_value(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, date):
        return v.isoformat()
    return v
