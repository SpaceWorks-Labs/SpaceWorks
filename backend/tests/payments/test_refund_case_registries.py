"""Portability, drift, purge, notifications, Connect fee and the refunds report."""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.data_export.classification import EXPORTED_MODEL_FIELDS
from apps.data_export.datasets import DATASET_SPECS
from apps.data_export.references import RELATIONAL_USER_FIELDS
from apps.operations.reports_refunds import build_refunds
from apps.payments.models import Payment, RefundCase, RefundPolicy
from apps.payments.providers import RefundRequest
from apps.payments.services_refund_cases import open_due_case, request_refund
from apps.payments.services_refund_decisions import approve_case, decline_case
from apps.payments.services_refunds_offline import record_offline_refund
from apps.tenant_migration.money_digest import MoneyDriftRefused, assert_money_unchanged, money_fingerprint
from apps.tenant_migration.tenant_dump_field_snapshot import FIRST_PARTY_FIELD_NAMES
from apps.tenant_migration.tenant_dump_model_catalog import FIRST_PARTY_MODEL_RULES
from tests.payments.refund_case_helpers import charge, member, paid_event, receipt, registration, space_with_currency
from tests.return_helpers import make_member

pytestmark = pytest.mark.django_db


def paid(space, slug, **extra):
    user = member(f"{slug}-m", space)
    return user, charge(space, user, subject_id=registration(paid_event(space), user).pk, **extra)


@pytest.mark.parametrize("label", ["payments.RefundCase", "payments.RefundPolicy"])
def test_models_are_classified_exported_and_catalogued(label):
    from django.apps import apps
    model = apps.get_model(label)
    fields = {field.name for field in model._meta.local_concrete_fields}
    assert fields == set(EXPORTED_MODEL_FIELDS[label].split()) == FIRST_PARTY_FIELD_NAMES[label]
    assert label in DATASET_SPECS and label in FIRST_PARTY_MODEL_RULES
    users = {name for model_label, name in RELATIONAL_USER_FIELDS if model_label == label}
    assert users == ({"requested_by", "decided_by"} if label.endswith("Case") else {"updated_by"})


def test_opening_and_deciding_a_case_is_money_drift():
    space = space_with_currency("reg-drift")
    staff = make_member("reg-drift-staff", space)
    user, payment = paid(space, "reg-drift")
    capture = SimpleNamespace(source_makerspace_id=space.pk, money_fingerprint_sha256=money_fingerprint(space.pk))
    case = request_refund(payment, member=user, reason="please")
    with pytest.raises(MoneyDriftRefused):
        assert_money_unchanged(capture)
    capture.money_fingerprint_sha256 = money_fingerprint(space.pk)
    decline_case(case, actor=staff, note="No")
    with pytest.raises(MoneyDriftRefused):
        assert_money_unchanged(capture)


@pytest.mark.django_db(transaction=True)
def test_purge_deletes_cases_before_refunds_and_payments(monkeypatch):
    from apps.accounts.models import User
    from apps.makerspaces import lifecycle
    space = space_with_currency("reg-purge")
    staff = make_member("reg-purge-staff", space)
    _, payment = paid(space, "reg-purge")
    case = open_due_case(payment, reason_code="event_cancelled", actor=None)
    approve_case(case, actor=staff, amount=Decimal("5.00"), receipt=receipt())
    request_refund(payment, member=payment.member, reason="rest please")
    assert RefundCase.objects.count() == 2 and RefundCase.objects.filter(refund__isnull=False).exists()
    actor = User.objects.create_superuser(username="reg-purge-super", email="reg-purge-super@example.com",
                                          access_status=User.AccessStatus.ACTIVE)
    monkeypatch.setattr(lifecycle, "_delete_storage_keys", lambda _keys: None)
    space_id = space.pk
    lifecycle.purge(lifecycle.archive(space, actor), actor)
    assert not RefundCase.objects.exists() and not Payment.objects.filter(makerspace_id=space_id).exists()


