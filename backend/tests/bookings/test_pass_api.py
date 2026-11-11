from copy import deepcopy
from unittest.mock import Mock

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.bookings import pass_rendering
from apps.bookings.models import Booking, BookableSpace
from apps.bookings.pass_templates import DEFAULT_PASS_TEMPLATE, PASS_FIELDS
from apps.bookings.services_arrival import reverse_arrival
from apps.bookings.views_passes import BookingPassRenderThrottle
from tests.bookings.pass_helpers import pass_world, pdf_content, pdf_text
from tests.bookings.staff_grant_helpers import client_for, grant_fixture

pytestmark = pytest.mark.django_db


def test_checkin_only_pass_inspects_renderer_inputs_and_actual_pdf(monkeypatch):
    w = pass_world(monkeypatch)
    w.row.name = "Allowed Booker"
    w.row.email, w.row.phone, w.row.note = "private-contact@example.test", "987654321234", "PRIVATE-NOTE-SENTINEL"
    w.row.custom_answers = {"answers": [{"id": "purpose", "value": "PRIVATE-ANSWER-SENTINEL"}]}
    w.row.save(update_fields=["name", "email", "phone", "note", "custom_answers"])
    spy = Mock(wraps=pass_rendering.render_sheet)
    monkeypatch.setattr(pass_rendering, "render_sheet", spy)
    response = w.client.post(w.print_url, {}, format="json")
    assert response.status_code == 200
    assert set(spy.call_args.args[1][0]) == set(PASS_FIELDS)
    assert spy.call_args.args[1][0]["name"] == "Allowed Booker"
    content = pdf_content(response.content)
    text = pdf_text(response.content)
    assert "Allowed Booker" in text and f"Booking #{w.row.pk}" in text
    for secret in (w.row.email, w.row.phone, w.row.note, "PRIVATE-ANSWER-SENTINEL",
                   str(w.row.checkin_token), str(w.row.public_token)):
        assert secret not in repr(spy.call_args)
        assert secret.encode() not in content
        assert secret not in text
    assert response["Cache-Control"] == "private, no-store"
    assert response["Referrer-Policy"] == "no-referrer"
    assert AuditLog.objects.filter(action="booking.pass_downloaded", target_id=str(w.row.pk)).exists()
    assert w.client.get(f"/api/v1/admin/spaces/{w.resource.pk}/bookings/").status_code == 403
    assert w.client.get(w.template_url).status_code == 403


@pytest.mark.parametrize("permission", ["edit_details", "manage_reservations", "publish_page"])
def test_other_resource_permissions_never_confer_scanner_print(monkeypatch, permission):
    w = pass_world(monkeypatch, permission=permission)
    assert w.client.post(w.print_url, {}, format="json").status_code == 403


def test_owner_only_download_and_booking_only_installation(monkeypatch):
    w = pass_world(monkeypatch, arrived=False)
    w.tenant.enabled_modules = [key for key in w.tenant.enabled_modules if key not in {"events", "membership", "payments", "presence"}]
    w.tenant.save(update_fields=["enabled_modules"])
    # An account with no membership continues to own its original reservation.
    w.member.makerspace_memberships.all().delete()
    assert w.owner.get(w.member_url).status_code == 200
    assert w.client.get(w.member_url).status_code == 404
    # A tenant-bound staff account is refused by the member-identity guard before any
    # booking lookup (separate account kinds), so it learns nothing about the token.
    assert client_for(w.actor).get(w.member_url).status_code == 404  # one account per person: a non-owner just does not find the booking


@pytest.mark.parametrize("status", ["pending", "rejected", "cancelled", "no_show"])
def test_nonadmitted_status_refuses_both_print_paths(monkeypatch, status):
    w = pass_world(monkeypatch)
    Booking.objects.filter(pk=w.row.pk).update(status=status)
    assert w.owner.get(w.member_url).status_code == 409
    assert w.client.post(w.print_url, {}, format="json").status_code == 409


def test_active_arrival_is_required_and_revocation_has_immediate_effect(monkeypatch):
    w = pass_world(monkeypatch)
    assert w.client.post(w.print_url, {}, format="json").status_code == 200
    reverse_arrival(w.row, actor=w.actor)
    assert w.client.post(w.print_url, {}, format="json").status_code == 409
    # Owner rendering has its own authorization and does not require arrival.
    assert w.owner.get(w.member_url).status_code == 200
    w.grant.revoked_at = timezone.now()
    w.grant.save(update_fields=["revoked_at"])
    assert w.client.post(w.print_url, {}, format="json").status_code in (403, 404)


