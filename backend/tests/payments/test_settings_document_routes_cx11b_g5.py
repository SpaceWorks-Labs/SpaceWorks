"""Retained ledger settings and issued documents stay available without creation switches."""
from decimal import Decimal
from io import BytesIO
from urllib.parse import parse_qs, urlparse

import pytest
from django.core import signing
from django.urls import reverse
from pypdf import PdfReader

from apps.payments.document_delivery import SALT, download_path
from apps.payments.documents import issue_bill
from apps.payments.models import EventMoneySettings, MakerspaceBillingSettings
from tests.payments.ledger_fixtures_cx11b_g5 import seed
from tests.payments.route_support_cx11b_g5 import cycle, hidden, ids, personal_client, world

pytestmark = [pytest.mark.django_db, pytest.mark.area_payments_ledger]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["payments", "charges.enabled"])
@pytest.mark.parametrize("name,method", [("payment-billing-settings", "GET"), ("payment-billing-settings", "PATCH"),
    ("admin-event-money-settings", "GET"), ("admin-event-money-settings", "PATCH")])
def test_money_settings_exact_saved_values_standing_and_core_independence(native, key, name, method):
    s = seed(native)
    event_policy = EventMoneySettings.for_makerspace(s.space)
    event_policy.save()
    billing = name == "payment-billing-settings"
    body = {"payment_terms_days": 17} if billing else {"expected_version": event_policy.version, "prize_tds_rate": "7.50"}
    audit = ("payment.billing_policy_updated" if billing else "payment.event_money_settings_updated",) if method == "PATCH" else ()
    def result(response):
        if billing:
            row = MakerspaceBillingSettings.objects.get(makerspace=s.space)
            expected = 17 if method == "PATCH" else s.policy.payment_terms_days
            assert row.payment_terms_days == response.data["payment_terms_days"] == expected
            assert response.data["payment_instructions"] == "G5 pay at desk"
        else:
            row = EventMoneySettings.objects.get(makerspace=s.space)
            expected = Decimal("7.50") if method == "PATCH" else event_policy.prize_tds_rate
            assert row.prize_tds_rate == Decimal(response.data["prize_tds_rate"]) == expected
            assert row.version == event_policy.version + (method == "PATCH")
    w = world(s.space, s.client, reverse(name, kwargs={"makerspace_id": s.space.pk}), method,
        body if method == "PATCH" else {}, audit=audit, check=result, probes=[hidden(s.foreign)])
    cycle(w, key)


DOCUMENTS = ("staff-payment-documents", "staff-payment-document-url", "payment-document-download",
             "member-payment-documents", "member-payment-document-url")


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["payments", "billing.documents"])
@pytest.mark.parametrize("name", DOCUMENTS)
def test_document_route_exact_subject_download_binding_and_retained_issued_document(native, key, name):
    s = seed(native)
    s.space.enabled_features += ["billing.documents"]
    s.space.save(update_fields=["enabled_features"])
    document = issue_bill(s.payment, actor=s.actor)
    member = name.startswith("member-")
    caller = s.payer_client if member or name == "payment-document-download" else s.client
    if native and name == "payment-document-download":
        # This mixed-audience route selects its tenant through the signed grant.
        for transport in (caller, s.client, s.foreign):
            transport._credentials.pop("HTTP_X_MAKERSPACE_ID", None)
    kwargs = {"makerspace_id": s.space.pk}
    if name.endswith("-url"):
        kwargs["document_id"] = document.pk
    url = reverse(name, kwargs=kwargs) if name != "payment-document-download" else download_path(
        document, s.payer, makerspace_id=s.space.pk, audience="member")
    def result(response):
        if name.endswith("documents"):
            assert ids(response) == [document.pk]
            assert (response.data["results"][0]["payment"], response.data["results"][0]["number"]) == (s.payment.pk, document.number)
        elif name.endswith("-url"):
            token = parse_qs(urlparse(response.data["url"]).query)["token"][0]
            owner = s.payer if member else s.actor
            assert signing.loads(token, salt=SALT) == {"document": document.pk, "user": owner.pk,
                "space": s.space.pk, "audience": "member" if member else "staff"}
            assert response.data["expires_in"] == 300
        else:
            assert response["Content-Type"] == "application/pdf" and response["Cache-Control"] == "private, no-store"
            text = " ".join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages)
            assert document.number in text and "G5 retained charge" in text
        assert document.payment_id == s.payment.pk and document.amount == Decimal("100")
    if name == "payment-document-download":
        # User-bound signed grant: an authenticated non-owner is 403, not a tenant oracle (494).
        probes = [hidden(s.client, (403, "permission_denied")), hidden(s.foreign, (403, "permission_denied"))]
    elif member:
        # 494 preserves member access contracts: an account with no membership/charge gets 403.
        probes = [hidden(s.foreign, (403, "permission_denied"))]
        from tests.accounts.account_factories import make_membership
        make_membership(s.actor, s.space)
        other = personal_client(s.actor, s.space, native)
        if name.endswith("-url"):
            # Give this other person membership standing, but never the payer's document.
            probes.append(hidden(other, (404, "not_found")))
        else:
            def empty(response):
                assert response.data["count"] == 0 and response.data["results"] == []
            probes.append((other, (200, None), empty))
    elif name == "staff-payment-documents" and not native:
        # Staff document discovery is action-scoped: a foreign manager sees no rows.
        def empty(response):
            assert response.data == {"count": 0, "next": None, "previous": None, "results": []}
        probes = [(s.foreign, (200, None), empty)]
    else:
        probes = [hidden(s.foreign)]
    cycle(world(s.space, caller, url, check=result, probes=probes), key)