def test_connect_refund_returns_the_application_fee_but_reverses_no_transfer(monkeypatch):
    from apps.payments import services_refunds
    space = space_with_currency("reg-connect")
    staff = make_member("reg-connect-staff", space)
    _, payment = paid(space, "reg-connect", status="paid_online", provider="stripe", stripe_provider="connect",
                      stripe_application_fee_amount=150, stripe_payment_intent_id="pi_connect")
    seen = []

    class Provider:
        def create_refund(self, source, request):
            seen.append(request)
            return SimpleNamespace(refund_id="re_c", status="succeeded")

    monkeypatch.setattr(services_refunds, "source_for_payment", lambda payment: object())
    monkeypatch.setattr(services_refunds, "get_provider", lambda name: Provider())
    services_refunds.refund_payment(payment, amount="5.00", reason="part", actor=staff)
    assert seen[0].refund_application_fee is True and seen[0].reverse_transfer is False
    assert RefundRequest("pi", 1, "usd", "r", "k", {}).refund_application_fee is False


def test_stripe_adapter_sends_the_fee_flag_only_when_asked(monkeypatch):
    from apps.payments import stripe_client
    from apps.payments.providers.stripe import StripeProvider
    calls = []
    monkeypatch.setattr(stripe_client, "create_refund", lambda source, **params: calls.append(params) or
                        {"id": "re_x", "status": "succeeded"})
    adapter = StripeProvider()
    adapter.create_refund(object(), RefundRequest("pi_1", 100, "usd", "1", "k", {}, refund_application_fee=True))
    adapter.create_refund(object(), RefundRequest("pi_1", 100, "usd", "2", "k2", {}))
    assert calls[0]["refund_application_fee"] is True and "refund_application_fee" not in calls[1]
    assert "reverse_transfer" not in calls[0]


def test_refunds_report_groups_cases_and_manual_refunds_per_currency():
    space = space_with_currency("reg-report")
    staff = make_member("reg-report-staff", space)
    _, approved = paid(space, "reg-report-a")
    user_b, declined = paid(space, "reg-report-b")
    _, manual = paid(space, "reg-report-c")
    approve_case(open_due_case(approved, reason_code="event_cancelled", actor=None), actor=staff,
                 amount=Decimal("8.00"), receipt=receipt())
    decline_case(request_refund(declined, member=user_b, reason="x"), actor=staff, note="No")
    record_offline_refund(manual, amount=Decimal("3.00"), reason="desk", receipt=receipt(), actor=staff)
    rows = {(row["reason_code"]): row for row in build_refunds(space.pk).records}
    assert rows["event_cancelled"]["refunded"] == Decimal("8.00") and rows["event_cancelled"]["due"] == Decimal("20.00")
    assert rows["member_request"]["declined"] == 1 and rows["member_request"]["count"] == 1
    assert rows["manual"]["refunded"] == Decimal("3.00") and rows["manual"]["area"] == "events"
    assert all(row["currency"] == "usd" for row in rows.values())
    other = space_with_currency("reg-report-other")
    assert build_refunds(other.pk).records == []


def test_policy_api_round_trip_requires_manage_makerspace():
    from tests.payments.refund_case_helpers import finance_reader
    from tests.return_helpers import authenticated_client
    space = space_with_currency("reg-policy-api")
    manager = make_member("reg-policy-manager", space)
    finance = finance_reader(space)
    url = f"/api/v1/admin/makerspace/{space.pk}/refund-policies"
    listed = authenticated_client(finance).get(url)
    assert listed.status_code == 200 and [row["configured"] for row in listed.data] == [False, False, False]
    body = {"full_before_minutes": 2880, "partial_before_minutes": 1440, "partial_percent": 50,
            "cancellation_fee": "2.50"}
    assert authenticated_client(finance).put(f"{url}/events", body, format="json").status_code == 404
    saved = authenticated_client(manager).put(f"{url}/events", body, format="json")
    assert saved.status_code == 200 and saved.data["configured"] is True and saved.data["currency"] == "usd"
    bad = authenticated_client(manager).put(f"{url}/events", {**body, "partial_before_minutes": 9999}, format="json")
    assert bad.status_code == 400
    assert authenticated_client(manager).put(f"{url}/loans", body, format="json").status_code == 404
    assert authenticated_client(manager).delete(f"{url}/events").status_code == 204
    assert not RefundPolicy.objects.exists()
