"""G3 transport/switch proof; successful calls MUST supply a domain assertion."""
from contextlib import contextmanager

from django.db import connection
from django.core.cache import cache
from tests.modules.test_switch_matrix_objects_rest_isolation import separate_on_case
from django.urls import reverse

from apps.audit.models import AuditLog
from tests.inventory.switch_support_cx11b_p1 import snapshot
from tests.modules.switch_matrix_object_helpers import client_for, response_pair
from tests.modules.test_switch_matrix_objects_rest_isolation import rolled_back
from tests.modules.test_switch_matrix_objects_rest_support import no_domain_writes, switch
from tests.return_helpers import make_member, make_space


def person_client(actor, space, native):
    if not native:
        from tests.return_helpers import authenticated_client
        return authenticated_client(actor)
    from rest_framework.test import APIClient
    from apps.accounts.services_device_tokens import issue_device_token_pair
    from tests.accounts.account_factories import device_grant
    access, _, _ = issue_device_token_pair(actor, device_grant(actor))
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


def foreign_client(native, *, personal=False):
    space = make_space("g3-foreign")
    actor = make_member("g3-foreign-manager", space)
    return person_client(actor, space, native) if personal else client_for(actor, space, native)


def send(client, name, args, method="get", body=None):
    return getattr(client, method)(reverse(name, args=args), body or {}, format="json")


def foreign_refusal(native, *, space_path=False):
    # 494/524: native selection of a foreign object is refused in authentication;
    # 481/494 normalize makerspace-addressed STAFF paths only. Browser lookups 520.
    return (403, "permission_denied") if native else (404, "not_found")


def audit_count(space, action):
    return AuditLog.objects.filter(makerspace=space, action=action).count()


@contextmanager
def audit_delta(space, expected):
    before = {action: audit_count(space, action) for action in expected}
    yield
    assert {action: audit_count(space, action) - before[action] for action in expected} == expected


def prove(space, objects, key, call, check, *, status=200, off=(404, "not_found"), outsiders=(), audits=None,
          off_check=None, after_off=None):
    """On, off, restored command, then retained committed rows after another off/on.

    Each outsider is (client, (status, code)); its exact per-route contract is
    probed in every switch state, under the same attempted-write prohibition.
    """
    def refused(caller, expected):
        before = snapshot(objects)
        cache.clear()
        with no_domain_writes():
            response = call(caller)
        contract = expected() if callable(expected) else expected
        assert response_pair(response) == contract, getattr(response, "data", None)
        if caller is None and contract[1] in {"feature_disabled", "module_disabled"}:
            assert response.data["feature" if contract[1] == "feature_disabled" else "module"] == key
        if caller is None and off_check:
            off_check(response)
        assert snapshot(objects) == before

    def success():
        cache.clear()
        with audit_delta(space, audits or {}):
            response = call(None)
            assert response_pair(response) == (status, None), getattr(response, "data", None)
            check(response)

    before = snapshot(objects)
    if separate_on_case():
        for outsider, expected in outsiders:
            refused(outsider, expected)
        success()
        return
    if not connection.get_autocommit():
        with rolled_back():
            success()
    assert snapshot(objects) == before
    for outsider, expected in outsiders:
        refused(outsider, expected)
    original = switch(space, key)
    refused(None, off)
    for outsider, expected in outsiders:
        refused(outsider, expected)
    assert snapshot(objects) == before
    switch(space, key, original=original)
    for outsider, expected in outsiders:
        refused(outsider, expected)
    success()
    written = snapshot(objects)
    switch(space, key)
    refused(None, after_off or off)
    for outsider, expected in outsiders:
        refused(outsider, expected)
    switch(space, key, original=original)
    assert snapshot(objects) == written


def isolation(w, area, kind="repairs"):
    """An OR-gated queue is isolated to one live area, never a fictional module."""
    from apps.maintenance.repairs import areas
    keys = set(areas.REPAIRS.values()) | set(areas.REPORTING.values())
    w.space.enabled_features = sorted(set(w.space.enabled_features) - keys | {getattr(areas, kind.upper())[area]})
    w.space.save(update_fields=["enabled_features"])
