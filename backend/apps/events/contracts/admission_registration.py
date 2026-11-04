"""Query-free installation of production A/F/P/C adapters in web and workers."""
from django.conf import settings
from django.http import Http404
from apps.accounts.models import User
from apps.events import event_authority
from apps.events.models import Event
from apps.events.hackathons.admission_models import HackathonApplication
from apps.events.programme.admission_forms import AdmissionForms
from apps.events.programme.prepared_forms import EventIntentBinding

_event_binding = EventIntentBinding()


class _IntentBindings:
    """One installed binding: stage responses resolve through R, never the DOB resolver."""

    def require_binding(self, **kwargs):
        if str(getattr(kwargs["actual_subject"], "kind", "")) == "stage_response":
            from apps.events.staged_forms.prefill_provider import require_binding
            return require_binding(**kwargs)
        return _event_binding.require_binding(**kwargs)


_intent_binding = _IntentBindings()


def context_gate(*, event, actor, request=None):
    from apps.events.answer_derivations.subjects import require_event
    from apps.events.hackathons.admission_transactions import require_member
    require_event(event)
    require_member(actor)
    if request is not None:
        from apps.makerspaces.origin_scope import object_in_staff_origin_scope
        if not object_in_staff_origin_scope(request, event):
            raise Http404


def readiness(*, actor_id):
    from apps.encryption.account_readiness import assert_ready
    from apps.encryption.crypto import PiiUnavailable
    try:
        assert_ready()
    except PiiUnavailable:
        return "unavailable"
    return "ready"


def subject_conflict(*, event_id, reviewer_id, application_ids):
    from apps.events.hackathons.team_models import HackathonTeamMember
    from apps.events.mentoring.policy import is_conflicted
    owners = HackathonApplication.objects.filter(event_id=event_id, pk__in=application_ids).values("member_id")
    teams = HackathonTeamMember.objects.filter(event_id=event_id, member_id__in=owners,
        state="active").values_list("team_id", flat=True)
    return any(is_conflicted(member_id=reviewer_id, team_id=team_id) for team_id in set(teams))


def reviewer_candidates(*, event_id):
    event = Event.objects.get(pk=event_id)
    return tuple(actor.pk for actor in User.objects.filter(is_active=True, access_status="active",
        is_tenant_dump_stub=False).order_by("pk") if event_authority.can(actor, event, "review_applications"))


def enqueue_notice(*, event_id, member_id, application_id, revision, kind):
    from apps.integrations.notification_outbox import emit
    from apps.events.hackathons.admission_notifications import render_notice
    event = Event.objects.get(pk=event_id)
    app = HackathonApplication.objects.get(pk=application_id, event_id=event_id, member_id=member_id)
    rendered = render_notice(kind=kind, application_url=f"/member/events/{event_id}/application")
    emit(makerspace=event.makerspace, recipient=app.member, feature="events", stream="events",
        event=kind, audience="member", source_kind="events.application", source_id=str(app.pk),
        revision=str(revision), subject=app, dedup_key=f"event-application:{app.pk}:{revision}:{kind}",
        context={"event_id": event_id}, rendered={"subject": rendered["title"], "text": rendered["body"]})


def storage_budget_used(*, event_id):
    from apps.events.submissions.models_assets import EventAssetUsage
    row = EventAssetUsage.objects.filter(event_id=event_id).first()
    return row.used_bytes + row.reserved_bytes if row else 0


def storage_budget_limit(*, event_id):
    from apps.makerspaces.limits import is_self_host
    from apps.events.submissions.quota import MANAGED_ALLOWANCE
    return None if is_self_host() else MANAGED_ALLOWANCE


def upload_policy_supported(*, name, version):
    from apps.maker_formats.registry import POLICY_NAME, POLICY_VERSION
    return name == POLICY_NAME and type(version) is int and version == POLICY_VERSION


def assert_encryption_ready(*, event_id):
    from apps.encryption.write_fence import assert_mapped_write_allowed
    assert_mapped_write_allowed(Event.objects.values_list("makerspace_id", flat=True).get(pk=event_id))


def has_submission(*, team_id):
    from apps.events.submissions.admission_reopen import has_submission as check
    from apps.events.hackathons.team_models import HackathonTeam
    return check(team_id=team_id, event_id=HackathonTeam.objects.values_list("event_id", flat=True).get(pk=team_id))


def reopen_submission_locked(*, team_id, actor_id, reason_code, locks):
    from apps.events.submissions.admission_reopen import reopen_submission_locked as reopen
    return reopen(team_id=team_id, event_id=locks.event_id, actor_id=actor_id, reason=reason_code, locks=locks)


def install():
    from apps.accounts.saved_details.subject_binding import install_subject_binding
    from apps.events.hackathons.admission_ports import install_production
    from apps.events.contributions.ports import install as install_contributors
    from apps.events.contributions.runtime import ContributorPorts
    from apps.events.contributions.runtime_notices import register
    from apps.events.contracts.photo_registration import public_member_card
    from apps.events.hackathons.admission_date_notices import register_date_notices
    from apps.events.programme.providers import register_answer_projector
    from apps.events.programme.answer_projection import registration_answers
    from apps.events.hackathons.team_notifications import register as register_teams
    install_subject_binding(_intent_binding)
    install_contributors(ContributorPorts())
    install_production(forms=AdmissionForms(), context_gate=context_gate, readiness=readiness,
        public_profile=public_member_card, reviewer_candidates=reviewer_candidates,
        subject_conflict=subject_conflict, has_submission=has_submission,
        reopen_submission_locked=reopen_submission_locked, enqueue_notice=enqueue_notice,
        assert_encryption_ready=assert_encryption_ready, storage_budget_used=storage_budget_used,
        storage_budget_limit=storage_budget_limit, upload_policy_supported=upload_policy_supported,
        default_attendance_required=lambda **kwargs: True)
    register_date_notices()
    register()
    register_teams()
    register_answer_projector(registration_answers)
