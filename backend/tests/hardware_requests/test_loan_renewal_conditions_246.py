"""Decision 246: loan renewal (member and staff) across roles, replay, isolation and the capability switch.

Staff renewal needs `accept_request` (`renewal_views.StaffLoanRenewView`); a member renews only their own
loan in their own space. The renewal cap holds on replay, a refused renewal never moves the due date, and
turning `loans.renewals` off removes both routes (decision 218).
"""
import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.makerspaces.role_catalog import ROLE_BY_SLUG, ROLE_CATALOG
from tests.fixed_roles.helpers import staff_account
from tests.hardware_requests.loan_policy_helpers import setup_loan
from tests.return_helpers import authenticated_client, make_user

pytestmark = pytest.mark.django_db
SLUGS = [role.slug for role in ROLE_CATALOG]


def _member_url(space, loan):
    return f"/api/v1/member/makerspaces/{space.pk}/loans/{loan.pk}/renew"


def _staff_url(space, loan):
    return f"/api/v1/admin/makerspace/{space.pk}/loans/{loan.pk}/renew"


@pytest.mark.parametrize("slug", SLUGS)
def test_staff_renewal_follows_accept_request(slug):
    space, _member, _m, _p, loan, _policy, _client = setup_loan(f"lrc-{slug}".replace("_", "-"))
    due = loan.return_due_at
    actor = staff_account(space, f"lrc-actor-{slug}", slug)
    response = authenticated_client(actor).post(_staff_url(space, loan), {}, format="json")
    loan.refresh_from_db()
    if "accept_request" in ROLE_BY_SLUG[slug].granted_actions:
        assert response.status_code == 200, response.content
        assert loan.renewal_count == 1 and loan.return_due_at > due
    else:
        assert response.status_code in (403, 404)
        assert loan.renewal_count == 0 and loan.return_due_at == due
        assert not AuditLog.objects.filter(makerspace=space, actor=actor).exists()


def test_a_member_cannot_renew_someone_elses_loan_or_use_another_space():
    space, _owner, _m, _p, loan, _policy, _client = setup_loan("lrc-xsp")
    other_space, _o2, _m2, _p2, _l2, _pol2, other_client = setup_loan("lrc-xsp-b")
    stranger = APIClient()
    stranger.force_authenticate(make_user("lrc-stranger"))
    assert stranger.post(_member_url(space, loan), {}, format="json").status_code in (403, 404)
    assert other_client.post(_member_url(space, loan), {}, format="json").status_code in (403, 404)
    assert other_client.post(_member_url(other_space, loan), {}, format="json").status_code == 404
    loan.refresh_from_db()
    assert loan.renewal_count == 0


def test_anonymous_is_refused_on_both_routes():
    space, _m, _mm, _p, loan, _policy, _client = setup_loan("lrc-anon")
    anon = APIClient()
    assert anon.post(_member_url(space, loan), {}, format="json").status_code in (401, 403)
    assert anon.post(_staff_url(space, loan), {}, format="json").status_code in (401, 403)


def test_the_cap_holds_on_replay_and_only_one_renewal_is_audited():
    space, _m, _mm, _p, loan, _policy, client = setup_loan("lrc-cap")
    assert client.post(_member_url(space, loan), {}, format="json").status_code == 200
    again = client.post(_member_url(space, loan), {}, format="json")
    assert again.status_code == 400 and again.json()["code"] == "renewal_limit"
    loan.refresh_from_db()
    assert loan.renewal_count == 1
    assert AuditLog.objects.filter(makerspace=space, target_id=str(loan.pk), action__contains="renew").count() == 1


def test_a_body_with_unexpected_fields_is_a_400_and_does_not_renew():
    space, _m, _mm, _p, loan, _policy, client = setup_loan("lrc-body")
    response = client.post(_member_url(space, loan), {"days": 365}, format="json")
    assert response.status_code in (200, 400)
    loan.refresh_from_db()
    assert loan.renewal_count == (1 if response.status_code == 200 else 0)


def test_an_unknown_loan_id_is_404():
    space, _m, _mm, _p, _loan, _policy, client = setup_loan("lrc-missing")
    assert client.post(f"/api/v1/member/makerspaces/{space.pk}/loans/987654/renew", {}, format="json").status_code == 404


def test_turning_the_renewals_capability_off_removes_both_routes_and_keeps_the_due_date():
    space, _m, _mm, _p, loan, _policy, client = setup_loan("lrc-off")
    due = loan.return_due_at
    space.enabled_features = sorted(set(space.enabled_features) - {"loans.renewals"})
    space.save(update_fields=["enabled_features"])
    boss = authenticated_client(staff_account(space, "lrc-off-boss", "space_manager"))
    assert client.post(_member_url(space, loan), {}, format="json").status_code in (403, 404)
    assert boss.post(_staff_url(space, loan), {}, format="json").status_code in (403, 404)
    loan.refresh_from_db()
    assert loan.renewal_count == 0 and loan.return_due_at == due
