"""Verified contact reports (#80/#103) and bearer technician consent (#128 C-4)."""
from datetime import timedelta

import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401
from django.core import signing
from django.utils import timezone
from rest_framework.test import APIClient

from apps.hardware_requests.contact_verification import email_key
from apps.hardware_requests.models import HardwareRequest
from apps.maintenance.models import IssueReport
from apps.maintenance.repairs import optin, photos, storage
from tests.inventory.switch_support_cx11b_p1 import snapshot
from tests.maintenance.l16_helpers import external, world
from tests.maintenance.report_world_cx11b_g3 import SOURCES, otp, report_world
from tests.maintenance.route_support_cx11b_g3 import audit_delta, person_client, prove, send
from tests.modules.switch_matrix_object_helpers import client_for, response_pair
from tests.modules.test_switch_matrix_objects_rest_support import no_domain_writes, switch

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_inventory,
              pytest.mark.area_machines, pytest.mark.area_bookings]


def contact_world(source, native):
    w = report_world(source, False)
    w.space.enabled_modules = [k for k in w.space.enabled_modules if k not in {"member_accounts", "membership"}]
    w.space.save(update_fields=["enabled_modules"])
    w.email = "pat@example.test"
    if source == "loan":
        HardwareRequest.objects.filter(pk=w.origin.pk).update(anonymous_payload_fingerprint=email_key(w.space, w.email))
    else:
        w.origin.member, w.origin.email = None, w.email
        w.origin.save(update_fields=["member", "email"])
    w.challenge = otp(w.space, w.email)
    w.client = client_for(w.manager, w.space, native) if native else APIClient()
    w.body = {**w.link, "title": "Cracked handle", "description": "Handle cracked", "contact_name": "Pat",
              "contact_email": w.email, "email_code": "752903"}
    return w


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("source", ["loan", "booking"])
@pytest.mark.parametrize("gate", ["feature", "parent"])
def test_verified_contact_report_effect_switch_and_missing_space(source, gate, native):
    w = contact_world(source, native)
    _, feature, parent = SOURCES[source]
    key = feature if gate == "feature" else parent

    def call(c):
        # Public slug routes carry no account standing (80/103). Missing public
        # space is the no-standing probe; invalid OTP is checked separately.
        w.challenge.refresh_from_db()
        consumed = w.challenge.consumed_at
        response = send(c or w.client, "public-issue-report", ["g3-no-such-space" if c else w.space.slug], "post", w.body)
        if response.status_code == 404:
            w.challenge.refresh_from_db()
            assert w.challenge.consumed_at == consumed
        return response

    def check(response):
        row = IssueReport.objects.get(pk=response.data["id"])
        assert (row.reporter_id, row.reporter_name, row.reporter_email, row.title, row.state) == (
            None, "Pat", w.email, "Cracked handle", "reported")
        assert getattr(row, w.origin_field + "_id") == w.origin.pk
        assert row.events.get().kind == "reported" and IssueReport.objects.filter(makerspace=w.space).count() == 1
        w.challenge.refresh_from_db()
        assert w.challenge.consumed_at is not None

    # The second disabled cycle occurs after a successful report spent the OTP;
    # the gate must still run before consume_code (517).
    prove(w.space, {"origin": w.origin}, key, call, check, status=201, off=(404, "capability_disabled"),
          outsiders=[(APIClient(), (404, "not_found"))], audits={"issue.reported": 1})


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
def test_contact_ownership_requires_the_real_one_time_code_before_eligibility(native):
    w = contact_world("loan", native)
    # Wrong code deliberately burns an authentication attempt and audit (80).
    # No issue, repair child, stock movement or loan mutation may result.
    before = HardwareRequest.objects.filter(pk=w.origin.pk).values().get()
    with audit_delta(w.space, {"request.contact_code_failed": 1, "issue.reported": 0}):
        answer = send(w.client, "public-issue-report", [w.space.slug], "post", {**w.body, "email_code": "000000"})
    assert response_pair(answer) == (400, None)
    assert answer.data["email_code"].code == "invalid"
    w.challenge.refresh_from_db()
    assert w.challenge.failed_attempts == 1 and w.challenge.consumed_at is None
    assert not IssueReport.objects.filter(makerspace=w.space).exists()
    assert HardwareRequest.objects.filter(pk=w.origin.pk).values().get() == before
    other = otp(w.space, "other@example.test")
    answer = send(w.client, "public-issue-report", [w.space.slug], "post", {**w.body, "contact_email": "other@example.test"})
    assert response_pair(answer) == (403, "reporter_not_eligible")
    other.refresh_from_db()
    assert other.consumed_at is not None and not IssueReport.objects.filter(makerspace=w.space).exists()


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("source", ["loan", "booking", "job"])
@pytest.mark.parametrize("gate", ["feature", "parent"])
def test_public_photo_upload_is_email_bound_and_staged(source, gate, native, monkeypatch):
    w = report_world(source, False)
    w.space.enabled_modules = [k for k in w.space.enabled_modules if k not in {"member_accounts", "membership"}]
    w.space.save(update_fields=["enabled_modules"])
    client = client_for(w.manager, w.space, native) if native else APIClient()
    _, feature, parent = SOURCES[source]
    key = feature if gate == "feature" else parent
    seen = []

    def presign(key, mime):
        seen.append((key, mime))
        return {"url": "https://storage.example.test/" + storage.staging_key(key), "method": "PUT"}
    monkeypatch.setattr(storage, "presign", presign)

    def check(response):
        grant = signing.loads(response.data["photo_token"], salt=photos.SALT, max_age=photos.MAX_AGE)
        assert (grant["m"], grant["o"]) == (w.space.pk, photos.owner_for_email(email_key(w.space, "pat@example.test")))
        assert storage.owns_key(grant["k"], w.space.pk) and seen[-1] == (grant["k"], "image/png")
        assert response.data["upload"]["url"].endswith(storage.staging_key(grant["k"]))
        assert not IssueReport.objects.filter(makerspace=w.space).exists()

    prove(w.space, {"origin": w.origin}, key,
          lambda c: send(c or client, "public-issue-photo-upload", ["g3-no-such-space" if c else w.space.slug], "post",
                         {"contact_email": "pat@example.test", "content_type": "image/png"}), check,
          status=201, off=(404, "capability_disabled"), outsiders=[(APIClient(), (404, "not_found"))])


