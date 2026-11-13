from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from rest_framework.exceptions import PermissionDenied

from apps.makerspaces import resource_grants_services as lifecycle


def adapter(**overrides):
    values = dict(grant_model=object, invite_model=object, permissions=("check_in",),
                  namespace="test", audit_prefix="test", target=Mock(), lock_target=Mock(),
                  scope=Mock(), can_manage=Mock(return_value=False), can=Mock(return_value=True),
                  active=Mock(return_value=True), lock_authority=Mock(side_effect=lambda actor, target: actor))
    return lifecycle.GrantAdapter(**{**values, **overrides})


def test_existing_default_requires_full_management_even_with_permission():
    with pytest.raises(PermissionDenied):
        lifecycle._require_subset(adapter(), object(), object(), ["check_in"])
    assert lifecycle._require_subset(adapter(can_manage=lambda *a: True), "actor", object(), ["check_in"]) == "actor"


@pytest.mark.parametrize("operation", ["create_invite", "update_permissions", "revoke_grant",
                                       "revoke_invite", "redeem_invite"])
def test_opt_in_validator_receives_operation_existing_scope_and_locked_actor(operation):
    policy = Mock(return_value=True)
    hook = adapter(subset_validator=policy)
    row = SimpleNamespace(permissions=["check_in"], event_id=42)
    lifecycle._require_subset(hook, "actor", "target", ["check_in"], operation=operation, row=row)
    hook.lock_authority.assert_called_once_with("actor", "target")
    policy.assert_called_once_with(actor="actor", target="target", permissions=("check_in",), operation=operation, row=row)
    hook.can_manage.assert_not_called()


@pytest.mark.parametrize("result", [False, None, 1, "yes"])
def test_subset_hook_must_explicitly_authorize(result):
    with pytest.raises(PermissionDenied):
        lifecycle._require_subset(adapter(subset_validator=lambda **k: result), object(), object(), ())


def test_subset_hook_never_authorizes_an_inactive_or_missing_creator():
    policy = Mock(return_value=True)
    with pytest.raises(PermissionDenied):
        lifecycle._require_subset(adapter(active=lambda actor: False, subset_validator=policy),
                                  None, object(), ())
    policy.assert_not_called()


@pytest.mark.django_db
def test_issue_then_redemption_rechecks_changed_policy_without_spending_invite():
    from apps.events.services_staff_grants import ADAPTER
    from apps.events.models import EventStaffGrant
    from tests.events.staff_grant_helpers import grant_fixture

    _, manager, user, event, old_grant = grant_fixture()
    old_grant.delete()
    allowed = [True]
    seen = []

    def policy(**kwargs):
        seen.append(kwargs["operation"])
        return allowed[0]

    hook = replace(ADAPTER, subset_validator=policy)
    invite, token = lifecycle.create_invite(hook, event, actor=manager, permissions=["check_in"])
    allowed[0] = False
    with pytest.raises(PermissionDenied):
        lifecycle.redeem_invite(hook, token, actor=user)
    invite.refresh_from_db()
    assert invite.redeemed_at is None and not EventStaffGrant.objects.exists()
    assert seen == ["create_invite", "redeem_invite"]
