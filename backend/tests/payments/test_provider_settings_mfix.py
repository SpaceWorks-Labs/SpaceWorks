from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.models_reauthentication import ReauthenticationSession
from apps.audit.models import AuditLog
from apps.makerspaces.models import MakerspaceMembership, MakerspaceRole
from apps.payments.models import MakerspacePaymentSettings, Payment
from apps.admin_api.serializers_payments import MakerspacePaymentSettingsSerializer
from apps.payments.provider_settings import PaymentProviderConflict
from tests.accounts.reauth_helpers import force_recent_authenticate
from tests.payments.test_machine_payments import service_request
from tests.return_helpers import make_member, make_space, make_user


pytestmark = pytest.mark.django_db
RAZORPAY = {
    "razorpay_key_id": "rzp_test_Merchant123",
    "razorpay_key_secret": "MerchantSecret123",
    "razorpay_webhook_secret": "WebhookSecret456",
}


@pytest.fixture
def merchant():
    space = make_space("provider-settings-mfix")
    manager = make_member("provider-settings-manager", space)
    row = MakerspacePaymentSettings.objects.create(makerspace=space)
    client = APIClient()
    force_recent_authenticate(client, manager)
    return space, manager, row, client, f"/api/v1/admin/makerspace/{space.pk}/payment-settings"


def collection(space, manager, *, provider="stripe", **rail):
    subject = service_request(space, manager)
    return Payment.objects.create(
        makerspace=space, member=manager, created_by=manager,
        subject_type=Payment.SubjectType.MACHINE_SERVICE_REQUEST, subject_id=subject.pk,
        amount=Decimal("2.00"), currency="usd", provider=provider, **rail,
    )


def test_provider_and_credentials_write_only_preserve_and_clear(merchant):
    space, _, row, client, url = merchant
    saved = client.patch(url, {"provider": "razorpay", **RAZORPAY}, format="json")
    assert saved.status_code == 200
    assert saved.data["provider"] == "razorpay"
    assert saved.data["effective_mode"] == "raw"
    for response in (saved, client.get(url)):
        for field, value in RAZORPAY.items():
            assert field not in response.data
            assert value not in str(response.data)
            assert response.data[f"{field}_set"] is True
        for provider in ("stripe", "razorpay"):
            assert response.data[f"{provider}_webhook_url"] == (
                f"http://testserver/api/v1/webhooks/{provider}/{space.public_code}"
            )
    row.refresh_from_db()
    assert row.razorpay_key_secret.startswith("fernet:")
    assert row.razorpay_webhook_secret.startswith("fernet:")
    assert row.get_razorpay_key_secret() == RAZORPAY["razorpay_key_secret"]
    assert row.get_razorpay_webhook_secret() == RAZORPAY["razorpay_webhook_secret"]
    assert client.patch(url, {"default_currency": "INR"}, format="json").status_code == 200
    row.refresh_from_db()
    assert row.get_razorpay_key_secret() == RAZORPAY["razorpay_key_secret"]
    # Clearing one credential leaves omitted siblings intact.
    cleared = client.patch(url, {"razorpay_key_secret": ""}, format="json")
    assert cleared.status_code == 200
    assert cleared.data["razorpay_key_secret_set"] is False
    assert cleared.data["razorpay_webhook_secret_set"] is True
    assert cleared.data["razorpay_key_id_set"] is True
    row.refresh_from_db()
    assert row.razorpay_key_secret == ""
    cleared = client.patch(url, {"razorpay_key_id": "", "razorpay_webhook_secret": ""}, format="json")
    assert cleared.status_code == 200
    assert not cleared.data["razorpay_key_id_set"]
    assert not cleared.data["razorpay_webhook_secret_set"]
    assert client.patch(url, {"provider": "stripe"}, format="json").status_code == 200


