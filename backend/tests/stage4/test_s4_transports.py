"""Real JWTs reach staff transports without losing tenant/owner/capability checks."""
import pytest
from django.urls import resolve, reverse
from rest_framework.request import Request
from rest_framework.test import APIClient, APIRequestFactory

from apps.accounts.models import User
from apps.boxes.models import QrCode
from apps.makerspaces.origin_scope_routes import request_route_targets
from apps.payments.documents import issue_bill
from tests.account_split.p1_helpers import staff
from tests.billing_docs.test_r1_bills import pending
from tests.hardware_requests.test_kiosk_online import (
    HEADERS, kiosk_settings, kiosk_space, make_staff,
)
from tests.return_helpers import make_accepted_request, make_product
from .helpers import bearer_client

pytestmark = pytest.mark.django_db


def resolved_targets(path):
    raw = APIRequestFactory().get(path)
    raw.resolver_match = resolve(path)
    return request_route_targets(Request(raw))


def test_staff_and_member_downloads_recheck_grant_owner_and_tenant(monkeypatch):
    space, _, payment = pending("s4-download")
    bill = issue_bill(payment)
    manager, _ = staff(space, "s4-finance", role="space_manager")
    intruder, _ = staff(space, "s4-other-finance", role="space_manager")
    outsider = User.objects.create_user("s4-other-payer")
    monkeypatch.setattr("apps.payments.document_pdf.render_document_pdf", lambda row: b"%PDF-s4")
    path = reverse("payment-document-download", args=[bill.pk])
    assert resolved_targets(path) == ("payment-document-download", {space.pk}, False, True)
    for actor, grant_name in [(manager, "staff-payment-document-url"), (payment.member, "member-payment-document-url")]:
        api = bearer_client(actor)
        grant = api.get(reverse(grant_name, args=[space.pk, bill.pk]))
        assert grant.status_code == 200, grant.data
        response = api.get(grant.data["url"])
        assert response.status_code == 200, getattr(response, "data", None)
        assert response.content == b"%PDF-s4" and "no-store" in response["Cache-Control"]
        assert bearer_client(intruder).get(grant.data["url"]).status_code == 403
        assert bearer_client(outsider).get(grant.data["url"]).status_code == 403
    assert bearer_client(manager).get(path, {"token": "invalid"}).status_code == 400
    from tests.return_helpers import make_space
    foreign, _ = staff(make_space("s4-foreign-finance"), "s4-foreign-finance", role="space_manager")
    # The surface guard no longer pre-refuses this mixed-audience route (surface_policy.enforce_request,
    # decisions 63/66): the view owns the check. Without a signed grant it refuses everyone alike, and a
    # foreign space's staff cannot mint a grant for this space's document.
    assert bearer_client(foreign).get(path).status_code == 400
    assert bearer_client(foreign).get(reverse("staff-payment-document-url", args=[space.pk, bill.pk])).status_code in {403, 404}
    assert bearer_client(User.objects.create_superuser("s4-root")).get(path).status_code == 400


def test_kiosk_lease_package_evidence_and_command_use_station_tenant(monkeypatch):
    space = kiosk_space("s4-station")
    operator = make_staff(space)
    api = bearer_client(operator)
    station = api.post(reverse("admin-kiosk-station-list-create", args=[space.pk]),
        {"name": "S4 desk", "kind": "handover"}, format="json")
    assert station.status_code == 201, station.data
    token = station.data["public_token"]
    api = APIClient()
    opened = api.post(reverse("kiosk-station-session", args=[token]),
        {"pin": station.data["pin"]}, format="json", **HEADERS)
    assert opened.status_code == 201, opened.data
    api.credentials(**bearer_client(operator)._credentials)
    leased = api.post(reverse("kiosk-station-operator-lease", args=[token]), **HEADERS)
    assert leased.status_code == 201, leased.data
    headers = {**HEADERS, "HTTP_X_KIOSK_OPERATOR_LEASE": leased.data["lease_token"]}
    product = make_product(space)
    request = make_accepted_request(space, product, 1)
    package = api.post(reverse("kiosk-station-work-package", args=[token]),
        {"kind": "reviewed_request", "id": request.pk}, format="json", **headers)
    assert package.status_code == 200, package.data
    monkeypatch.setattr("apps.evidence.services_upload.presigned_upload", lambda key, content_type:
        {"url": "https://storage.test/upload", "fields": {"key": f"staging/{key}"}})
    photo = api.post(reverse("kiosk-station-evidence-prepare", args=[token]),
        {"evidence_type": "issue", "content_type": "image/jpeg"}, format="json", **headers)
    assert photo.status_code == 201, photo.data
    qr = QrCode.objects.create(makerspace=space, target_type=QrCode.TargetType.PRODUCT, target_id=product.pk)
    command = api.post(reverse("kiosk-station-command-online", args=[token]),
        {"version": 1, "kind": "resolve_qr", "payload": {"payload": qr.payload}}, format="json", **headers)
    assert command.status_code == 200, command.data
    foreign = make_staff(kiosk_space("s4-station-other"))
    api.credentials(**bearer_client(foreign)._credentials)
    for name in ("kiosk-station-operator-lease", "kiosk-station-work-package",
                 "kiosk-station-evidence-prepare", "kiosk-station-command-online"):
        path = reverse(name, args=[token])
        assert resolved_targets(path) == (name, {space.pk}, False, True)
        assert api.post(path, {}, format="json", **headers).status_code == 403
    api.credentials(**bearer_client(operator)._credentials)
    assert api.post(reverse("kiosk-station-command-online", args=[token]),
        {"version": 1, "kind": "resolve_qr", "payload": {"payload": qr.payload}}, format="json", **HEADERS).status_code == 403


def test_provider_media_has_no_account_authentication_or_account_authority():
    from apps.integrations.notification_media_views import NotificationMediaView
    assert NotificationMediaView.authentication_classes == []
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION="Bearer invalid-account-token")
    response = api.get(reverse("notification-media", args=["unknown-capability"]))
    assert response.status_code == 404
