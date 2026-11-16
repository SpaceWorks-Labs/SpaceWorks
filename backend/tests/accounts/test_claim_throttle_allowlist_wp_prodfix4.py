"""The four reviewed custom throttle surfaces remain exact and fail closed."""
import pytest
from django.utils.module_loading import import_string
from rest_framework.views import APIView

from apps.accounts.claim_pre_auth_allowlists import POLICY_OVERRIDE_ALLOWLIST
from apps.accounts.claim_pre_auth_guard import _custom_policy_methods, _validate_policies

pytestmark = pytest.mark.area_auth


@pytest.mark.parametrize("path", [
    "apps.apiclients.throttling.ClientTierRateThrottle",
    "apps.apiclients.throttling.MemberPrincipalRateThrottle",
    "apps.events.throttles.CollaborativeRegistrationThrottle",
    "apps.events.throttles.PublicFeedbackRateThrottle",
])
def test_reviewed_throttle_methods_are_exact_and_an_additional_hook_still_fails(path, monkeypatch):
    policy = import_string(path)
    expected = {"_apply_space_limit", "_tier", "allow_request", "get_cache_key", "_consume_slot", "wait"}
    assert _custom_policy_methods(policy) == POLICY_OVERRIDE_ALLOWLIST[path] == expected

    class ClaimView(APIView):
        authentication_classes = []
        permission_classes = []
        throttle_classes = [policy]

    assert _validate_policies("reviewed-claim", ClaimView) == []
    monkeypatch.setattr(policy, "unexpected_hook", lambda self: True, raising=False)
    assert _validate_policies("reviewed-claim", ClaimView) == [
        "reviewed-claim has unrecognised policy overrides on " + path + ": " + str(sorted(expected | {"unexpected_hook"}))
    ]
