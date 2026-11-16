from types import SimpleNamespace

import pytest
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.makerspaces.origin_scope import validate_native_makerspace_scope
from apps.makerspaces.origin_scope_model_lookups import BASE_MODEL_LOOKUPS


@pytest.mark.skip(reason="#63 (U-A2 fef4372c): staff are personal accounts; no account is fixed to one tenant any more")
def test_native_staff_cannot_select_a_different_tenant_even_with_an_attested_grant():
    user = SimpleNamespace(pk=1, account_kind="staff", staff_makerspace_id=11)
    grant = SimpleNamespace(user_id=1, status="active", revoked_at=None, attested_at=timezone.now(),
                            Status=SimpleNamespace(ACTIVE="active"))
    request = SimpleNamespace(headers={"X-Makerspace-Id": "12"})
    with pytest.raises(PermissionDenied, match="fixed to the account tenant"):
        validate_native_makerspace_scope(request, user, grant)


def test_usage_candidate_scope_resolves_the_machine_owner():
    assert BASE_MODEL_LOOKUPS["admin-machine-usage-candidates"] == ("machines.Machine", "makerspace_id")
