"""Organization cohort arithmetic, excluding distinct-person consent snapshots."""

from .report_fields_hi import COMMUNICATION_COUNTS, COMMUNICATION_GROUPS
from .reports_hi_common import combine_counts, percent, ratio


def combine_communications(rows_by_space, *, limit):
    cohorts = [(space_id, [row for row in rows if row.get("measurement") != "current_consent_snapshot"])
               for space_id, rows in rows_by_space]
    rows = combine_counts(cohorts, limit=limit, groups=COMMUNICATION_GROUPS, counts=COMMUNICATION_COUNTS,
                          rates=(("success_rate_percent", "sent_count", "delivery_count"),),
                          latest=("last_activity_at",))
    for row in rows:
        messaging = row["channel"] in ("sms", "whatsapp")
        row["read_rate_percent"] = percent(
            row["read_rate_numerator"] if messaging else row["inbox_read_count"],
            row["read_rate_denominator"] if messaging else row["inbox_created_count"],
        )
        for rate in ("delivery_rate", "read_rate"):
            row[rate] = ratio(row[f"{rate}_numerator"], row[f"{rate}_denominator"])
    return rows