@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["machines", "bookings", "loans.enabled", "machines.repairs", "inventory.repairs",
                                 "bookings.room_repairs", "sms", "whatsapp", "telegram"])
def test_bearer_consent_retains_the_same_contact_independently_of_delivery_switches(method, native, key):
    # C-4: a valid seven-day bearer proves the recipient, not a signed-in account;
    # recording consent does not authorize delivery or resurrect archived contacts.
    w = world("g3-opt-in")
    token = "g3-retained-bearer"
    row = external(w, opt_in_digest=optin.digest(token), opt_in_expires_at=timezone.now() + timedelta(days=7))
    client = person_client(w.manager, w.space, native) if native else APIClient()
    objects = {"contact": row}

    def check(response):
        row.refresh_from_db()
        assert response.data["technician_name"] == "Ravi Repairs" and response.data["makerspace_name"] == w.space.name
        assert "email" not in response.data and "phone" not in response.data
        if method == "post":
            assert row.sms_opted_in_at is not None and "sms" in row.channels and response.data["consent"]["sms"] is True

    for disabled in (False, True, False):
        original = switch(w.space, key) if disabled else None
        before = snapshot(objects)
        with no_domain_writes():
            invalid = send(client, "public-technician-opt-in", ["wrong-bearer"], method, {"channels": ["sms"]})
        assert response_pair(invalid) == (404, "opt_in_invalid") and snapshot(objects) == before
        with audit_delta(w.space, {"technician.opted_in": 1 if method == "post" else 0}):
            response = send(client, "public-technician-opt-in", [token], method, {"channels": ["sms"]})
        assert response_pair(response) == (200, None)
        check(response)
        if disabled:
            retained = snapshot(objects)
            switch(w.space, key, original=original)
            assert snapshot(objects) == retained

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]