@pytest.mark.parametrize("provider", ["stripe", "razorpay"])
@pytest.mark.parametrize("rail", [
    {"stripe_checkout_session_id": "cs_pending"},
    {"stripe_payment_intent_id": "pi_pending", "online_rail": "native_payment_intent"},
    {"external_order_id": "order_pending", "online_rail": "native_payment_intent"},
    {"checkout_url": "https://checkout.example.test/pending"},
    {"stripe_checkout_url": "https://checkout.example.test/legacy"},
])
def test_switch_refuses_pending_other_rail(merchant, provider, rail):
    space, manager, row, client, url = merchant
    row.provider = provider
    row.save()
    collection(space, manager, provider=provider, **rail)
    target = "stripe" if provider == "razorpay" else "razorpay"
    response = client.patch(url, {"provider": target, **RAZORPAY}, format="json")
    assert response.status_code == 409
    assert response.data["code"] == "payment_provider_conflict"
    assert "pending" in response.data["detail"]
    row.refresh_from_db()
    assert row.provider == provider
    assert row.razorpay_key_secret == ""
    assert not AuditLog.objects.filter(action="payments.settings_updated", makerspace=space).exists()


@pytest.mark.parametrize("state", ["no_handle", "expired", "paid_online", "other_tenant", "same_provider"])
def test_switch_allows_collections_that_cannot_strand_other_rail(merchant, state):
    space, manager, row, client, url = merchant
    options = {}
    if state != "no_handle":
        options["external_order_id"] = "order_safe"
    if state == "expired":
        options["stripe_checkout_session_expired_at"] = timezone.now()
    if state == "paid_online":
        options["status"] = "paid_online"
    if state == "other_tenant":
        space = make_space("other-provider-settings")
        manager = make_member("other-provider-manager", space)
    if state == "same_provider":
        options["provider"] = "razorpay"
    collection(space, manager, **options)
    assert client.patch(url, {"provider": "razorpay"}, format="json").status_code == 200
    row.refresh_from_db()
    assert row.provider == "razorpay"


def test_razorpay_rotation_cannot_strand_pending_collection(merchant):
    space, manager, _, client, url = merchant
    assert client.patch(url, {"provider": "razorpay", **RAZORPAY}, format="json").status_code == 200
    collection(space, manager, provider="razorpay", external_order_id="order_keep")
    assert client.patch(url, RAZORPAY, format="json").status_code == 200
    for field in RAZORPAY:
        response = client.patch(url, {field: ""}, format="json")
        assert response.status_code == 400
        assert "pending" in str(response.data[field])


def test_locked_save_rechecks_collection_created_after_boundary_validation(merchant):
    space, manager, row, _, _ = merchant
    serializer = MakerspacePaymentSettingsSerializer(row, data={"provider": "razorpay"}, partial=True)
    assert serializer.is_valid(), serializer.errors
    collection(space, manager, stripe_payment_intent_id="pi_started_after_validation")
    with pytest.raises(PaymentProviderConflict):
        serializer.save()
    row.refresh_from_db()
    assert row.provider == "stripe"


def test_razorpay_configuration_validation_never_calls_a_provider(merchant, monkeypatch):
    from apps.payments import stripe_client

    def forbidden(*args, **kwargs):
        raise AssertionError("Credential validation must remain local.")

    monkeypatch.setattr(stripe_client, "checkout_session_is_closed", forbidden)
    _, _, _, client, url = merchant
    assert client.patch(url, {"provider": "razorpay", **RAZORPAY}, format="json").status_code == 200


@pytest.mark.parametrize("field,value", [
    ("provider", "paypal"), ("razorpay_key_id", "pk_test_wrong"),
    ("razorpay_key_id", "rzp_live_"), ("razorpay_key_secret", "invalid secret"),
    ("razorpay_webhook_secret", "bad\nsecret"), ("razorpay_key_id", "x" * 256),
    ("razorpay_webhook_secret", "   "),
])
def test_validation_errors_are_field_scoped_and_do_not_echo_secrets(merchant, field, value):
    _, _, row, client, url = merchant
    response = client.patch(url, {field: value}, format="json")
    assert response.status_code == 400
    assert field in response.data
    if field != "provider":
        assert value not in str(response.data)
    row.refresh_from_db()
    assert row.provider == "stripe"
    assert row.razorpay_key_secret == ""


