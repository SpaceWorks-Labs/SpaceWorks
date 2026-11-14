"""Decision 533: retained certification contexts map safely or terminate delivery."""
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.integrations.models_contract import NotificationDelivery, NotificationEnvelope
from apps.integrations.notification_delivery import ensure_deliveries
from apps.integrations.notification_sources import source_eligible
from apps.integrations.notification_tasks import deliver_envelope, runnable_deliveries
from apps.machines.models import CertificationType, MachineAccessGrant, MachineType
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.notifications_p2_broadcasts import notify_broadcast
from apps.notifications.models_broadcasts import MemberBroadcast
from apps.notifications.models_inbox import NotificationInboxRow
from apps.notifications.models_preferences import NotificationPreference
from tests.modules.test_switch_matrix_objects_rest_support import switch
from tests.notifications.routes_support_cx11b_g6 import world
from tests.payments.account_helpers import make_payer

pytestmark = [pytest.mark.django_db, pytest.mark.area_notifications]


@pytest.fixture
def campaign(settings, monkeypatch):
    settings.NOTIFICATION_FANOUT_VIA_CELERY = False
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda *_: None)
    space, actor, _, stranger, _ = world(False, staff=True)
    member = make_payer("g6-legacy-" + uuid4().hex[:8], space)
    kind = MachineType.objects.create(makerspace=space, name="Legacy audience", slug="legacy-audience")
    certification = CertificationType.objects.create(makerspace=space, machine_type=kind, name="Old induction")
    grant = MachineAccessGrant.objects.create(makerspace=space, member=member, machine_type=kind, granted_by=actor)
    NotificationPreference.objects.create(makerspace=space, user=member,
        category="members", channels=["in_app"], email_fallback=False)
    row = MemberBroadcast.objects.create(makerspace=space, created_by=actor,
        title="Retained broadcast", body="A stored audience context.")
    notify_broadcast(row, user_id=member.pk, segment={"machine_type_id": kind.pk})
    envelope = NotificationEnvelope.objects.get(source_kind="membership.broadcast", source_id=str(row.pk))
    ensure_deliveries(envelope)
    delivery = NotificationDelivery.objects.get(envelope=envelope)
    assert (delivery.channel, delivery.state, delivery.attempt_count) == ("in_app", "retrying", 0)
    return SimpleNamespace(space=space, actor=actor,
        foreign_space=MakerspaceMembership.staff_tracks.get(user=stranger).makerspace,
        member=member, kind=kind, certification=certification, grant=grant, row=row,
        envelope=envelope, delivery=delivery)


def stored_segment(case, segment):
    # Simulate the persisted pre-319 context without changing the source revision.
    case.envelope.context = {**case.envelope.context, "segment": segment}
    case.envelope.save(update_fields=["context"])


def assert_terminal(case, state, error):
    case.envelope.refresh_from_db()
    case.delivery.refresh_from_db()
    assert case.envelope.processed_at is not None
    assert (case.delivery.state, case.delivery.last_error, case.delivery.attempt_count,
            case.delivery.retryable, case.delivery.next_attempt_at, case.delivery.claim_until) == (
                state, error, 1, False, None, None)
    assert not runnable_deliveries(case.envelope.deliveries.all()).exists()
    assert list(case.envelope.deliveries.values_list("pk", flat=True)) == [case.delivery.pk]


@pytest.mark.parametrize("also_machine_type", [False, True])
def test_legacy_certification_context_maps_to_live_grant_and_replay_is_inert(campaign, also_machine_type):
    case = campaign
    segment = {"certification_id": case.certification.pk}
    if also_machine_type:
        segment["machine_type_id"] = case.kind.pk
    stored_segment(case, segment)
    assert source_eligible(case.envelope) is True
    deliver_envelope(case.envelope.pk)
    assert_terminal(case, "sent", "")
    rows = NotificationInboxRow.objects.filter(makerspace=case.space, user=case.member, event="broadcast")
    assert list(rows.values_list("title", flat=True)) == [case.row.title]
    processed_at, updated_at = case.envelope.processed_at, case.delivery.updated_at
    deliver_envelope(case.envelope.pk)
    assert_terminal(case, "sent", "")
    assert (case.envelope.processed_at, case.delivery.updated_at) == (processed_at, updated_at)
    assert rows.count() == 1
    assert case.envelope.context["segment"] == segment


