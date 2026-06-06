# import os
# import csv
# import uuid
# from datetime import datetime
# from pathlib import Path

# # env_path = Path(__file__).resolve().parent.parent.parent/".env.app"
# # load_dotenv(env_path)

# EXPORT_DIR = os.getenv("EXPORT_DIR", "./exports")
# ROW_THRESHOLD = int(os.getenv("ROW_THRESHOLD", 5))


# def _ensure_dir():
#     Path(EXPORT_DIR).mkdir(parents=True, exist_ok=True)


# def _timestamp() -> str:
#     return datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + str(uuid.uuid4())[:6]


# def _write_csv(filename: str, rows: list[dict]) -> str | None:
#     """
#     Write list of dicts to CSV safely.
#     Returns file path or None.
#     """

#     if not rows:
#         return None

#     _ensure_dir()

#     path = os.path.join(EXPORT_DIR, filename)

#     # key handling (avoids key mismatch crash)
#     keys = set()

#     for row in rows:
#         for k in row.keys():
#             keys.add(k)

#     fieldnames = sorted(keys)

#     try:
#         with open(path, "w", newline="", encoding="utf-8") as f:
#             writer = csv.DictWriter(f, fieldnames=fieldnames)
#             writer.writeheader()
#             writer.writerows(rows)

#         return path

#     except Exception as e:
#         print(f"[EXPORT ERROR] {e}")
#         return None


# # EXPORTERS (TOOL-SPECIFIC)
# def _export_overdue_loans(loans: list[dict]) -> str | None:
#     return _write_csv(f"overdue_loans_{_timestamp()}.csv", loans)


# def _export_repayment_summary(repayments: list[dict]) -> str | None:
#     return _write_csv(f"repayment_summary_{_timestamp()}.csv", repayments)


# EXPORT_REGISTRY = {
#     "get_overdue_loans": _export_overdue_loans,
#     "get_repayment_summary": _export_repayment_summary,
# }


# # MAIN EXPORT DECIDER
# def maybe_export(tool_name: str, tool_result: dict) -> str | None:
#     """
#     Decides whether to export tool result as CSV.
#     """

#     if not tool_result:
#         return None

#     # extract rows safely
#     rows = (
#         tool_result.get("rows")
#         or tool_result.get("loans")
#         or tool_result.get("repayments")
#     )

#     if not rows:
#         return None

#     # threshold rule
#     if len(rows) < ROW_THRESHOLD:
#         return None

#     export_fn = EXPORT_REGISTRY.get(tool_name)

#     if not export_fn:
#         return None

#     return export_fn(rows)

import os
import csv
import uuid

from pathlib import Path
from datetime import datetime

EXPORT_DIR = os.getenv("EXPORT_DIR", "./exports")

ROW_THRESHOLD = int(os.getenv("ROW_THRESHOLD", 3))


def _ensure_dir() -> None:
    """
    Create export directory if missing.
    """

    Path(EXPORT_DIR).mkdir(
        parents=True,
        exist_ok=True,
    )


def _generate_dataset_id(
    prefix: str,
) -> str:
    """
    Generate logical dataset identifier.

    Example:
        overdue_loans_20260526_104455_ab12cd
    """

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    short_id = str(uuid.uuid4())[:6]

    return f"{prefix}_" f"{timestamp}_" f"{short_id}"


def export_csv(
    rows: list[dict],
    prefix: str,
) -> tuple[str | None, str | None]:
    """
    Generic CSV exporter.

    Returns:
        (
            dataset_id,
            export_path,
        )

    Cases:
        - no rows:
            (None, None)

        - below threshold:
            (dataset_id, None)

        - success:
            (dataset_id, export_path)

        - failure:
            (None, None)
    """

    if not rows:
        return (None, None)

    dataset_id = _generate_dataset_id(
        prefix=prefix,
    )

    # Skip export for small datasets
    if len(rows) < ROW_THRESHOLD:
        return (dataset_id, None)

    _ensure_dir()

    export_path = os.path.join(
        EXPORT_DIR,
        f"{dataset_id}.csv",
    )

    # normalize fieldnames
    fieldnames = sorted({key for row in rows for key in row.keys()})

    try:

        with open(
            export_path,
            "w",
            newline="",
            encoding="utf-8",
        ) as f:

            writer = csv.DictWriter(
                f,
                fieldnames=fieldnames,
                extrasaction="ignore",
            )

            writer.writeheader()

            writer.writerows(rows)

        return (
            dataset_id,
            export_path,
        )

    except Exception as e:

        print(f"[EXPORT ERROR] {e}")
        return (None, None)
