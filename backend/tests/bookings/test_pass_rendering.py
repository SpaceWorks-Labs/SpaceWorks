from copy import deepcopy
from unittest.mock import Mock

import pytest
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.bookings.models import Booking
from apps.bookings.pass_rendering import render_pass, sample_values
from apps.bookings.pass_templates import DEFAULT_PASS_TEMPLATE
from apps.bookings.services_passes import save_pass_template
from tests.bookings.pass_helpers import pass_world, pdf_content


@pytest.mark.parametrize("name,font", [
    ("Renée Müller", b"NotoSans"), ("अदिति शर्मा", b"NotoSansDevanagari"),
    ("张伟", b"NotoSansSC"), ("مرحبا أحمد", b"NotoSansArabic"),
    ("שלום דנה", b"NotoSansHebrew"),
])
def test_real_pdf_unicode_rtl_and_cjk_fallback(name, font):
    values = {**sample_values(), "name": name}
    pdf = render_pass(DEFAULT_PASS_TEMPLATE, values)
    assert pdf.startswith(b"%PDF-") and font in pdf
    assert b"/Count 1" in pdf


def test_overflow_refuses_instead_of_clipping():
    template = deepcopy(DEFAULT_PASS_TEMPLATE)
    template["elements"][0].update(width_mm=1, height_mm=1)
    with pytest.raises(ValidationError):
        render_pass(template, {**sample_values(), "name": "W" * 500})
    with pytest.raises(ValidationError):
        render_pass(DEFAULT_PASS_TEMPLATE, {**sample_values(), "name": "X" * 501})


def test_pdf_remains_one_sheet_and_drops_extra_projection_keys():
    pdf = render_pass(DEFAULT_PASS_TEMPLATE, {**sample_values(), "email": "PRIVATE-EXTRA-SENTINEL"})
    content = pdf_content(pdf)
    assert b"Sample booker" in content and b"PRIVATE-EXTRA-SENTINEL" not in content
    assert b"/Count 1" in pdf


@pytest.mark.django_db
def test_completed_arrival_prints_and_reversal_stops_it(monkeypatch):
    from apps.bookings.services_arrival import reverse_arrival
    from tests.bookings.staff_grant_helpers import client_for
    w = pass_world(monkeypatch)
    Booking.objects.filter(pk=w.row.pk).update(status="completed")
    assert w.client.post(w.print_url, {}, format="json").status_code == 200
    reverse_arrival(w.row, actor=w.actor)
    assert w.client.post(w.print_url, {}, format="json").status_code == 409
    assert client_for(w.member).get(w.member_url).status_code == 200


@pytest.mark.django_db
def test_pdf_is_rebuilt_and_never_reuses_a_prior_owner_or_sample_render(monkeypatch):
    w = pass_world(monkeypatch, permission="edit_details")
    assert w.owner.get(w.member_url).status_code == 200
    assert w.client.post(w.preview_url, {}, format="json").status_code == 200
    w.row.name = "Changed Booker"
    w.row.save(update_fields=["name"])
    from tests.bookings.staff_grant_helpers import client_for
    staff_pdf = client_for(w.actor).post(w.print_url, {}, format="json")
    content = pdf_content(staff_pdf.content)
    assert b"Changed Booker" in content and b"Sample booker" not in content


@pytest.mark.django_db
def test_failed_render_has_no_success_audit_and_failed_audit_rolls_back_layout(monkeypatch):
    w = pass_world(monkeypatch, permission="edit_details")
    from apps.bookings import services_passes
    fail = Mock(side_effect=ValidationError({"layout": "Overflow"}))
    monkeypatch.setattr(services_passes, "render_pass", fail)
    assert w.owner.get(w.member_url).status_code == 400
    assert not AuditLog.objects.filter(action="booking.pass_downloaded").exists()
    monkeypatch.setattr(services_passes.audit, "record", Mock(side_effect=RuntimeError("audit unavailable")))
    with pytest.raises(RuntimeError):
        save_pass_template(w.resource, DEFAULT_PASS_TEMPLATE, actor=w.grantee)
    w.resource.refresh_from_db()
    assert w.resource.pass_template == {}
    assert not AuditLog.objects.filter(action="booking.pass_template_updated").exists()


@pytest.mark.django_db
def test_scanner_reloads_arrival_after_waiting_for_the_booking_locks(monkeypatch):
    from apps.bookings import services_passes
    from apps.bookings.exceptions import BookingInvalidTransition
    from apps.bookings.services_arrival import reverse_arrival
    w = pass_world(monkeypatch)
    original = services_passes._locked_booking
    def reverse_before_lock(candidate):
        reverse_arrival(candidate, actor=w.actor)
        return original(candidate)
    monkeypatch.setattr(services_passes, "_locked_booking", reverse_before_lock)
    with pytest.raises(BookingInvalidTransition):
        services_passes.booking_pass(w.row, actor=w.grantee, scanner=True)
    assert not AuditLog.objects.filter(action="booking.pass_downloaded").exists()