@pytest.mark.parametrize("field,value", [
    ("provider", "razorpay"), *RAZORPAY.items(), ("stripe_secret_key", "sk_new"),
    ("stripe_publishable_key", "pk_new"), ("stripe_webhook_secret", "whsec_new"),
])
def test_recent_reauthentication_required_for_configuration(merchant, field, value):
    _, manager, _, client, url = merchant
    ReauthenticationSession.objects.filter(user=manager).update(auth_time=timezone.now() - timedelta(minutes=11))
    assert client.get(url).status_code == 200
    response = client.patch(url, {field: value}, format="json")
    assert response.status_code == 403
    assert response.data["code"] == "recent_reauth_required"
    assert client.patch(url, {"default_currency": "inr"}, format="json").status_code == 200


@pytest.mark.parametrize("actor", ["member", "inventory_manager", "other_manager"])
def test_settings_remain_scoped_to_space_managers(merchant, actor):
    space, _, row, client, url = merchant
    if actor == "other_manager":
        user = make_member("foreign-manager", make_space("foreign-provider-settings"))
    else:
        role = (MakerspaceMembership.Role.CUSTOM if actor == "member"
                else MakerspaceMembership.Role.INVENTORY_MANAGER)
        user = make_member(f"denied-{actor}", space, membership_role=role,
                           role=User.Role.REQUESTER)
        if actor == "member":
            # Member is a fixed MakerspaceRole, represented by CUSTOM in the legacy enum.
            membership = MakerspaceMembership.objects.get(makerspace=space, user=user)
            membership.assigned_role = MakerspaceRole.objects.get(makerspace=space, slug="member")
            membership.save(update_fields=["assigned_role"])
    force_recent_authenticate(client, user)
    assert client.get(url).status_code in (403, 404)
    assert client.patch(url, {"provider": "razorpay", **RAZORPAY}, format="json").status_code in (403, 404)
    row.refresh_from_db()
    assert row.provider == "stripe"


def test_audit_records_names_only_and_superadmin_never_reads_secrets(merchant):
    space, _, _, client, url = merchant
    changes = {"provider": "razorpay", **RAZORPAY}
    assert client.patch(url, changes, format="json").status_code == 200
    log = AuditLog.objects.get(action="payments.settings_updated", makerspace=space)
    assert log.meta == {"fields": sorted(changes)}
    user = make_user("allowed-superadmin", role=User.Role.SUPERADMIN,
                     access_status=User.AccessStatus.ACTIVE, is_superuser=True, is_staff=True)
    force_recent_authenticate(client, user)
    response = client.get(url)
    assert response.status_code == 200
    for field, secret in RAZORPAY.items():
        assert field not in response.data
        assert secret not in str(log.meta) + str(response.data)


def test_generated_schema_preserves_android_and_ios_attestation_choices():
    schema = SchemaGenerator().get_schema(request=None, public=True)
    components = schema["components"]["schemas"]

    def resolve(node):
        if "$ref" in node:
            return resolve(components[node["$ref"].rsplit("/", 1)[1]])
        if "allOf" in node:
            return resolve(node["allOf"][0])
        return node

    proofs = components["DeviceAttestationPayload"]["anyOf"]
    types = [set(resolve(proof["properties"]["type"])["enum"])
             for proof in proofs if "type" in proof.get("properties", {})]
    assert types == [{"play_integrity"}, {"app_attest"}, {"development"}]
    for name in ("DeviceIdentity", "DeviceLogin", "DeviceGrant"):
        assert set(resolve(components[name]["properties"]["platform"])["enum"]) == {"apple", "android"}
    # Social/native delivery calls iOS `ios`; the device challenge calls it `apple`.
    assert {"ios", "android"} <= set(components["ClientPlatformEnum"]["enum"])
    payment = components["MakerspacePaymentSettings"]
    for field in RAZORPAY:
        assert payment["properties"][field]["writeOnly"] is True
