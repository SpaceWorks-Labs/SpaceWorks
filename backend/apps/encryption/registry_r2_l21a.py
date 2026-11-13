"""Scoped-PII fields added by release-2 lane L21a (stage review notes, attendance notes, crew answers)."""


def participation_pii_fields(field):
    return (
        field("events.AdmissionStageReview", "notes", "assignment.stage.event.makerspace_id", None, "source", "none"),
        field("events.EventAttendanceReply", "note", "makerspace_id", None, "source", "none"),
        field("events.EventCrewMember", "answers", "makerspace_id", None, "source", "none"),
        field("events.EventCrewMember", "dietary", "makerspace_id", None, "source", "none"),
    )
