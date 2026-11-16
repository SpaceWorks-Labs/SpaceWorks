"""G2 HTTP proof: exact effects, attempted-write fence and independent switches."""
from types import SimpleNamespace

from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.services_device_tokens import issue_device_token_pair
from apps.audit.models import AuditLog
from tests.accounts.account_factories import device_grant, make_staff
from tests.modules.switch_matrix_helpers import MODULE_KEYS, live_space
from tests.modules.switch_matrix_object_helpers import client_for, object_world, response_pair
from tests.modules.test_switch_matrix_objects_rest_isolation import rolled_back
from tests.modules.test_switch_matrix_objects_rest_support import domain_rows, no_domain_writes


def personal(user, space, native):
    client = APIClient()
    if native:
        token, _, _ = issue_device_token_pair(user, device_grant(user))
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}", HTTP_X_MAKERSPACE_ID=str(space.pk))
    else:
        client.force_authenticate(user)
    return client


def world(native):
    space, client, objects = object_world(native)
    actor = User.objects.get(username="sx-real-object-manager")
    other = live_space("g2-foreign", MODULE_KEYS)
    outsider = make_staff(other, username="g2-foreign-staff", access_status="active")
    foreign = client_for(outsider, other, native)
    return SimpleNamespace(space=space, client=client, actor=actor, foreign=foreign,
                           outsider=outsider, other=other, native=native, **objects)


def toggle(space, key, original=None):
    # Remove ONLY this key: leaving sibling switches on proves independence.
    field = "enabled_features" if "." in key else "enabled_modules"
    previous = list(getattr(space, field))
    setattr(space, field, original if original is not None else [item for item in previous if item != key])
    space.save(update_fields=[field])
    cache.clear()
    return previous


def command(client, name, method, args, body=None):
    cache.clear()
    return getattr(client, method)(reverse(name, args=args), {} if body is None else body, format="json")


def actions():
    return list(AuditLog.objects.order_by("pk").values_list("action", flat=True))


def prove(w, key, call, check, *, status=200, audits=(), off=(404, "module_disabled"),
          foreign=None, foreign_check=None, off_check=None, foreign_off=None, foreign_off_check=None,
          providers=()):
    """Run the SAME seeded effect before disable and after restore; retain its committed result.

    Each caller supplies a concrete response/persisted-effect check. 481/494/506/520
    require route-specific standing; public/list exceptions supply their exact contract.
    """
    if foreign is None:
        from apps.accounts.models import DeviceGrant
        from rest_framework_simplejwt.tokens import AccessToken
        bearer = w.foreign._credentials.get("HTTP_AUTHORIZATION", "")
        grant_id = AccessToken(bearer.split()[1]).get("device_grant_id") if bearer else None
        fixed_staff = grant_id is not None and DeviceGrant.objects.filter(pk=grant_id, authority="staff").exists()
        foreign = (403, "permission_denied") if fixed_staff else (404, "not_found")

    # 494 preserves native selection refusals; same-space nonowners still reach
    # the owner lookup and retain its 404 (520). Public/list probes stay explicit.
    selection = w.foreign._credentials.get("HTTP_X_MAKERSPACE_ID")
    if selection is not None and str(selection) != str(w.space.pk) and foreign[0] >= 400:
        foreign = (403, "permission_denied")
        foreign_off = foreign

    def success():
        before = actions()
        calls = [provider.call_count for provider in providers]
        response = call(w.client)
        assert response_pair(response) == (status, None), getattr(response, "data", None)
        check(response)
        assert actions()[len(before):] == list(audits)
        assert [provider.call_count for provider in providers] == [count + 1 for count in calls]

    def outsider(expected, disabled=False):
        before = domain_rows()
        calls = [provider.call_count for provider in providers]
        with no_domain_writes():
            response = call(w.foreign)
        assert response_pair(response) == expected, getattr(response, "data", None)
        inspect = foreign_off_check if disabled and foreign_off_check else foreign_check
        if inspect and response.status_code < 400:
            inspect(response)
        assert domain_rows() == before
        assert [provider.call_count for provider in providers] == calls

    with rolled_back():
        success()
    outsider(foreign)
    before = domain_rows()
    original = toggle(w.space, key)
    outsider(foreign_off or foreign, disabled=True)
    calls = [provider.call_count for provider in providers]
    with no_domain_writes():
        response = call(w.client)
    assert response_pair(response) == off, getattr(response, "data", None)
    if off[1] in {"module_disabled", "feature_disabled"}:
        assert response.data["module" if off[1] == "module_disabled" else "feature"] == key
    if off_check:
        off_check(response)
    assert domain_rows() == before
    assert [provider.call_count for provider in providers] == calls
    toggle(w.space, key, original)
    assert domain_rows() == before
    outsider(foreign)
    success()
    written = domain_rows()
    toggle(w.space, key)
    # A deleted object can now legitimately be not_found; its original off refusal
    # was proved while it existed. Never resurrect it merely to repeat that request.
    assert domain_rows() == written
    toggle(w.space, key, original)
    assert domain_rows() == written


def rows(response):
    data = response.data
    return data["results"] if isinstance(data, dict) and "results" in data else data
