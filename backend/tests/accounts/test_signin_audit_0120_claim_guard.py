"""REDIS-AUTH-AUDIT (decision 339b): redeeming a member claim code is a sign-in door.

It mints a member session, so the platform IP deny rules and automatic blocks (S-C) apply to
it like every other sign-in route; before 0.12.0 only its per-address throttle did.
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts.ip_guard_middleware import guarded
from apps.accounts.models import IPAccessRule, User
from apps.accounts.views_claim import ClaimRedemptionView

pytestmark = pytest.mark.django_db
REDEEM = "/api/v1/auth/claim/redeem"


def test_claim_redemption_is_a_guarded_sign_in_route():
    assert guarded(ClaimRedemptionView.as_view(), "auth-claim-redeem")


def test_a_deny_rule_refuses_claim_redemption_before_the_code_is_read():
    root = User.objects.create_user(username="claim-guard-root", password="Root password 77!",
                                    account_kind="platform", role=User.Role.SUPERADMIN, is_superuser=True,
                                    is_staff=True)
    IPAccessRule.objects.create(cidr="203.0.113.0/24", action="deny", created_by=root)
    body = {"makerspace_slug": "no-such-space", "code": "AAAA-BBBB-CCCC"}
    refused = APIClient().post(REDEEM, body, format="json", REMOTE_ADDR="203.0.113.9")
    assert refused.status_code == 429 and refused.json()["code"] == "ip_blocked"
    elsewhere = APIClient().post(REDEEM, body, format="json", REMOTE_ADDR="198.51.100.9")
    assert elsewhere.status_code != 429