def test_cross_resource_cross_tenant_and_wrong_origin_refuse(monkeypatch):
    w = pass_world(monkeypatch)
    other, _, _, resource, _, _ = grant_fixture(slug="pass-other")
    url = f"/api/v1/admin/spaces/{resource.pk}/arrival/{w.row.pk}/pass/"
    assert w.client.post(url, {}, format="json").status_code in (403, 404)
    second = BookableSpace.objects.create(makerspace=w.tenant, name="Second resource")
    url = f"/api/v1/admin/spaces/{second.pk}/arrival/{w.row.pk}/pass/"
    assert client_for(w.actor).post(url, {}, format="json").status_code == 404
    other.frontend_domain, other.frontend_domain_status = "foreign-pass.example.test", "verified"
    other.save(update_fields=["frontend_domain", "frontend_domain_status"])
    assert w.client.post(w.print_url, {}, format="json", HTTP_ORIGIN="https://foreign-pass.example.test").status_code == 403


@pytest.mark.parametrize("key", ["bookings", "bookings.confirmations", "bookings.passes"])
def test_module_and_feature_shutdown_refuse_without_pdf_cache(monkeypatch, key):
    w = pass_world(monkeypatch)
    assert w.owner.get(w.member_url).status_code == 200
    attr = "enabled_modules" if key == "bookings" else "enabled_features"
    setattr(w.tenant, attr, [item for item in getattr(w.tenant, attr) if item != key])
    w.tenant.save(update_fields=[attr])
    assert w.owner.get(w.member_url).status_code in (400, 404)
    assert w.client.post(w.print_url, {}, format="json").status_code in (400, 403, 404)


def test_editor_preview_is_sample_only_and_hostile_stored_templates_refuse_every_path(monkeypatch):
    w = pass_world(monkeypatch, permission="edit_details")
    template = deepcopy(DEFAULT_PASS_TEMPLATE)
    assert w.client.put(w.template_url, template, format="json").status_code == 200
    response = w.client.post(w.preview_url, template, format="json")
    assert response.status_code == 200 and b"Sample booker" in pdf_content(response.content)
    assert AuditLog.objects.filter(action="booking.pass_template_updated").count() == 1
    assert AuditLog.objects.filter(action="booking.pass_previewed").count() == 1
    template["elements"][0]["field"] = "custom:purpose"
    for url, method in ((w.template_url, w.client.put), (w.preview_url, w.client.post)):
        assert method(url, template, format="json").status_code == 400
    # Simulate a legacy/imported template bypassing today's editor validation.
    BookableSpace.objects.filter(pk=w.resource.pk).update(pass_template=template)
    assert w.client.get(w.template_url).status_code == 400
    assert w.owner.get(w.member_url).status_code == 400
    assert client_for(w.actor).post(w.print_url, {}, format="json").status_code == 400
    assert AuditLog.objects.filter(action="booking.pass_downloaded").count() == 0


def test_staff_override_and_real_recipient_preview_refuse(monkeypatch):
    w = pass_world(monkeypatch, permission="edit_details")
    assert w.client.post(w.preview_url, {"booking_id": w.row.pk}, format="json").status_code == 400
    assert client_for(w.actor).post(w.print_url, {"template_override": {}}, format="json").status_code == 400


def test_render_throttle_and_pre_dispatch_private_errors(monkeypatch):
    w = pass_world(monkeypatch)
    monkeypatch.setattr(BookingPassRenderThrottle, "allow_request", lambda *args: False)
    monkeypatch.setattr(BookingPassRenderThrottle, "wait", lambda *args: 60)
    response = w.owner.get(w.member_url)
    assert response.status_code == 429 and "no-store" in response["Cache-Control"]
    assert response["Referrer-Policy"] == "no-referrer"
    assert not AuditLog.objects.filter(action="booking.pass_downloaded").exists()


def test_checkin_gate_is_separate_from_owner_passes(monkeypatch):
    w = pass_world(monkeypatch)
    w.tenant.enabled_features.remove("bookings.checkin")
    w.tenant.save(update_fields=["enabled_features"])
    assert w.owner.get(w.member_url).status_code == 200
    assert w.client.post(w.print_url, {}, format="json").status_code == 404


@pytest.mark.parametrize("state", ["inactive", "restricted", "revoked", "archived"])
def test_live_account_and_tenant_restrictions_refuse(monkeypatch, state):
    w = pass_world(monkeypatch)
    if state == "inactive":
        w.grantee.is_active = False
        w.grantee.save(update_fields=["is_active"])
    elif state == "restricted":
        w.grantee.access_status = "restricted"
        w.grantee.save(update_fields=["access_status"])
    elif state == "revoked":
        membership = w.member.makerspace_memberships.get(makerspace=w.tenant)
        membership.status = "revoked"
        membership.save(update_fields=["status"])
        assert w.owner.get(w.member_url).status_code == 404
        return
    else:
        w.tenant.archived_at = timezone.now()
        w.tenant.save(update_fields=["archived_at"])
    assert w.client.post(w.print_url, {}, format="json").status_code in (403, 404)
