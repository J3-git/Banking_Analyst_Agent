# csv exports:
import os
import csv
from datetime import datetime
# from dotenv import load_dotenv
from pathlib import Path

# env_path = Path(__file__).resolve().parent.parent.parent/".env.app"
# load_dotenv(env_path)
 
EXPORT_DIR    = os.getenv("EXPORT_DIR")
ROW_THRESHOLD = 10
 
 
def _ensure_dir():
    os.makedirs(EXPORT_DIR, exist_ok=True)
 
 
def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")
 
 
def _write_csv(filename: str, rows: list[dict]) -> str:
    """Write list of dicts to CSV. Returns file path."""
    _ensure_dir()
    path = os.path.join(EXPORT_DIR, filename)
    if not rows:
        return None
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return path
 
 
def _export_overdue_loans(loans: list) -> str:
    return _write_csv(f"overdue_loans_{_timestamp()}.csv", loans)
 
 
def _export_repayment_summary(repayments: list) -> str:
    return _write_csv(f"repayment_summary_{_timestamp()}.csv", repayments)
 
 
# called by tool nodes after query
def maybe_export(intent: str, tool_result: dict) -> str | None:
    """
    Checks if result is large enough to warrant export.
    Returns file path if exported, None otherwise.
    """
    if not tool_result:
        return None
 
    if intent == "get_overdue_loans":
        loans = tool_result.get("loans", [])
        if len(loans) > ROW_THRESHOLD:
            return _export_overdue_loans(loans)
 
    elif intent == "get_repayment_summary":
        repayments = tool_result.get("repayments", [])
        if len(repayments) > ROW_THRESHOLD:
            return _export_repayment_summary(repayments)
 
    return None