"""Decision 221(a): account-only borrowers self-renew only when the Space Manager allows it."""
import pytest

from apps.audit.models import AuditLog
from apps.makerspaces.member_loans import member_loans
from apps.makerspaces.loan_policy_settings import update_loan_policy
from rest_framework.exceptions import PermissionDenied
from django.utils import timezone
from tests.hardware_requests.loan_policy_helpers import setup_loan
from tests.return_helpers import make_member

pytestmark = pytest.mark.django_db


def account_only(space):
    space.enabled_modules = sorted((set(space.enabled_modules) - {"membership"}) | {"member_accounts"})
    space.save(update_fields=["enabled_modules"])


def renew(client, space, loan):
    return client.post(f"/api/v1/member/makerspaces/{space.pk}/loans/{loan.pk}/renew", {}, format="json")


def test_account_only_borrower_cannot_self_renew_by_default():
    space, member, _, _, loan, policy, client = setup_loan("sr-default")
    account_only(space)
    assert policy.account_self_renewal is False
    assert renew(client, space, loan).status_code == 404  # surface absent, as before
    row = member_loans(space, member, timezone.now())[0]
    assert row["can_renew"] is False and row["renewal_refusal"] == "self_renewal_off"


def test_switch_on_applies_the_normal_policy_and_limits():
    space, member, _, _, loan, policy, client = setup_loan("sr-on")
    account_only(space)
    policy.account_self_renewal = True
    policy.save()
    assert member_loans(space, member, timezone.now())[0]["can_renew"] is True
    assert renew(client, space, loan).status_code == 200
    loan.refresh_from_db()
    assert loan.renewal_count == 1
    again = renew(client, space, loan)  # loan_max_renewals defaults to 1: the cap still applies
    assert again.status_code == 400 and again.json()["code"] == "renewal_limit"


@pytest.mark.parametrize("status", ["restricted", "suspended"])
def test_switch_on_still_refuses_restricted_or_suspended_accounts(status):
    space, member, _, _, loan, policy, client = setup_loan(f"sr-{status}")
    account_only(space)
    policy.account_self_renewal = True
    policy.save()
    member.access_status = status
    member.save(update_fields=["access_status"])
    assert renew(client, space, loan).status_code in (400, 403)
    loan.refresh_from_db()
    assert loan.renewal_count == 0


def test_without_member_accounts_the_switch_does_nothing():
    space, _, _, _, loan, policy, client = setup_loan("sr-noacct")
    space.enabled_modules = sorted(set(space.enabled_modules) - {"membership", "member_accounts"})
    space.save(update_fields=["enabled_modules"])
    policy.account_self_renewal = True
    policy.save()
    assert renew(client, space, loan).status_code == 404


def test_only_manage_makerspace_can_change_the_switch_and_it_is_audited():
    space, _, _, _, _, _, _ = setup_loan("sr-setting")
    inventory_manager = make_member("sr-im", space, membership_role="inventory_manager")
    with pytest.raises(PermissionDenied):
        update_loan_policy(inventory_manager, space, {"account_self_renewal": True})
    manager = make_member("sr-sm", space)
    update_loan_policy(manager, space, {"account_self_renewal": True})
    entry = AuditLog.objects.filter(action="makerspace.return_policy_updated", makerspace=space).latest("pk")
    assert entry.meta["before"]["account_self_renewal"] is False
    assert entry.meta["after"]["account_self_renewal"] is True
    # An inventory manager may still edit other lending settings without touching the switch.
    update_loan_policy(inventory_manager, space, {"loan_max_renewals": 2})
