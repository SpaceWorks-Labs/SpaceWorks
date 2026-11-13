"""Every new mutation enforces resource authority and strict boundary inputs."""

import pytest
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient

from apps.accounts.rbac import Action
from apps.bookings import services
from apps.bookings.models import BookableSpace
from tests.bookings.staff_grant_helpers import client_for
from tests.bookings.test_staff_tools_helpers import payload, request, snapshot, world
from tests.machines.certification_helpers import _manager, _space

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("operation", ["details", "time", "restore"])
def test_manage_reservations_grant_can_use_staff_tools(monkeypatch, operation):
    w = world(monkeypatch)
    if operation == "restore":
        w.row = services.cancel_booking(w.row, actor=w.actor)
    response = request(w, operation)
    assert response.status_code == 200, response.data
    assert response.data["id"] == w.row.pk


@pytest.mark.parametrize("operation", ["clone", "details", "time", "restore"])
@pytest.mark.parametrize("permission", ["edit_details", "check_in", "publish_page"])
def test_other_resource_permissions_do_not_authorize_mutations(monkeypatch, operation, permission):
    w = world(monkeypatch, permission=permission)
    if operation == "restore":
        w.row = services.cancel_booking(w.row, actor=w.actor)
    before = snapshot(w)
    count = BookableSpace.objects.count()
    assert request(w, operation).status_code in (403, 404)
    assert snapshot(w) == before and BookableSpace.objects.count() == count


@pytest.mark.parametrize("operation", ["clone", "details", "time", "restore"])
def test_foreign_tenant_member_and_unauthenticated_callers_cannot_mutate(monkeypatch, operation):
    w = world(monkeypatch)
    if operation == "restore":
        w.row = services.cancel_booking(w.row, actor=w.actor)
    other = _space("staff-tools-foreign", certifications=False)
    outsider, _ = _manager(other, "foreign-manager", actions=(Action.MANAGE_BOOKINGS,))
    before = snapshot(w)
    assert request(w, operation, client_for(outsider)).status_code == 404
    assert request(w, operation, client_for(w.member)).status_code in (403, 404)
    assert request(w, operation, APIClient()).status_code in (401, 403)
    assert snapshot(w) == before


@pytest.mark.parametrize("operation", ["clone", "details", "time", "restore"])
def test_services_recheck_authority_without_http_resolver(monkeypatch, operation):
    w = world(monkeypatch, permission="check_in")
    if operation == "restore":
        w.row = services.cancel_booking(w.row, actor=w.actor)
    before = snapshot(w)
    with pytest.raises(PermissionDenied):
        if operation == "clone":
            services.clone_space(w.resource, actor=w.grantee)
        elif operation == "details":
            services.edit_booking_details(w.row, actor=w.grantee, note="No")
        elif operation == "time":
            from tests.bookings.test_staff_tools_helpers import NOW
            from datetime import timedelta
            services.edit_booking_time(w.row, actor=w.grantee, starts_at=NOW + timedelta(days=3), ends_at=NOW + timedelta(days=3, hours=1))
        else:
            services.restore_booking(w.row, actor=w.grantee)
    assert snapshot(w) == before


@pytest.mark.parametrize("operation", ["clone", "details", "time", "restore"])
def test_tenant_manager_and_feature_gates(monkeypatch, operation):
    w = world(monkeypatch)
    if operation == "restore":
        w.row = services.cancel_booking(w.row, actor=w.actor)
    key = "bookings.clone" if operation == "clone" else "bookings.staff_tools"
    w.tenant.enabled_features.remove(key)
    w.tenant.save(update_fields=["enabled_features"])
    before = snapshot(w)
    assert request(w, operation, client_for(w.actor)).status_code == 404
    assert snapshot(w) == before
    w.tenant.enabled_features.append(key)
    w.tenant.save(update_fields=["enabled_features"])
    assert request(w, operation, client_for(w.actor)).status_code == (201 if operation == "clone" else 200)


@pytest.mark.parametrize("operation", ["details", "time", "clone", "restore"])
@pytest.mark.parametrize("field,value", [("status", "confirmed"), ("member_id", 123), ("space", 123), ("override", True), ("payment_amount", "0")])
def test_http_unknown_fields_are_refused_without_side_effects(monkeypatch, operation, field, value):
    w = world(monkeypatch)
    if operation == "restore":
        w.row = services.cancel_booking(w.row, actor=w.actor)
    before = snapshot(w)
    response = request(w, operation, client_for(w.actor), **{field: value})
    assert response.status_code == 400
    assert snapshot(w) == before


@pytest.mark.parametrize("changes", [{}, {"note": None}, {"note": "x" * 5001}, {"custom_answers": {}}, {"custom_answers": {"unknown": "x"}}, {"status": "confirmed"}])
def test_detail_service_validates_note_and_current_answer_schema(monkeypatch, changes):
    w = world(monkeypatch)
    before = snapshot(w)
    with pytest.raises(ValidationError):
        services.edit_booking_details(w.row, actor=w.actor, **changes)
    assert snapshot(w) == before


def test_valid_note_answer_edit_preserves_identity_calendar_and_money(monkeypatch):
    w = world(monkeypatch, charged=True)
    before, payments, audits = snapshot(w)
    result = services.edit_booking_details(w.row, actor=w.grantee,
                                           note="  Updated private note  ", custom_answers={"purpose": "Updated answer"})
    assert result.note == "Updated private note" and result.custom_answers["answers"][0]["value"] == "Updated answer"
    after, current_payments, current_audits = snapshot(w)
    assert {key: value for key, value in after.items() if key not in {"note", "custom_answers"}} == {
        key: value for key, value in before.items() if key not in {"note", "custom_answers"}
    }
    assert current_payments == payments and len(current_audits) == len(audits) + 1
    assert current_audits[-1]["action"] == "booking.details_edited"
    assert "Updated private note" not in str(current_audits[-1]["meta"])


def test_note_only_patch_preserves_historical_answers_after_form_replacement(monkeypatch):
    w = world(monkeypatch, charged=True)
    w.resource.custom_form = [{"id": "new", "label": "New required question", "type": "short_text",
                               "options": [], "required": True}]
    w.resource.save(update_fields=["custom_form"])
    before, payments, audits = snapshot(w)
    response = request(w, "details", note="Updated private note")
    assert response.status_code == 200, response.data
    assert response.data["custom_answers"] == before["custom_answers"]
    after, current_payments, current_audits = snapshot(w)
    w.row.refresh_from_db()
    assert w.row.note == "Updated private note"
    assert {key: value for key, value in after.items() if key != "note"} == {
        key: value for key, value in before.items() if key != "note"
    }
    assert current_payments == payments and len(current_audits) == len(audits) + 1
    assert current_audits[-1]["action"] == "booking.details_edited"
    assert current_audits[-1]["meta"]["changed_fields"] == ["note"]
