"""CSV safety for masked checklists; never a payment instruction/export."""

import csv
import io
import unicodedata

from .validation import PayoutValidationError


COLUMNS = (
    "batch_id", "obligation_id", "event_id", "event_title", "participant_reference",
    "country", "method", "masked_payee", "currency", "approved_minor", "effective_paid_minor",
    "remaining_minor", "payee_revision", "claim_reference", "decision_reference", "exported_at",
)
NUMERIC_COLUMNS = frozenset({"approved_minor", "effective_paid_minor", "remaining_minor"})


def safe_cell(value):
    if not isinstance(value, str):
        raise PayoutValidationError("invalid_csv_text")
    # Leading whitespace/control characters can hide an Excel formula prefix.
    cleaned = "".join(char for char in value if not unicodedata.category(char).startswith("C"))
    if value != cleaned or cleaned.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + cleaned
    return cleaned


def encode_rows(rows):
    """Closed columns: caller may not smuggle plaintext through arbitrary keys."""
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=COLUMNS, lineterminator="\r\n")
    writer.writeheader()
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(COLUMNS):
            raise PayoutValidationError("invalid_csv_columns")
        masked = row["masked_payee"]
        if (not isinstance(masked, str) or not (masked == "Routing details hidden" or masked == "••••@••••"
                or (masked.startswith("••••") and len(masked) == 8))):
            raise PayoutValidationError("unmasked_csv_payee")
        result = {}
        for key in COLUMNS:
            if key in NUMERIC_COLUMNS:
                from .validation import minor
                result[key] = minor(row[key], zero=True)
            else:
                result[key] = safe_cell(row[key])
        writer.writerow(result)
    return output.getvalue()
