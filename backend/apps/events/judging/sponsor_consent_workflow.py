"""Sole consent writer for participants AND role-only contributors (§12C).

Grant is explicit and asset/hash/purpose specific. Effective reads also require
an own-track frozen submission; a contributor role alone cannot confer access.
"""


from apps.accounts.staff_identity import is_person
from django.contrib.auth import get_user_model
from django.http import Http404
from django.utils import timezone

from .boundary import active_member, assert_locked, audit, changed, command, envelope, mutation, owned
from .errors import ProgrammeError, require_version
from .models_consent import ParticipantSponsorResumeConsent, SponsorResumeConsentHistory
from .ports import runtime
from .serializers import CommandInput, SponsorGrantInput, validated


def _asset(event_id, member_id, asset_id, *, ready=True):
    asset = runtime().participant_asset(asset_id)
    if asset.event_id != event_id or asset.member_id != member_id or asset.purpose != "resume":
        raise Http404
    if ready and (asset.state != "ready" or not asset.current):
        raise ProgrammeError("asset_not_ready", "Choose a ready current résumé.")
    if ready and asset.expires_at and asset.expires_at <= timezone.now():
        raise ProgrammeError("asset_expired", "This résumé has expired.", status=410)
    return asset


def _sponsor(event_id, sponsor_id):
    sponsor = runtime().sponsor(sponsor_id)
    if sponsor.event_id != event_id or not sponsor.active:
        raise Http404
    return sponsor


def _history(row, actor, reason_code):
    SponsorResumeConsentHistory.objects.create(consent=row, revision=row.consent_revision, state=row.state,
        asset_sha256=row.asset_sha256, disclosure_revision=row.disclosure_revision, actor=actor, reason_code=reason_code)


def grant(*, subject, sponsor_id, asset_id, purpose, disclosure_revision, locks):
    """Internal C/B contract: call only with an attested owner-subject lock context."""
    assert_locked(locks)
    if subject.event_id != locks.event_id or subject.owner_member_id not in locks.account_ids:
        raise Http404
    actor = get_user_model().objects.get(pk=subject.owner_member_id)
    active_member(actor)
    runtime().require_subject_owner(actor_id=actor.pk, subject=subject)
    return _grant_locked(event_id=subject.event_id, actor=actor, sponsor_id=sponsor_id, asset_id=asset_id,
                         purpose=purpose, disclosure_revision=disclosure_revision)


def _grant_locked(*, event_id, actor, sponsor_id, asset_id, purpose, disclosure_revision):
    from apps.events.models import Event
    event = Event.objects.get(pk=event_id)
    asset, sponsor = _asset(event_id, actor.pk, asset_id), _sponsor(event_id, sponsor_id)
    if purpose != "recruiting":
        raise ProgrammeError("invalid_purpose", "Choose recruiting consent.", status=400)
    if disclosure_revision != sponsor.disclosure_revision:
        raise ProgrammeError("disclosure_changed", "Review the current sponsor disclosure.")
    row = ParticipantSponsorResumeConsent.objects.filter(event_id=event_id, member=actor, sponsor_id=sponsor_id,
                                                         participant_asset_id=asset_id, purpose=purpose).first()
    if row is None:
        row = ParticipantSponsorResumeConsent(event=event, member=actor, sponsor_id=sponsor_id,
            participant_asset_id=asset_id, asset_sha256=asset.sha256, purpose=purpose,
            disclosure_revision=disclosure_revision, state="granted", consented_at=timezone.now(), expires_at=asset.expires_at)
    else:
        row.version += 1
        row.consent_revision += 1
        row.state, row.revoked_at, row.consented_at = "granted", None, timezone.now()
        row.asset_sha256, row.expires_at = asset.sha256, asset.expires_at
        row.disclosure_revision = disclosure_revision
    row.save()
    _history(row, actor, "explicit_owner_grant")
    audit(event, actor, "sponsor_resume_granted", row, version=row.version, sponsor_id=sponsor_id, asset_id=asset_id)
    return row.pk


def grant_command(event_id, *, actor, data, subject):
    values = validated(SponsorGrantInput, data)
    active_member(actor)
    if subject.event_id != event_id or subject.owner_member_id != actor.pk:
        raise Http404
    runtime().require_subject_owner(actor_id=actor.pk, subject=subject)
    _asset(event_id, actor.pk, values["asset_id"])
    _sponsor(event_id, values["sponsor_id"])
    with mutation(event_id, actor, owner=True, account_ids=(actor.pk,)) as (event, locks):
        def run():
            prior = ParticipantSponsorResumeConsent.objects.filter(event=event, member=actor,
                sponsor_id=values["sponsor_id"], participant_asset_id=values["asset_id"], purpose=values["purpose"]).first()
            if prior:
                require_version(prior, values["expected_version"])
            elif values["expected_version"] != 0:
                raise ProgrammeError("stale_version", "This item changed.", current_version=0)
            pk = grant(subject=subject, sponsor_id=values["sponsor_id"], asset_id=values["asset_id"],
                       purpose=values["purpose"], disclosure_revision=values["disclosure_revision"], locks=locks)
            row = ParticipantSponsorResumeConsent.objects.get(pk=pk)
            return envelope(row, sponsor_id=row.sponsor_id, asset_id=row.participant_asset_id, purpose=row.purpose)
        return command(event, actor, values, path="resume-consents", run=run)


