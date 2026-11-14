"""P2 proofs share real authentication, dependency toggles and the domain SQL fence."""
from contextlib import contextmanager
from uuid import uuid4

from django.core.cache import cache
from django.db import connection

from tests.modules.switch_matrix_object_helpers import response_pair, retained
from tests.modules.test_switch_matrix_objects_rest_isolation import rolled_back
from tests.modules.test_switch_matrix_objects_rest_support import (
    _no_write, domain_rows, no_domain_writes, switch,
)


@contextmanager
def no_policy_writes():
    """Reject attempted SQL writes even if a fail-safe worker catches the exception."""
    attempted = []
    def guard(execute, sql, params, many, context):
        try:
            return _no_write(execute, sql, params, many, context)
        except AssertionError:
            attempted.append(sql[:160])
            raise
    with connection.execute_wrapper(guard):
        yield
    assert attempted == [], attempted


def route_cycle(space, client, objects, key, url, *, method="get", body=None,
                on=(200, None), off=(404, "feature_disabled"), check=None):
    def send():
        cache.clear()
        return getattr(client, method)(url, {} if body is None else body, format="json") if method != "get" else client.get(url)

    foreign = None
    foreign_pair = (403, "permission_denied") if "HTTP_AUTHORIZATION" in client._credentials else (404, "not_found")
    if url.startswith("/api/v1/admin/"):
        from tests.accounts.account_factories import make_staff
        from tests.modules.switch_matrix_helpers import MODULE_KEYS, live_space
        from tests.modules.switch_matrix_object_helpers import client_for
        suffix = uuid4().hex[:8]
        other = live_space("p2-foreign-" + suffix, MODULE_KEYS)
        actor = make_staff(other, username="p2-foreign-" + suffix, access_status="active")
        foreign = client_for(actor, other, "HTTP_AUTHORIZATION" in client._credentials)
        with no_domain_writes():
            response = getattr(foreign, method)(url, body or {}, format="json") if method != "get" else foreign.get(url)
        assert response_pair(response) == foreign_pair, getattr(response, "data", None)
    # Run the valid on-state operation in a savepoint so restoration uses the same object.
    with rolled_back():
        response = send()
        assert response_pair(response) == on, getattr(response, "data", None)
        if check:
            check(response)
    before, rows = retained(objects), domain_rows()
    original = switch(space, key)
    if foreign is not None:
        with no_domain_writes():
            hidden = getattr(foreign, method)(url, body or {}, format="json") if method != "get" else foreign.get(url)
        assert response_pair(hidden) == foreign_pair, getattr(hidden, "data", None)
    with no_domain_writes():
        response = send()
    assert response_pair(response) == off, getattr(response, "data", None)
    assert retained(objects) == before
    assert domain_rows() == rows
    switch(space, key, original=original)
    assert retained(objects) == before
    response = send()
    assert response_pair(response) == on, getattr(response, "data", None)
    if check:
        check(response)
    written = domain_rows()
    original = switch(space, key)
    with no_domain_writes():
        assert response_pair(send()) == off
    assert domain_rows() == written
    switch(space, key, original=original)
    assert domain_rows() == written
    return response


def read_policy_cycle(space, objects, key, read, expected_on, expected_off):
    """Routeless policies change a real consumer's result without changing stored data."""
    before, rows = retained(objects), domain_rows()
    with no_policy_writes():
        assert read() == expected_on
    original = switch(space, key)
    with no_policy_writes():
        assert read() == expected_off
    assert retained(objects) == before
    assert domain_rows() == rows
    switch(space, key, original=original)
    with no_policy_writes():
        assert read() == expected_on
    assert retained(objects) == before
    assert domain_rows() == rows
