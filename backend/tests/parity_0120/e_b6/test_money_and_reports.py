"""E-B6 C19/C20/C24: Money and Spending in the event PDF, the orders CSV, the series card and the test-mode flag."""
from types import SimpleNamespace

import pytest

from apps.events.models import EventOrder
from apps.operations import reports
from apps.operations.report_pdf import render_pdf
from apps.operations.reports_event_orders import ORDER_FIELDS, build_event_orders
from apps.operations.reports_events_money import MONEY_FIELDS, build_event_report_pdf, money_visible, series_money
from apps.payments.models import Payment
from apps.payments.test_mode import payment_is_test, source_test_mode
from tests.events.orders_helpers import order_payment, place, settle_offline, ticketed_event, verified

pytestmark = pytest.mark.django_db


def paid_event(capture):
    space, event, staff, ticket = ticketed_event(amount=12)
    # The orders report is an event export: its own switch (off by default) has to be on.
    space.enabled_modules = sorted(set(space.enabled_modules or []) | {"reports"})
    space.enabled_features = sorted(set(space.enabled_features or []) | {"reports.event_exports"})
    space.save(update_fields=["enabled_modules", "enabled_features"])
    buyer = verified("buyer")
    assert place(buyer, event, [{"ticket_type_id": ticket.pk, "quantity": 2}]).status_code == 201
    order = EventOrder.objects.get()
    with capture(execute=True):
        settle_offline(order_payment(order), staff)
    return space, event, staff, order


def turn_charges(space, on):
    features = set(space.enabled_features) - {"charges.enabled", "charges.events"}
    space.enabled_features = sorted(features | ({"charges.enabled", "charges.events"} if on else set()))
    space.save(update_fields=["enabled_features"])


def test_pdf_sections_are_hidden_when_payments_and_charges_are_off(django_capture_on_commit_callbacks):
    space, event, staff, order = paid_event(django_capture_on_commit_callbacks)
    turn_charges(space, False)
    assert not money_visible(space, staff)
    result = build_event_report_pdf(space.pk, subject_kind="event", subject_id=event.pk, actor=staff)
    assert not set(MONEY_FIELDS) & set(result.field_order)


def test_pdf_sections_show_income_per_currency_for_a_finance_viewer(django_capture_on_commit_callbacks):
    space, event, staff, order = paid_event(django_capture_on_commit_callbacks)
    turn_charges(space, True)
    result = build_event_report_pdf(space.pk, subject_kind="event", subject_id=event.pk, actor=staff)
    assert set(MONEY_FIELDS) <= set(result.field_order)
    assert "24" in result.records[0]["money_income"]


def test_the_pdf_prints_money_and_spending_as_their_own_sections():
    rows = [("title", "money_income", "money_net", "spending_expenses"), ("Open day", "24.00 USD", "24.00 USD", "")]
    pdf = render_pdf(rows, provenance={}, title="Post-event analytics")
    assert pdf.startswith(b"%PDF")


def test_orders_csv_has_one_row_per_order_with_live_money(django_capture_on_commit_callbacks):
    space, event, staff, order = paid_event(django_capture_on_commit_callbacks)
    result = build_event_orders(space.pk, subject_kind="event", subject_id=event.pk)
    assert result.field_order == ORDER_FIELDS and len(result.records) == 1
    row = result.records[0]
    assert (row["order_id"], row["status"], row["tickets"], row["paid"]) == (order.pk, "paid", 2, "24.00")
    assert row["buyer_email"] and row["payment_method"] == "In person" and row["test_paid"] == ""


def test_a_test_mode_payment_never_joins_live_money(django_capture_on_commit_callbacks):
    # A settled payment is immutable (DB trigger), so the order is paid by a test-mode Stripe session from the
    # start: the pending row is moved to paid_online with the test session id in one update.
    space, event, staff, ticket = ticketed_event(amount=12)
    buyer = verified("buyer")
    assert place(buyer, event, [{"ticket_type_id": ticket.pk, "quantity": 2}]).status_code == 201
    order = EventOrder.objects.get()
    Payment.objects.filter(pk=order_payment(order).pk).update(
        status="paid_online", provider="stripe", stripe_checkout_session_id="cs_test_abc")
    row = build_event_orders(space.pk, subject_kind="event", subject_id=event.pk).records[0]
    assert row["paid"] == "" and row["test_paid"] == "24.00"


def test_orders_report_needs_the_registration_grant(django_capture_on_commit_callbacks):
    from rest_framework.exceptions import PermissionDenied
    space, event, staff, order = paid_event(django_capture_on_commit_callbacks)
    filters = {"subject_kind": "event", "subject_id": event.pk}
    assert reports.report_rows("event-orders", space.pk, actor=staff, report_filters=filters)
    with pytest.raises(PermissionDenied):
        reports.report_rows("event-orders", space.pk, actor=verified("outsider"), report_filters=filters)


def test_series_money_card_is_null_when_hidden(django_capture_on_commit_callbacks):
    from apps.events.models import EventSeries
    space, event, staff, order = paid_event(django_capture_on_commit_callbacks)
    from django.utils import timezone
    series = EventSeries.objects.create(
        makerspace=space, title="Weekly workshops", recurrence_timezone="UTC",
        dtstart_local_date=timezone.now().date(), dtstart_local_time=timezone.now().time().replace(microsecond=0),
        recurrence_rule="FREQ=WEEKLY;COUNT=2", duration_minutes=120)
    event.series, event.series_revision, event.series_occurrence_key = series, 1, "first"
    event.save(update_fields=["series", "series_revision", "series_occurrence_key"])
    assert series_money(space, series, staff) is not None  # visible while charges are on
    turn_charges(space, False)
    assert series_money(space, series, staff) is None


def test_test_mode_is_derived_from_the_public_key_prefix_and_never_leaks_the_key():
    assert source_test_mode(SimpleNamespace(publishable_key="pk_test_123")) is True
    assert source_test_mode(SimpleNamespace(publishable_key="rzp_live_abc")) is False
    assert source_test_mode(SimpleNamespace(publishable_key="")) is None
    assert source_test_mode(None) is None
    assert payment_is_test(SimpleNamespace(provider="stripe", stripe_checkout_session_id="cs_test_x")) is True
    assert payment_is_test(SimpleNamespace(provider="razorpay", stripe_checkout_session_id=None)) is False


def test_the_settings_payload_carries_test_mode_not_the_key(monkeypatch):
    from apps.admin_api.serializers_payments import MakerspacePaymentSettingsSerializer
    from apps.payments.models import MakerspacePaymentSettings
    from tests.return_helpers import make_space
    space = make_space("c20-test-mode")
    row = MakerspacePaymentSettings.for_makerspace(space)
    monkeypatch.setattr("apps.payments.test_mode.space_test_mode", lambda _space: True)
    data = MakerspacePaymentSettingsSerializer(row).data
    assert data["test_mode"] is True
    assert "pk_test" not in str(data) and "sk_test" not in str(data)
