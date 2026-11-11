"""Reviewers cannot read private line text, payees, receipt bytes or foreign rows."""
import json
import pytest
from django.utils import timezone
from rest_framework.test import force_authenticate, APIRequestFactory
from apps.accounts.models import User
from tests.events.manual_grant_fixture import create_manual_grant
from apps.event_reimbursements.views_admin import ClaimDetailView, ClaimReviewView, ProgrammeView
from apps.event_reimbursements.views_member import ClaimView, ReimbursementView
from apps.event_reimbursements import claim_workflow
from apps.event_reimbursements.projections import claim_detail
from tests.accounts.test_reauthentication import request as session_request
from .helpers import submitted, decision_data
from .conftest import cmd

pytestmark = pytest.mark.django_db(transaction=True)


def test_private_event_virtual_context_requires_canonical_participation(world):
    world.event.is_public = False
    world.event.save(update_fields=["is_public"])
    req = session_request(world.owner, surface="member"); req.method = "GET"
    result = call(ReimbursementView, req, pk=world.event.pk, makerspace_id=world.space.pk)
    assert result.status_code == 404
    from apps.events.services_registration import register
    register(world.event, member=world.owner, actor=world.manager, staff_registration=True)
    req = session_request(world.owner, surface="member"); req.method = "GET"
    result = call(ReimbursementView, req, pk=world.event.pk, makerspace_id=world.space.pk)
    assert result.status_code == 200


def call(view, req, **kwargs):
    force_authenticate(req, user=req.user, token=req.auth)
    return view.as_view()(req, **kwargs)


def test_reviewer_detail_is_metadata_only_and_finance_has_private_lines(world, monkeypatch):
    claim, _, _ = submitted(world, monkeypatch)
    reviewer = User.objects.create_user(username="receipt-reviewer", account_kind="member")
    create_manual_grant(makerspace=world.space, event=world.event, user=reviewer,
        permissions=["review_reimbursements"], granted_by=world.manager)
    req = session_request(reviewer, surface="delegated")
    req.method = "GET"
    response = call(ClaimDetailView, req, pk=world.event.pk, claim_id=claim.pk)
    assert response.status_code == 200
    encoded = json.dumps(response.data, default=str)
    assert "Private vendor" not in encoded and "Private traveller" not in encoded
    assert "draft" not in response.data and "revisions" not in response.data
    assert "receipt_metadata" in response.data
    assert "download" not in encoded and "object_key" not in encoded and "payee" not in encoded
    assert "Private vendor" in json.dumps(claim_detail(claim, finance=True), default=str)
    assert response["Cache-Control"] == "private, no-store"


def test_other_member_and_foreign_event_nested_claim_are_uniform_404(world, make_world, monkeypatch):
    claim, _, _ = submitted(world, monkeypatch)
    other = User.objects.create_user(username="other-borrower", account_kind="member")
    req = session_request(other, surface="member"); req.method = "GET"
    response = call(ClaimView, req, pk=world.event.pk, makerspace_id=world.space.pk)
    assert response.status_code == 404
    foreign = make_world()
    req = foreign.finance; req.method = "GET"
    response = call(ClaimDetailView, req, pk=foreign.event.pk, claim_id=claim.pk)
    assert response.status_code == 404


def test_reviewer_finance_decision_does_not_move_money(world, monkeypatch):
    claim, _, line_id = submitted(world, monkeypatch)
    reviewer = User.objects.create_user(username="decision-reviewer", account_kind="member")
    create_manual_grant(makerspace=world.space, event=world.event, user=reviewer,
        permissions=["review_reimbursements"], granted_by=world.manager)
    value = decision_data(world, claim, line_id, 10000)
    session = session_request(reviewer, surface="delegated")
    req = APIRequestFactory().post("/", value, format="json", HTTP_ORIGIN="http://localhost:5000",
        HTTP_IDEMPOTENCY_KEY=str(value["operation_id"]))
    req.user, req.auth = reviewer, session.auth
    response = call(ClaimReviewView, req, pk=world.event.pk, claim_id=claim.pk)
    assert response.status_code == 403
    world.pool.refresh_from_db()
    assert (world.pool.reserved_minor, world.pool.committed_minor) == (10000, 0)
    assert not claim.decisions.exists()


def test_finance_requires_recent_reauth_and_revoked_sessions_refuse(world):
    req = session_request(world.manager)
    from apps.event_reimbursements.programme_workflow import configure
    from rest_framework.exceptions import PermissionDenied
    with pytest.raises(PermissionDenied):
        configure(request=req, event_id=world.event.pk, data=cmd(world.programme.version,
            policy_revision=world.programme.finance_policy_revision, settings={}, pool_id=world.pool.pk,
            expected_pool_version=world.pool.version, budget_delta_minor=0, reason_code="other"))


def test_audits_and_notifications_do_not_include_claim_private_text(world, monkeypatch):
    claim, _, line_id = submitted(world, monkeypatch)
    claim_workflow.decide(request=world.finance, event_id=world.event.pk, claim_id=claim.pk,
        data=decision_data(world, claim, line_id, 9000, outcome="partially_approved"))
    from apps.audit.models import AuditLog
    from apps.integrations.models_contract import NotificationEnvelope
    audit = json.dumps(list(AuditLog.objects.filter(makerspace=world.space).values("action", "meta")), default=str)
    notices = json.dumps(list(NotificationEnvelope.objects.filter(makerspace=world.space).values("context", "message_body")), default=str)
    for secret in ("Private vendor", "Private traveller", "Private support statement", "Private financial explanation"):
        assert secret not in audit and secret not in notices