def revoke(*, consent_id, actor_id, locks):
    assert_locked(locks)
    row = ParticipantSponsorResumeConsent.objects.select_for_update().filter(
        pk=consent_id, event_id=locks.event_id, member_id=actor_id).first()
    if row is None:
        raise Http404
    actor = get_user_model().objects.get(pk=actor_id)
    active_member(actor)
    _revoke_locked(row, actor, "owner_revoked")


def _revoke_locked(row, actor, reason_code):
    if row.state == "revoked":
        return
    row.state, row.revoked_at = "revoked", timezone.now()
    row.version += 1
    row.consent_revision += 1
    row.save()
    _history(row, actor, reason_code)
    audit(row.event, actor, "sponsor_resume_revoked", row, version=row.version, asset_id=row.participant_asset_id)


def revoke_command(event_id, consent_id, *, actor, data):
    values = validated(CommandInput, data)
    active_member(actor)
    if not ParticipantSponsorResumeConsent.objects.filter(pk=consent_id, event_id=event_id, member=actor).exists():
        raise Http404
    with mutation(event_id, actor, owner=True, account_ids=(actor.pk,)) as (event, locks):
        def run():
            row = owned(ParticipantSponsorResumeConsent, event_id, consent_id, expected=values["expected_version"])
            revoke(consent_id=row.pk, actor_id=actor.pk, locks=locks)
            row.refresh_from_db()
            return envelope(row, revoked_at=row.revoked_at.isoformat() if row.revoked_at else None)
        return command(event, actor, values, path=f"resume-consents/{consent_id}/revoke", run=run)


def revoke_asset_locked(*, event_id, asset_id, locks, actor_id=None):
    """B invokes on replace/delete in its SAME transaction; no grant inheritance."""
    assert_locked(locks)
    if event_id != locks.event_id:
        raise Http404
    actor = get_user_model().objects.filter(pk=actor_id).first() if actor_id else None
    for row in ParticipantSponsorResumeConsent.objects.select_for_update().filter(
            event_id=event_id, participant_asset_id=asset_id, state="granted").order_by("pk"):
        _revoke_locked(row, actor, "asset_invalidated")


def require_effective_for_asset(*, event_id, member_id, sponsor_id, asset_id, purpose):
    if purpose != "recruiting":
        raise Http404
    from apps.events.models import Event
    event = Event.objects.select_related("makerspace").filter(pk=event_id).first()
    if event is None:
        raise Http404
    runtime().require_programme(event)
    asset, sponsor = _asset(event_id, member_id, asset_id, ready=False), _sponsor(event_id, sponsor_id)
    member = get_user_model().objects.filter(pk=member_id).first()
    from apps.events import event_authority
    if not member or not event_authority._active(member) or not is_person(member):
        raise Http404
    row = ParticipantSponsorResumeConsent.objects.filter(event_id=event_id, member_id=member_id,
        sponsor_id=sponsor_id, participant_asset_id=asset_id, purpose=purpose, state="granted").first()
    now = timezone.now()
    if row is None or row.asset_sha256 != asset.sha256 or not asset.current:
        raise Http404
    if not any(s.event_id == event_id and s.eligible and s.current and member_id in s.member_ids
               and set(s.track_ids) & set(sponsor.track_ids) for s in runtime().snapshots(event_id)):
        raise Http404
    if asset.state == "expired" or (asset.expires_at and asset.expires_at <= now) or (row.expires_at and row.expires_at <= now):
        raise ProgrammeError("asset_expired", "This résumé has expired.", status=410)
    if asset.state != "ready":
        raise Http404


def project_owner(*, event_id, member_id):
    """Only invoke after the caller proved this exact owner; never an organizer vault read."""
    rows = ParticipantSponsorResumeConsent.objects.filter(event_id=event_id, member_id=member_id).order_by("pk")
    return {"consents": [{"id": r.pk, "sponsor_id": r.sponsor_id, "sponsor_name": runtime().sponsor(r.sponsor_id).name,
             "asset_id": r.participant_asset_id, "purpose": r.purpose, "state": r.state,
             "version": r.version, "consented_at": r.consented_at, "expires_at": r.expires_at} for r in rows],
            "sponsors": [{"id": s.id, "name": s.name, "disclosure_revision": s.disclosure_revision}
                         for s in runtime().sponsors(event_id) if s.event_id == event_id and s.active]}
