"""Departure includes account-only ownership, historical tenants and source routing."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.db.models import Q
from django.utils import timezone

from apps.accounts import account_deletion_discovery as discovery
from apps.accounts.models import DeviceGrant, NativeAppRegistration
from apps.boxes.models import Box, BoxScan
from apps.data_export.types import TenantPredicate
from apps.evidence.models import EvidencePhoto
from apps.integrations.models import PushDevice
from apps.makerspaces.models import MakerspaceMembership, MembershipRequest
from apps.notifications.models import MemberNotificationPreference, NotificationInboxRow
from apps.organizations.models import Organization, OrganizationMembership
from tests.accounts import deletion_factories as make
from tests.accounts.account_factories import make_membership

pytestmark = pytest.mark.django_db


def test_empty_account_has_no_tenants():
    assert discovery.tenant_ids(make.identity()) == set()


@pytest.mark.parametrize("domain", ["request", "booking", "registration", "service", "payment", "application", "evidence", "inbox", "preferences"])
def test_account_only_participation_is_discovered_without_membership(domain):
    user, tenant = make.identity(), make.space()
    if domain == "request":
        make.request(user, tenant)
    elif domain == "booking":
        make.booking(user, tenant)
    elif domain == "registration":
        make.registration(user, tenant)
    elif domain == "service":
        make.service_job(user, tenant)
    elif domain == "payment":
        make.payment(user, tenant)
    elif domain == "application":
        MembershipRequest.objects.create(user=user, makerspace=tenant, kind="request", state="requested")
    elif domain == "evidence":
        EvidencePhoto.objects.create(
            makerspace=tenant, uploaded_by=user, evidence_type="issue", object_key=f"deletion/{uuid4().hex}",
        )
    elif domain == "inbox":
        NotificationInboxRow.objects.create(
            user=user, makerspace=tenant, event_key=uuid4(), feature="events", event="registered", title="Event",
        )
    else:
        MemberNotificationPreference.objects.create(user=user, makerspace=tenant, feature="events", channel="email")
    assert not MakerspaceMembership.objects.filter(user=user).exists()
    assert discovery.tenant_ids(user) == {tenant.pk}


def test_revoked_memberships_and_archived_spaces_are_still_discovered():
    user, tenant = make.identity(), make.space()
    make_membership(user, tenant, status="revoked")
    tenant.archived_at = timezone.now()
    tenant.save(update_fields=["archived_at"])
    assert discovery.tenant_ids(user) == {tenant.pk}


def test_payment_includes_owning_and_via_spaces_without_memberships():
    user, owning, via = make.identity(), make.space(), make.space()
    make.payment(user, owning, status="paid_online", via=via)
    assert discovery.tenant_ids(user) == {owning.pk, via.pk}


def test_event_registration_includes_host_activity_and_money_routes():
    user, host, activity, money = make.identity(), make.space(), make.space(), make.space()
    make.registration(user, host, registered_via_makerspace=activity, payment_via_makerspace=money)
    assert discovery.tenant_ids(user) == {host.pk, activity.pk, money.pk}


def test_legacy_service_jobs_supply_missing_member_tenant():
    user, tenant = make.identity(), make.space()
    make.service_job(user, tenant, legacy=True, status="collected")
    assert discovery.tenant_ids(user) == {tenant.pk}


def test_recipient_email_logs_include_owning_tenant_and_ignore_platform_null():
    from apps.integrations.models_email import EmailLog
    user, tenant = make.identity(), make.space()
    for scope in (tenant, None):
        EmailLog.objects.create(recipient=user, makerspace=scope, to_email="member@example.test", subject="Notice")
    assert discovery.tenant_ids(user) == {tenant.pk}


def test_staff_authorship_is_not_member_ownership():
    user, other, tenant = make.identity(), make.identity(), make.space()
    make.service_job(other, tenant, requester=user)
    assert discovery.tenant_ids(user) == set()
    assert discovery.tenant_ids(other) == {tenant.pk}


def test_scan_subject_path_follows_borrower_instead_of_staff_actor():
    user, staff, tenant = make.identity(), make.identity(), make.space()
    request = make.request(user, tenant)
    box = Box.objects.create(makerspace=tenant, label="Borrower evidence")
    BoxScan.objects.create(makerspace=tenant, request=request, box=box, actor=staff, context="issue")
    assert discovery.tenant_ids(user) == {tenant.pk}
    assert discovery.tenant_ids(staff) == set()


def test_unrelated_accounts_do_not_add_tenants_and_null_routing_is_removed():
    user, other, own, foreign = make.identity(), make.identity(), make.space(), make.space()
    make.payment(user, own, via=None)
    make.payment(other, foreign)
    assert discovery.tenant_ids(user) == {own.pk}


def test_push_destinations_are_included_even_when_inactive():
    user, tenant, now = make.identity(), make.space(), timezone.now()
    registration = NativeAppRegistration.objects.create(
        app_id="test.deletion", platform="apple", environment="development", verifier_config_key="test",
        status=NativeAppRegistration.Status.APPROVED,
    )
    grant = DeviceGrant.objects.create(
        registration=registration, user=user, platform="apple", app_id="test.deletion",
        signing_identity="test", environment="development", attestation_subject_fingerprint="a" * 64,
        attested_at=now, last_used_at=now,
    )
    PushDevice.objects.create(user=user, makerspace=tenant, device_grant=grant,
        provider="apns", environment="development", token_ciphertext="secret",
        token_fingerprint="b" * 64, active=False)
    assert discovery.tenant_ids(user) == {tenant.pk}


def test_all_ownership_and_tenant_predicate_paths_are_considered(monkeypatch):
    user = make.identity()
    recorded = []

    class Rows:
        def filter(self, own):
            assert own == Q(owner_id=user.pk) | Q(parent__member_id=user.pk)
            return self

        def values_list(self, path, *, flat):
            assert flat
            recorded.append(path)
            return {"makerspace": [1], "host__makerspace": [2], "local__makerspace": [3, None]}[path]

    rows = Rows()
    monkeypatch.setattr(discovery, "SUBJECT_PATHS", {"sample.Owned": ("owner", "parent__member")})
    monkeypatch.setattr(discovery, "DATASET_SPECS", {"sample.Owned": (
        "sample.csv", TenantPredicate(("makerspace", "host__makerspace"), ("local__makerspace",)),
    )})
    model = SimpleNamespace(_meta=SimpleNamespace(label="sample.Owned"), _default_manager=rows, objects=rows)
    monkeypatch.setattr(discovery, "_model", lambda label: model if label == "sample.Owned" else None)
    assert discovery.tenant_ids(user) == {1, 2, 3}
    assert recorded == ["makerspace", "host__makerspace", "local__makerspace"]


def test_tombstoned_domains_do_not_require_missing_tables(monkeypatch):
    monkeypatch.setattr(discovery, "_model", lambda label: None)
    assert discovery.tenant_ids(make.identity()) == set()


def test_organization_set_includes_suspended_membership_and_excludes_others():
    user, other = make.identity(), make.identity()
    org = Organization.objects.create(name="Departed", slug="departed")
    foreign = Organization.objects.create(name="Foreign", slug="foreign")
    OrganizationMembership.objects.create(user=user, organization=org, status="suspended")
    OrganizationMembership.objects.create(user=other, organization=foreign)
    assert discovery.organization_ids(user) == {org.pk}
