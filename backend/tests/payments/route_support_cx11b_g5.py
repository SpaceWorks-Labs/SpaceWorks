"""G5 HTTP proofs: real authentication, exact results, attempted-write fences."""
from types import SimpleNamespace
from contextlib import contextmanager
from unittest.mock import patch

from django.db import connection
from django.core.cache import cache
from tests.modules.test_switch_matrix_objects_rest_isolation import separate_on_case

from apps.audit.models import AuditLog
from tests.accounts.account_factories import make_staff
from tests.modules.switch_matrix_helpers import MODULE_KEYS, live_space
from tests.modules.switch_matrix_object_helpers import client_for, response_pair
from tests.modules.test_switch_matrix_objects_rest_isolation import rolled_back
from tests.modules.test_switch_matrix_objects_rest_support import domain_rows, no_domain_writes as _no_domain_writes, switch


@contextmanager
def no_domain_writes():
    from tests.modules.test_switch_matrix_objects_rest_support import _no_write
    attempts = []
    def detected(execute, sql, params, many, context):
        try:
            return _no_write(execute, sql, params, many, context)
        except AssertionError:
            attempts.append(sql[:160])
            raise
    # Also fail when an adapter catches AssertionError and returns its usual typed 503.
    with patch("tests.modules.test_switch_matrix_objects_rest_support._no_write", detected), _no_domain_writes():
        yield
    assert attempts == [], attempts


def foreign_client(native, *, reauth=False, browser_token=False):
    from uuid import uuid4
    from tests.accounts.test_reauthentication import PASSWORD
    from tests.modules.test_switch_matrix_objects_rest_additional_support import reauthenticate
    suffix = uuid4().hex[:10]
    space = live_space("g5-foreign-" + suffix, MODULE_KEYS)
    actor = make_staff(space, username="g5-foreign-" + suffix, password=PASSWORD)
    client = client_for(actor, space, native)
    if native and reauth:
        reauthenticate(client, actor, password=PASSWORD)
    if not native and browser_token:
        from rest_framework.test import APIClient
        from apps.accounts.tokens import SpaceWorksRefreshToken
        access = str(SpaceWorksRefreshToken.for_user(actor).access_token)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


def personal_client(actor, space, native):
    """Native member grants keep the selected membership, needed by the payment sheet."""
    if not native:
        return client_for(actor, space, False)
    from rest_framework.test import APIClient
    from apps.accounts.services_device_tokens import issue_device_token_pair
    from tests.accounts.account_factories import device_grant
    grant = device_grant(actor)
    access, _refresh, _family = issue_device_token_pair(actor, grant)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}", HTTP_X_MAKERSPACE_ID=str(space.pk))
    return client


def send(w, client=None):
    cache.clear()
    headers = {"HTTP_IDEMPOTENCY_KEY": str(w.body["operation_id"])} if "operation_id" in w.body else {}
    caller = client or w.client
    if callable(caller):
        return caller(w)
    if w.method == "GET":
        return caller.get(w.url, **headers)
    return getattr(caller, w.method.lower())(w.url, w.body, format="json", **headers)


def audits():
    return list(AuditLog.objects.order_by("pk").values_list("action", flat=True))


def success(w):
    before = audits()
    if w.method == "GET" and getattr(w, "read_only", True):
        with no_domain_writes():
            response = send(w)
    else:
        response = send(w)
    assert response_pair(response) == w.on, getattr(response, "data", None)
    w.check(response)
    delta = audits()[len(before):]
    if w.audit_prefix:
        delta = [action for action in delta if action.startswith(w.audit_prefix)]
    assert delta == list(w.audit), "Exact owning-operation audit delta"
    return response


def probe(w):
    for caller, expected, check in w.probes:
        before = domain_rows()
        with no_domain_writes():
            response = send(w, caller)
        expected = expected(w.disabled) if callable(expected) else expected
        assert response_pair(response) == expected, getattr(response, "data", None)
        check(response)
        assert domain_rows() == before


def cycle(w, key, off=None):
    """A neutral policy uses off=None: the core operation must still work while off."""
    w.disabled = False
    probe(w)
    if separate_on_case():
        success(w)
        return
    if not connection.get_autocommit():
        with rolled_back():
            success(w)
    before = domain_rows()
    original = switch(w.space, key)
    w.disabled = True
    probe(w)
    if off is None:
        with rolled_back():
            success(w)
    else:
        with no_domain_writes():
            response = send(w)
        assert response_pair(response) == off, getattr(response, "data", None)
        if hasattr(w, "off_check"):
            w.off_check(response)
    assert domain_rows() == before, "Switch/refusal must retain every domain row and audit"
    switch(w.space, key, original=original)
    w.disabled = False
    assert domain_rows() == before
    probe(w)
    success(w)
    written = domain_rows()
    switch(w.space, key)
    if off is not None and "operation_id" in w.body:
        # 517/520: a committed idempotency receipt is never a bypass while off.
        with no_domain_writes():
            replay = send(w)
        assert response_pair(replay) == off, getattr(replay, "data", None)
    assert domain_rows() == written, "The successful operation's children survive disabling"
    switch(w.space, key, original=original)
    assert domain_rows() == written, "The successful operation's children survive restoration"


def world(space, client, url, method="GET", body=None, on=(200, None), audit=(), check=None, probes=(), audit_prefix=None):
    assert check is not None, "Every operation needs a named, operation-specific result assertion"
    return SimpleNamespace(space=space, client=client, url=url, method=method, body=body or {},
                           on=on, audit=audit, check=check, probes=probes, audit_prefix=audit_prefix)


def hidden(client, expected=None):
    # 494/524 keep the real native tenant-selection refusal. Browser scoped lookups
    # use 481/520 concealment; this is not a blanket conversion of all refusals.
    if expected is None:
        expected = (403, "permission_denied") if "HTTP_AUTHORIZATION" in client._credentials else (404, "not_found")
    return client, expected, lambda response: None


def ids(response):
    data = response.data
    return [row["id"] for row in (data["results"] if isinstance(data, dict) else data)]
