"""Filter keys shared by saved report preferences and schedules."""


def allowed_report_filters(report_key):
    keys = {"start", "end"}
    from .report_subjects import SUBJECTS
    if any(report_key in adapter.report_keys for adapter in SUBJECTS.values()):
        keys.update(["subject_kind", "subject_id"])
    if report_key == "member-retention":
        keys.add("months")
    if report_key == "payment-reconciliation":
        keys.update(["status", "subject_type"])
    return keys
