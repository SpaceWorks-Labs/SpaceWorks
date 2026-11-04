"""A/C/D/E read-only readiness and respondent adapters for F."""

from functools import partial

from apps.events.hackathons.admission_models import HackathonConfig, HackathonApplication, HackathonCocRevision
from apps.events.contributions.models_roles import EventRoleAssignment
from apps.events.contributions.models_shifts import EventShift
from apps.events.mentoring.models_queue import EventHelpRequest
from apps.events.programme.providers import ReadinessProvider, Respondent, register_readiness, register_respondents
from apps.events.programme.readiness import EXPECTED_SUMMARIES


def summarize(key, *, event, actor):
    config = HackathonConfig.objects.filter(event=event, enabled=True).first()
    if key in ("coc", "team_limits", "storage", "rubric", "judge_coverage", "reviews") and not config:
        return None
    count = None
    if key == "coc":
        ready = HackathonCocRevision.objects.filter(event=event, revision=config.coc_revision).exists()
    elif key == "team_limits":
        ready = 1 <= config.team_min <= config.team_max <= 100
    elif key == "storage":
        # An allowance alone is not storage/scanner readiness. The actual
        # storage capability adapter must supply this before enablement.
        return {"status": "unavailable", "count": None}
    elif key == "reviews":
        count = HackathonApplication.objects.filter(event=event, state="submitted").count()
        ready = count == 0
    elif key in ("rubric", "judge_coverage"):
        from apps.events.judging.models_definitions import JudgingRound
        from apps.events.judging.projections import summary
        if key == "rubric":
            rounds = list(JudgingRound.objects.filter(event=event))
            ready = bool(rounds) and all(row.mode == "top3" or row.criteria.exists() for row in rounds)
        else:
            ready = summary(event.pk, actor=actor).get("coverage_complete") is True
    elif key == "certificates":
        from apps.events.models_certificate_templates import EventCertificateTemplateRevision
        ready = EventCertificateTemplateRevision.objects.filter(event=event).exists()
    elif key == "door_shifts":
        ready = EventShift.objects.filter(event=event, state="open", kind="volunteer",
            permission_preset__contains=["check_in"], signups__state="approved",
            signups__assignment__state="approved", signups__assignment__imported_inert=False).exists()
    elif key == "mentors":
        from apps.events.mentoring.analytics import summary
        count = summary(actor=actor, event=event)["active_mentors"]
        ready = count > 0
    elif key == "help":
        count = EventHelpRequest.objects.filter(event=event, practice_run_id=None, state="open").count()
        ready = count == 0
    else:
        count = EventRoleAssignment.objects.filter(event=event, state="applied", role="volunteer").count()
        ready = count == 0
    return {"status": "ready" if ready else "action" if key in ("reviews", "help", "approvals") else "missing",
            "count": count}


def respondents(*, event, actor, since, until):
    if not HackathonConfig.objects.filter(event=event, enabled=True).exists():
        return None
    # The funnel asks with since=None (all time); a None bound is no bound, not a lookup value.
    rows = HackathonApplication.objects.filter(event=event).exclude(submitted_at=None)
    if since is not None:
        rows = rows.filter(submitted_at__gte=since)
    if until is not None:
        rows = rows.filter(submitted_at__lt=until)
    rows = rows.values_list("member_id", "submitted_at")
    return True, tuple(Respondent(("member", pk), submitted) for pk, submitted in rows)


def install():
    for key, label, tab, feature, permission in EXPECTED_SUMMARIES:
        register_readiness(ReadinessProvider(key, permission, label, tab, feature, partial(summarize, key)))
    register_respondents(respondents)
