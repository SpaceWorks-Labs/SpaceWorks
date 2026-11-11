"""Cleanup follows account/parent identity even after optional inbox deletion."""
import pytest
from uuid import uuid4

from apps.accounts.models import User
from apps.integrations.models_cutover import NotificationLegacyMapping
from apps.notifications.member_push import send_envelope_push
from apps.notifications.models_inbox import NotificationInboxRow
from apps.notifications.models_push import MemberPushDelivery
from apps.notifications.privacy import scrub_account
from tests.notifications.test_support_m1b import push_case  # noqa: F401
from tests.return_helpers import make_member

pytestmark = pytest.mark.django_db


def test_archive_cancels_inbox_independent_children_and_redacts_mapping(push_case):
    case = push_case
    case.prepare(inbox=False)
    child = MemberPushDelivery.objects.create(envelope_delivery=case.parent, push_device=case.device)
    mapping = NotificationLegacyMapping.objects.create(legacy_model="MemberPushDelivery", legacy_id=child.pk,
        canonical_model="MemberPushDelivery", canonical_id=child.pk, makerspace=case.space, snapshot="private")
    scrub_account(case.user, case.space.pk)
    child.refresh_from_db()
    mapping.refresh_from_db()
    assert child.status == "canceled" and not child.retryable and not mapping.snapshot
    scrub_account(case.user, case.space.pk, purge=True)
    assert not MemberPushDelivery.objects.filter(pk=child.pk).exists()


def test_shared_contact_staff_inbox_is_untouched_by_member_cleanup(push_case):
    case = push_case
    case.prepare()
    staff = make_member("push-other-kind", case.space)
    assert staff.account_kind == "member"  # one account per person (U-A1); a staff role, another person
    # U-A1: one account per person keeps emails unique (uniq_person_email), so two accounts
    # can no longer share a contact; cleanup still keys on the account, never the address.
    theirs = NotificationInboxRow.objects.create(makerspace=case.space, user=staff,
        feature="bookings", event="confirmed", event_key=uuid4(), title="Private staff", summary="Staff only")
    scrub_account(case.user, case.space.pk)
    case.inbox.refresh_from_db()
    theirs.refresh_from_db()
    assert case.inbox.summary == "" and theirs.summary == "Staff only"


def test_tenant_cleanup_does_not_touch_same_accounts_other_tenant(push_case):
    from tests.return_helpers import make_space
    case = push_case
    case.prepare()
    other = make_space("push-other-tenant")
    row = NotificationInboxRow.objects.create(makerspace=other, user=case.user, event_key=uuid4(),
        feature="bookings", event="confirmed", title="Other private", summary="Other tenant")
    scrub_account(case.user, case.space.pk, purge=True)
    row.refresh_from_db()
    assert row.summary == "Other tenant"


def test_canonical_cleanup_redacts_mapping_before_clearing_its_ownership_context(push_case):
    from apps.integrations.notification_privacy import scrub_account as canonical_scrub
    case = push_case
    parent = case.prepare(inbox=False)
    child = MemberPushDelivery.objects.create(envelope_delivery=parent,
        push_device=case.device, platform=case.grant.platform, status="held")
    mapping = NotificationLegacyMapping.objects.create(legacy_model="MemberPushDelivery", legacy_id=child.pk,
        canonical_model="MemberPushDelivery", canonical_id=child.pk, makerspace=case.space, snapshot="private")
    envelope = parent.envelope
    envelope.source_kind, envelope.source_id = "migration.history", str(child.pk)
    envelope.context = {"legacy_model": "MemberPushDelivery"}
    envelope.save(update_fields=["source_kind", "source_id", "context"])
    case.device.delete()  # Only the parent still proves mapping ownership.
    canonical_scrub(case.user, case.space.pk)
    mapping.refresh_from_db()
    envelope.refresh_from_db()
    assert not mapping.snapshot and envelope.context == {}


def test_account_discovery_finds_an_inbox_independent_parent(push_case, monkeypatch):
    from apps.accounts import account_deletion_discovery as discovery
    case = push_case
    parent = case.prepare(inbox=False)
    MemberPushDelivery.objects.create(envelope_delivery=parent, push_device=case.device,
        platform=case.grant.platform, status="held")
    # Isolate the child selector: no membership, payment or inbox can mask a gap.
    get_model = discovery._model
    monkeypatch.setattr(discovery, "SUBJECT_PATHS", {})
    monkeypatch.setattr(discovery, "_model", lambda label: get_model(label)
        if label == "notifications.MemberPushDelivery" else None)
    assert discovery.tenant_ids(case.user) == {case.space.pk}