@pytest.mark.parametrize("reason", ["missing", "foreign", "conflict", "invalid", "no_grant", "revoked", "expired",
                                    "machines_off", "canonical_machines_off", "plan_deleted"])
def test_legacy_or_disabled_segment_skips_once_without_crash_or_retry(campaign, reason):
    case = campaign
    segment = {"certification_id": case.certification.pk}
    if reason == "missing":
        segment["certification_id"] = 2**31 - 1
    elif reason == "foreign":
        kind = MachineType.objects.create(makerspace=case.foreign_space, name="Foreign", slug="foreign-legacy")
        cert = CertificationType.objects.create(makerspace=case.foreign_space, machine_type=kind, name="Foreign induction")
        segment["certification_id"] = cert.pk
    elif reason == "conflict":
        kind = MachineType.objects.create(makerspace=case.space, name="Different", slug="different-legacy")
        segment["machine_type_id"] = kind.pk
    elif reason == "invalid":
        segment["certification_id"] = "not-an-id"
    elif reason == "no_grant":
        kind = MachineType.objects.create(makerspace=case.space, name="No access", slug="no-access-legacy")
        cert = CertificationType.objects.create(makerspace=case.space, machine_type=kind, name="No access induction")
        segment["certification_id"] = cert.pk
    elif reason in {"revoked", "expired"}:
        field = "revoked_at" if reason == "revoked" else "expires_at"
        setattr(case.grant, field, timezone.now() - timedelta(seconds=1))
        case.grant.save(update_fields=[field])
    elif reason in {"machines_off", "canonical_machines_off"}:
        switch(case.space, "machines")
        if reason == "canonical_machines_off":
            segment = {"machine_type_id": case.kind.pk}
    elif reason == "plan_deleted":
        segment["plan_id"] = 2**31 - 1
    stored_segment(case, segment)
    assert source_eligible(case.envelope) is False
    deliver_envelope(case.envelope.pk)
    assert_terminal(case, "skipped", "live_eligibility_changed")
    processed_at, updated_at = case.envelope.processed_at, case.delivery.updated_at
    deliver_envelope(case.envelope.pk)
    assert_terminal(case, "skipped", "live_eligibility_changed")
    assert (case.envelope.processed_at, case.delivery.updated_at) == (processed_at, updated_at)
    assert not NotificationInboxRow.objects.filter(makerspace=case.space, user=case.member).exists()
    assert case.envelope.context["segment"] == segment


@pytest.mark.parametrize("mapped", [False, True])
def test_retained_deferred_fanout_accepts_legacy_segment_without_retrying(campaign, mapped):
    case = campaign
    row = MemberBroadcast.objects.create(makerspace=case.space, created_by=case.actor,
        title="Old deferred job", body="Retained kwargs.")
    segment = {"certification_id": case.certification.pk if mapped else 2**31 - 1}
    for _ in range(2):
        notify_broadcast(row, user_id=case.member.pk, segment=segment)
    envelope = NotificationEnvelope.objects.get(source_kind="membership.broadcast", source_id=str(row.pk))
    assert envelope.context["segment"] == segment
    assert source_eligible(envelope) is mapped
    deliver_envelope(envelope.pk)
    envelope.refresh_from_db()
    assert envelope.processed_at is not None
    processed_at = envelope.processed_at
    deliver_envelope(envelope.pk)
    envelope.refresh_from_db()
    assert envelope.processed_at == processed_at
    assert not runnable_deliveries(envelope.deliveries.all()).exists()
    assert list(envelope.deliveries.values_list("channel", "state", "attempt_count")) == (
        [("in_app", "sent", 1)] if mapped else [])
