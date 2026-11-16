import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.integrations.notification_wa_twilio_config import callback_path
from tests.return_helpers import make_member, make_space

pytestmark = pytest.mark.django_db


def client(user):
    api = APIClient()
    api.force_authenticate(user)
    return api


def test_space_manager_refresh_confirms_provider_approval(wa):
    binding = wa.template(approved=False)
    path = reverse("whatsapp-twilio-template-refresh", kwargs={"makerspace_id": wa.space.pk})
    response = client(wa.user).post(path)
    assert response.status_code == 200 and response.data == {"checked": 1, "approved": 1, "unavailable": 0}
    binding.refresh_from_db()
    assert binding.approved
    assert wa.http.calls[-2][0].full_url.endswith("/ApprovalRequests")
    assert wa.http.calls[-1][0].full_url.endswith("/" + binding.template_name)


@pytest.mark.parametrize("failure", ["pending", "wrong_account", "unavailable"])
def test_unproven_template_never_becomes_approved(wa, failure):
    binding = wa.template(approved=True)
    if failure == "pending":
        wa.http.state["approval"] = "pending"
    elif failure == "wrong_account":
        wa.http.state["account"] = "AC" + "f" * 32
    else:
        wa.http.state["error"] = TimeoutError()
    response = client(wa.user).post(reverse("whatsapp-twilio-template-refresh", kwargs={"makerspace_id": wa.space.pk}))
    assert response.status_code == 200 and response.data["approved"] == 0
    binding.refresh_from_db()
    assert not binding.approved


@pytest.mark.parametrize("role", ["inventory_manager", "machine_manager", "event_manager", "booking_manager", "handover", "member"])
def test_other_roles_cannot_refresh_credentials_or_templates(wa, role):
    user = make_member("wa-role-" + role, wa.space, membership_role="custom" if role == "member" else role)
    from apps.makerspaces.models import MakerspaceMembership
    rows = MakerspaceMembership.objects if role == "member" else MakerspaceMembership.staff_tracks  # staff roles live on the staff track
    membership = rows.get(user=user, makerspace=wa.space)
    membership.assigned_role = wa.space.roles.get(slug=role)
    membership.save(update_fields=["assigned_role"])
    path = reverse("whatsapp-twilio-template-refresh", kwargs={"makerspace_id": wa.space.pk})
    assert client(user).post(path).status_code == 403 and not wa.http.calls


def test_cross_tenant_manager_cannot_refresh(wa):
    other = make_space("wa-foreign-manager")
    user = make_member("wa-foreign", other)
    path = reverse("whatsapp-twilio-template-refresh", kwargs={"makerspace_id": wa.space.pk})
    assert client(user).post(path).status_code == 404  # 481(1): another space answers like a missing one


def test_refresh_batches_are_bounded_and_unknown_fields_refused(wa):
    from apps.integrations.models_endpoints import WhatsAppTemplate
    for number in range(6):
        WhatsAppTemplate.objects.create(configuration=wa.config, event=f"event-{number}", audience="member",
            template_name="HX" + f"{number:032x}", variables=[])
    path = reverse("whatsapp-twilio-template-refresh", kwargs={"makerspace_id": wa.space.pk})
    assert client(wa.user).post(path).status_code == 400
    assert not wa.http.calls
    assert client(wa.user).post(path, {"unknown": True}, format="json").status_code == 400


def test_rotation_during_provider_approval_cannot_approve_next_installation(wa, monkeypatch):
    from apps.integrations.models_endpoints import ChannelConfiguration
    from apps.integrations.notification_wa_twilio_http import call
    binding = wa.template(approved=False)
    def rotate(*args, **kwargs):
        result = call(*args, **kwargs)
        ChannelConfiguration.objects.filter(pk=wa.config.pk).update(generation=wa.config.generation + 1)
        return result
    monkeypatch.setattr("apps.integrations.notification_wa_twilio_templates.call", rotate)
    path = reverse("whatsapp-twilio-template-refresh", kwargs={"makerspace_id": wa.space.pk})
    assert client(wa.user).post(path).status_code == 400
    binding.refresh_from_db()
    assert not binding.approved


def test_frozen_tenant_still_commits_stop_protection_and_holds_optional_writes(wa):
    from tests.tenant_migration.source_gate_helpers import close_gate
    from apps.integrations.models_cutover import NotificationIngress
    from apps.integrations.models_messaging_consent import MessagingSuppression
    close_gate(wa.space, wa.user)
    assert wa.post(params={"Body": "STOP"}).status_code == 200
    assert MessagingSuppression.objects.filter(channel="whatsapp", lifted_at__isnull=True).exists()
    assert NotificationIngress.objects.filter(protection_applied=True).exclude(state="processed").exists()
    wa.endpoint.refresh_from_db()
    assert wa.endpoint.revoked_at is None


def test_routes_have_tenant_targets_and_are_outside_client_and_claim_prefixes(wa, settings):
    from django.urls import resolve
    from django.test import RequestFactory
    from apps.accounts.claim_routes import CLAIM_REACHABLE_PREFIXES, policy_for
    from apps.accounts.claim_route_types import Refused
    from apps.apiclients.read_prefixes import mandatory_hmac_prefixes
    from apps.apiclients.scope_registry import lookup
    from apps.makerspaces.origin_scope_routes import authoritative_route_resolution
    from apps.tenant_migration.gate_policy import HTTP_ANONYMOUS_PARTICIPANTS
    paths = [callback_path(wa.config, "inbound"), callback_path(wa.config, "status", wa.delivery.pk),
        reverse("whatsapp-twilio-template-refresh", kwargs={"makerspace_id": wa.space.pk})]
    for path in paths:
        request = RequestFactory().post(path)
        request.resolver_match = resolve(path)
        assert authoritative_route_resolution(request) == ({wa.space.pk}, True)
        assert not path.startswith(tuple(settings.HMAC_PROTECTED_PATH_PREFIXES) + tuple(mandatory_hmac_prefixes()))
        assert not path.startswith(CLAIM_REACHABLE_PREFIXES)
        assert isinstance(policy_for(request.resolver_match.view_name, "POST"), Refused)
        assert lookup(request.resolver_match.view_name, "POST") is None
    assert "apps.integrations.notification_wa_twilio_views.TwilioWhatsAppWebhookView.post" in HTTP_ANONYMOUS_PARTICIPANTS
