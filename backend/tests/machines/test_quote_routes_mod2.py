"""MOD-2: the member approve-quote and decline-quote HTTP routes with their conditions."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.machines import service_workflow_review as review
from apps.machines.models import MachineServiceRequest
from apps.payments.models import Payment
from tests.machines.eta_helpers import job, owner, world
from tests.machines.test_job_flow import priced

from tests.refusal_helpers_mod2b import refused

pytestmark = pytest.mark.django_db
S = MachineServiceRequest.Status


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _quoted(slug):
    w = priced(world(slug))
    member = owner(f"{slug}-m")
    row = review.send_quote(job(w, member=member), w.staff, estimated_minutes=30)
    assert row.status == S.QUOTED
    return w, member, row


def _approve(client, row, digest):
    return client.post(reverse("member-machine-job-approve-quote", args=[row.pk]), {"digest": digest}, format="json")


def _decline(client, row):
    return client.post(reverse("member-machine-job-decline-quote", args=[row.pk]), {}, format="json")


def test_approve_with_the_shown_digest_queues_the_job_and_audits_once():
    w, member, row = _quoted("mod2-q-ok")
    response = _approve(_client(member), row, row.quote_digest)
    assert response.status_code == 200, response.content
    row.refresh_from_db()
    assert row.status != S.QUOTED and row.quote_approved_at is not None
    assert AuditLog.objects.filter(target_id=str(row.pk), action__icontains="quote_approved").count() == 1


def test_approving_twice_is_refused_and_does_not_audit_or_charge_again():
    w, member, row = _quoted("mod2-q-twice")
    assert _approve(_client(member), row, row.quote_digest).status_code == 200
    payments = Payment.objects.count()
    second = _approve(_client(member), row, row.quote_digest)
    refused(second, 409, "service_invalid_transition")
    assert Payment.objects.count() == payments
    assert AuditLog.objects.filter(target_id=str(row.pk), action__icontains="quote_approved").count() == 1


@pytest.mark.parametrize("digest", ["0" * 64, "", "x" * 65])
def test_a_wrong_or_malformed_digest_never_approves(digest):
    w, member, row = _quoted("mod2-q-digest")
    response = _approve(_client(member), row, digest)
    if digest == "0" * 64:
        refused(response, 409, "price_changed")
    else:
        assert response.status_code == 400 and "digest" in response.json()
    row.refresh_from_db()
    assert row.status == S.QUOTED


def test_missing_digest_is_a_400():
    w, member, row = _quoted("mod2-q-nodigest")
    response = _client(member).post(reverse("member-machine-job-approve-quote", args=[row.pk]), {}, format="json")
    assert response.status_code == 400


def test_an_expired_quote_cannot_be_approved_and_nothing_is_charged():
    w, member, row = _quoted("mod2-q-expired")
    MachineServiceRequest.objects.filter(pk=row.pk).update(quote_expires_at=timezone.now() - timedelta(minutes=1))
    before = Payment.objects.count()
    response = _approve(_client(member), row, row.quote_digest)
    refused(response, 409, "service_invalid_transition")
    row.refresh_from_db()
    assert row.status != S.ACCEPTED and Payment.objects.count() == before


def test_decline_cancels_with_nothing_charged_and_a_second_decline_is_refused():
    w, member, row = _quoted("mod2-q-decline")
    before = Payment.objects.count()
    response = _decline(_client(member), row)
    assert response.status_code == 200, response.content
    row.refresh_from_db()
    assert row.status == S.CANCELLED and Payment.objects.count() == before
    refused(_decline(_client(member), row), 409, "service_invalid_transition")
    refused(_approve(_client(member), row, row.quote_digest), 409, "service_invalid_transition")


def test_another_member_and_signed_out_cannot_answer_someone_elses_quote():
    w, member, row = _quoted("mod2-q-owner")
    stranger = owner("mod2-q-stranger")
    for call in (lambda c: _approve(c, row, row.quote_digest), lambda c: _decline(c, row)):
        assert call(_client(stranger)).status_code == 404  # not a 403: never confirms the job exists
        refused(call(APIClient()), 401, "not_authenticated")
    row.refresh_from_db()
    assert row.status == S.QUOTED


def test_an_unquoted_pending_job_cannot_be_approved_or_declined_through_the_quote_routes():
    w = priced(world("mod2-q-pending"))
    member = owner("mod2-q-pending-m")
    row = job(w, member=member)
    refused(_approve(_client(member), row, "0" * 64), 409, "service_invalid_transition")
    refused(_decline(_client(member), row), 409, "service_invalid_transition")
    row.refresh_from_db()
    assert row.status != S.CANCELLED
