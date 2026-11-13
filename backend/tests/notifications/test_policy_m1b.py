"""Live matrix, source, account, scope and intersected opt-outs before device I/O."""
import pytest
from django.utils import timezone

from apps.integrations.models import NotificationPreference as Matrix
from apps.makerspaces.models import MakerspaceMembership
from apps.notifications.member_push import send_envelope_push
from apps.notifications.models import MemberNotificationPreference
from apps.notifications.models_preferences import NotificationPreference
from apps.notifications.models_push import MemberPushDelivery
from tests.notifications.test_support_m1b import push_case  # noqa: F401

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("gate", ["native_push_matrix", "mobile.push", "platform_credentials",
    "source_module", "unservable", "source_deleted", "source_changed", "cutover_paused"])
def test_global_gate_revoked_after_enqueue_prevents_provider_io(push_case, gate):
    from apps.integrations.models_cutover import NotificationCutover
    case = push_case
    case.prepare()
    if gate == "native_push_matrix":
        Matrix.objects.filter(makerspace=case.space, channel="native_push").update(enabled=False)
    elif gate == "mobile.push":
        case.space.enabled_features.remove(gate)
        case.space.save(update_fields=["enabled_features"])
    elif gate == "platform_credentials":
        case.platform.set_fcm_service_account("")
        case.platform.set_apns_private_key("")
        case.platform.save()
    elif gate == "source_module":
        case.space.enabled_modules.remove("bookings")
        case.space.save(update_fields=["enabled_modules"])
    elif gate == "unservable":
        case.space.archived_at = timezone.now()
        case.space.save(update_fields=["archived_at"])
    elif gate == "source_deleted":
        # Payments are immutable; only the purge path may delete one, under its GUC.
        from django.db import connection, transaction
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL app.allow_immutable_delete = 'on'")
            case.charge.delete()
    elif gate == "source_changed":
        case.source_active = False
    else:
        NotificationCutover.objects.filter(pk=1).update(sending_enabled=False)
    result = send_envelope_push(case.parent, case.rendered)
    assert not result.accepted
    assert case.calls == [] and case.oauth_calls == []


@pytest.mark.parametrize("gate", ["membership_revoked", "receives_notifications", "personal_native_push",
    "canonical_selection", "revoked_grant", "unapproved_registration", "inactive_device",
    "inactive_account", "restricted_account", "deleted_account", "stub_account", "generation"])
def test_recipient_or_device_revocation_is_rechecked(push_case, gate):
    case = push_case
    case.prepare()
    if gate in {"membership_revoked", "receives_notifications"}:
        membership = MakerspaceMembership.objects.get(makerspace=case.space, user=case.user)
        membership.status = "revoked" if gate == "membership_revoked" else membership.status
        membership.receives_notifications = gate != "receives_notifications"
        membership.save(update_fields=["status", "receives_notifications"])
    elif gate == "personal_native_push":
        MemberNotificationPreference.objects.create(makerspace=case.space, user=case.user,
            feature="bookings", channel="native_push", enabled=False)
    elif gate == "canonical_selection":
        NotificationPreference.objects.filter(makerspace=case.space, user=case.user).update(channels=["in_app"])
    elif gate == "revoked_grant":
        type(case.grant).objects.filter(pk=case.grant.pk).update(status="revoked")
    elif gate == "unapproved_registration":
        registration = case.grant.registration
        registration.status = "pending"
        registration.save(update_fields=["status"])
    elif gate == "inactive_device":
        type(case.device).objects.filter(pk=case.device.pk).update(active=False)
    else:
        fields = {"inactive_account": {"is_active": False}, "restricted_account": {"access_status": "restricted"},
            "deleted_account": {"deletion_requested_at": timezone.now()}, "stub_account": {"is_tenant_dump_stub": True},
            "generation": {"credential_generation": case.user.credential_generation + 1}}[gate]
        type(case.user).objects.filter(pk=case.user.pk).update(**fields)
    assert not send_envelope_push(case.parent, case.rendered).accepted
    assert case.calls == []


@pytest.mark.parametrize("audience", ["member", "requester"])
def test_verified_account_only_owner_receives_push(push_case, audience):
    case = push_case
    MakerspaceMembership.objects.filter(makerspace=case.space, user=case.user).delete()
    case.prepare(inbox=False, audience=audience)
    assert send_envelope_push(case.parent, case.rendered).accepted
    assert len(case.calls) == 1


@pytest.mark.parametrize("scope", [
    {"category_id": -1}, {"machine_id": True}, {"machine_type_id": "1"}, {"contact": "secret"}, [],
    {"contact": None},  # A null never hides an unknown key.
])
def test_malformed_persisted_scope_fails_closed(push_case, scope):
    case = push_case
    case.prepare()
    type(case.envelope).objects.filter(pk=case.envelope.pk).update(scope=scope)
    assert not send_envelope_push(case.parent, case.rendered).accepted
    assert case.calls == []


def test_scoped_requester_deselection_reloads_envelope_subject(push_case):
    from apps.integrations.models_recipients import NotificationRecipient, RecipientCategoryScope
    from apps.inventory.models import Category
    from tests.return_helpers import make_member
    case = push_case
    category = Category.objects.create(makerspace=case.space, name="Subject", slug="subject")
    case.prepare(audience="requester", scope={"category_id": category.pk})
    staff = make_member("selected-push-staff", case.space)
    rule = NotificationRecipient.objects.create(makerspace=case.space, feature="bookings",
        event="confirmed", kind="user", user=staff)
    RecipientCategoryScope.objects.create(recipient=rule, category=category)
    assert not send_envelope_push(case.parent, case.rendered).accepted
    assert case.calls == []


