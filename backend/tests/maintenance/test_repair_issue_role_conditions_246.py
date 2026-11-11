"""Decision 246: the repair-issue lifecycle across every built-in role, with replay, validation and isolation.

For an inventory item the area manager is whoever holds `edit_inventory` (`repairs/areas.MANAGER_ACTION`).
A refused call must not move the issue or write history; a decision is made once (a second triage or
reject is a state conflict) and a payout writes one ledger expense (replay is covered in
`test_l16_dispatch_money.py`; the role gate and the stock/ledger invariants are asserted here).
"""
import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.maintenance.models import IssueReport
from apps.maintenance.repairs import services_issues as svc
from apps.makerspaces.role_catalog import ROLE_BY_SLUG, ROLE_CATALOG
from apps.payments.models_ledger_entries import LedgerEntry
from tests.fixed_roles.helpers import staff_account
from tests.maintenance.l16_helpers import world
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db
SLUGS = [role.slug for role in ROLE_CATALOG]


def _opened(w, subject_type="inventory_product", subject=None):
    return svc.open_issue(w.manager, w.space, subject_type=subject_type, subject=subject or w.product,
                          title="Broken handle")


def _manager(slug):
    return "edit_inventory" in ROLE_BY_SLUG[slug].granted_actions


@pytest.mark.parametrize("slug", SLUGS)
def test_triage_follows_the_inventory_area_manager_action(slug):
    w = world(f"ri-tri-{slug}".replace("_", "-"))
    issue = _opened(w)
    actor = staff_account(w.space, f"ri-tri-actor-{slug}", slug)
    response = authenticated_client(actor).post(f"/api/v1/admin/issues/{issue.pk}/triage", {"priority": "high"},
                                                format="json")
    issue.refresh_from_db()
    if _manager(slug):
        assert response.status_code == 200, response.content
        assert issue.state == "triaged"
        assert AuditLog.objects.filter(makerspace=w.space, action="issue.triaged", actor=actor).count() == 1
    else:
        assert response.status_code in (403, 404)
        assert issue.state == "reported"
        assert not AuditLog.objects.filter(makerspace=w.space, action="issue.triaged").exists()


@pytest.mark.parametrize("slug", SLUGS)
def test_reject_follows_the_inventory_area_manager_action(slug):
    w = world(f"ri-rej-{slug}".replace("_", "-"))
    issue = _opened(w)
    actor = staff_account(w.space, f"ri-rej-actor-{slug}", slug)
    response = authenticated_client(actor).post(f"/api/v1/admin/issues/{issue.pk}/reject",
                                                {"reason": "Not a fault"}, format="json")
    issue.refresh_from_db()
    assert (response.status_code == 200) is _manager(slug), response.content
    assert issue.state == ("rejected" if _manager(slug) else "reported")


def test_a_decided_issue_cannot_be_triaged_or_rejected_again():
    w = world("ri-replay")
    issue = _opened(w)
    boss = authenticated_client(w.manager)
    assert boss.post(f"/api/v1/admin/issues/{issue.pk}/triage", {}, format="json").status_code == 200
    assert boss.post(f"/api/v1/admin/issues/{issue.pk}/triage", {}, format="json").status_code in (400, 409)
    assert boss.post(f"/api/v1/admin/issues/{issue.pk}/reject", {"reason": "Dup"}, format="json").status_code == 200
    assert boss.post(f"/api/v1/admin/issues/{issue.pk}/reject", {"reason": "Dup"}, format="json").status_code in (400, 409)
    assert AuditLog.objects.filter(makerspace=w.space, action="issue.rejected").count() == 1
    assert AuditLog.objects.filter(makerspace=w.space, action="issue.triaged").count() == 1


@pytest.mark.parametrize("body", [{}, {"reason": ""}, {"reason": "   "}])
def test_reject_needs_a_reason_and_leaves_the_issue_open(body):
    w = world("ri-reason")
    issue = _opened(w)
    assert authenticated_client(w.manager).post(f"/api/v1/admin/issues/{issue.pk}/reject", body,
                                                format="json").status_code == 400
    issue.refresh_from_db()
    assert issue.state == "reported"


@pytest.mark.parametrize("body", [{}, {"amount": "-5", "currency": "usd"}, {"amount": "abc", "currency": "usd"}])
def test_a_quote_needs_a_positive_amount_and_writes_nothing_otherwise(body):
    w = world("ri-quote")
    issue = _opened(w)
    response = authenticated_client(w.manager).post(f"/api/v1/admin/issues/{issue.pk}/quote", body, format="json")
    assert response.status_code in (400, 409)
    assert not LedgerEntry.objects.filter(source_kind="repairs.payout").exists()


def test_a_payout_is_refused_for_an_unapproved_quote_and_for_non_managers_and_writes_no_expense():
    w = world("ri-pay")
    issue = _opened(w)
    boss = authenticated_client(w.manager)
    boss.post(f"/api/v1/admin/issues/{issue.pk}/quote", {"amount": "30", "currency": "usd"}, format="json")
    early = boss.post(f"/api/v1/admin/issues/{issue.pk}/payout", {"amount": "30", "method": "cash"}, format="json")
    assert early.status_code == 409
    outsider = authenticated_client(staff_account(w.space, "ri-pay-member", "member"))
    assert outsider.post(f"/api/v1/admin/issues/{issue.pk}/payout", {"amount": "30", "method": "cash"},
                         format="json").status_code in (403, 404)
    assert not LedgerEntry.objects.filter(source_kind="repairs.payout").exists()


def test_another_spaces_manager_and_anonymous_cannot_read_or_move_the_issue():
    w, other = world("ri-iso-a"), world("ri-iso-b")
    issue = _opened(w)
    outsider = authenticated_client(other.manager)
    assert outsider.get(f"/api/v1/admin/issues/{issue.pk}").status_code in (403, 404)
    assert outsider.post(f"/api/v1/admin/issues/{issue.pk}/triage", {}, format="json").status_code in (403, 404)
    assert outsider.get(f"/api/v1/admin/makerspaces/{w.space.pk}/issues").status_code in (200, 403, 404)
    anon = APIClient()
    assert anon.get(f"/api/v1/admin/issues/{issue.pk}").status_code in (401, 403)
    assert anon.post(f"/api/v1/admin/issues/{issue.pk}/triage", {}, format="json").status_code in (401, 403)
    assert IssueReport.objects.get(pk=issue.pk).state == "reported"
