"""A session's effective state, read from the session row plus its append-only amendments.

A closed session is never edited, so what staff decided afterwards is derived here: the
latest duration correction, the member an unattributed device session was assigned to,
and whether staff confirmed it. Callers that list many sessions prefetch `amendments`.
"""

FEATURE = "machines.sessions"


def sessions_on(makerspace):
    from apps.makerspaces.platform import feature_enabled
    return feature_enabled(makerspace, FEATURE)


def require_sessions(makerspace):
    from rest_framework.exceptions import NotFound
    if not sessions_on(makerspace):
        raise NotFound()
    return makerspace


def _amendments(session):
    return list(session.amendments.all())


def _latest(session, kind):
    rows = [row for row in _amendments(session) if row.kind == kind]
    return rows[-1] if rows else None


def effective_minutes(session):
    correction = _latest(session, "correct")
    return correction.minutes if correction is not None else session.duration_minutes


def effective_member_id(session):
    assignment = _latest(session, "assign")
    return assignment.member_id if assignment is not None else session.member_id


def effective_member(session):
    assignment = _latest(session, "assign")
    return assignment.member if assignment is not None else session.member


def confirmed(session):
    return _latest(session, "confirm") is not None


def needs_review(session):
    """Closed, auto-stopped or unattributed, and not yet confirmed by staff."""
    if session.ended_at is None:
        return False
    return (session.flagged or session.member_id is None) and not confirmed(session)


def status(session):
    if session.ended_at is None:
        return "live"
    return "review" if needs_review(session) else "closed"


def charge_state(session, payment=None):
    """job | none | running | raised | held | free -- what money this session carries."""
    if session.service_request_id:
        return "job"
    if not session.billable:
        return "none"
    if payment is not None:
        return "raised"
    if session.ended_at is None:
        return "running"
    if needs_review(session):
        return "held"
    return "free"