@pytest.mark.parametrize("tenant,selected,legacy,expected", [
    (True, True, True, True), (False, True, True, False),
    (True, False, True, False), (True, True, False, False), (False, False, False, False),
])
def test_opt_out_intersection_cannot_grant_a_tenant_channel(push_case, tenant, selected, legacy, expected):
    case = push_case
    case.prepare()
    Matrix.objects.filter(makerspace=case.space, channel="native_push").update(enabled=tenant)
    NotificationPreference.objects.filter(makerspace=case.space, user=case.user).update(
        channels=["native_push"] if selected else [])
    MemberNotificationPreference.objects.create(makerspace=case.space, user=case.user,
        feature="bookings", channel="native_push", enabled=legacy)
    assert send_envelope_push(case.parent, case.rendered).accepted is expected
    assert len(case.calls) == int(expected)


def test_frozen_source_boundary_stops_claim_and_provider_call(push_case):
    from contextlib import contextmanager
    from unittest.mock import patch
    from apps.tenant_migration.gate_errors import SourceMigrationGateClosed
    case = push_case
    case.prepare()

    @contextmanager
    def frozen(space_id):
        raise SourceMigrationGateClosed("frozen")
        yield

    with patch("apps.notifications.member_push.boundary_tenant_write", frozen):
        with pytest.raises(SourceMigrationGateClosed):
            send_envelope_push(case.parent, case.rendered)
    assert not MemberPushDelivery.objects.exists() and case.calls == []


def test_staff_push_uses_own_account_and_fixed_tenant_grant(push_case, monkeypatch):
    from apps.accounts.models import DeviceGrant
    from apps.accounts.models_mfa import UserMFA
    from apps.integrations.models_push import PushDevice
    from apps.integrations.notification_sources import SOURCES, NotificationSource
    from tests.return_helpers import make_member
    case = push_case
    member_user = case.user
    staff = make_member("push-native-staff", case.space)
    UserMFA.objects.create(user=staff, enabled_at=timezone.now())
    grant = DeviceGrant.objects.create(user=staff, registration=case.grant.registration,
        authority="staff", staff_makerspace_id=case.space.pk, login_method="password",
        credential_generation=staff.credential_generation, platform=case.grant.platform,
        app_id=case.grant.app_id, signing_identity=case.grant.signing_identity,
        environment=case.grant.environment, attested_at=timezone.now(), last_used_at=timezone.now(),
        attestation_subject_fingerprint="s" * 64)
    device = PushDevice(user=staff, makerspace=case.space, device_grant=grant,
        provider=case.device.provider, environment="development", token_fingerprint="s" * 64)
    device.set_token("staff-token")
    device.save()
    NotificationPreference.objects.create(makerspace=case.space, user=staff,
        category="bookings", channels=["native_push"], email_fallback=False)
    monkeypatch.setitem(SOURCES, "test.push", NotificationSource(
        eligible=lambda e: e.recipient_id == staff.pk and e.makerspace_id == case.space.pk))
    case.user = staff
    case.prepare(inbox=False, audience="staff")
    case.rendered["text"] = "Private staff booking detail"
    assert send_envelope_push(case.parent, case.rendered).accepted
    child = MemberPushDelivery.objects.get(envelope_delivery=case.parent)
    assert child.push_device_id == device.pk
    assert not MemberPushDelivery.objects.filter(envelope_delivery=case.parent, push_device__user=member_user).exists()
    assert len(case.calls) == 1


def test_member_grant_never_supplies_staff_audience_authority(push_case):
    from apps.notifications.member_push_policy import device_allowed
    case = push_case
    case.prepare()
    case.envelope.audience = "staff"
    assert not device_allowed(case.device, case.envelope)


def test_registration_from_other_tenant_cannot_receive_push_here(push_case):
    from tests.return_helpers import make_space
    from tests.device_helpers import make_native_app_registration
    from apps.accounts.models import DeviceGrant
    from apps.integrations.models_push import PushDevice
    case = push_case
    other = make_space("push-registration-other")
    app = make_native_app_registration(makerspace=other, platform=case.grant.platform)
    grant = DeviceGrant.objects.create(user=case.user, registration=app,
        authority="member", platform=app.platform, app_id=app.app_id, environment=app.environment,
        signing_identity="TEAM.org.spaceworks.app", attestation_subject_fingerprint="o" * 64,
        credential_generation=case.user.credential_generation, login_method="password",
        attested_at=timezone.now(), last_used_at=timezone.now())
    device = PushDevice(user=case.user, makerspace=case.space, device_grant=grant,
        provider=case.device.provider, environment="development", token_fingerprint="o" * 64)
    device.set_token("other-tenant-app")
    device.save()
    case.prepare(inbox=False)
    assert send_envelope_push(case.parent, case.rendered).accepted
    assert MemberPushDelivery.objects.get(envelope_delivery=case.parent, push_device=device).status == "skipped"
    assert len(case.calls) == 1
