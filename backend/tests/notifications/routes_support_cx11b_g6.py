"""G6: real transports, exact effects, retained rows and attempted-write fences."""
from uuid import uuid4

from django.apps import apps
from django.core.cache import cache
from django.db import connection

from apps.audit.models import AuditLog
from tests.accounts.account_factories import make_staff
from tests.modules.switch_matrix_helpers import MODULE_KEYS, live_space
from tests.modules.switch_matrix_object_helpers import client_for, response_pair
from tests.modules.test_switch_matrix_objects_rest_isolation import rolled_back
from tests.modules.test_switch_matrix_objects_rest_support import no_domain_writes, switch
from tests.notifications.test_object_switches_cx11b_p2 import personal_client
from tests.payments.account_helpers import make_payer


def world(native, *, staff=False):
    suffix = uuid4().hex[:10]
    space = live_space("g6-" + suffix, MODULE_KEYS)
    other = live_space("g6-other-" + suffix, MODULE_KEYS)
    factory = make_staff if staff else make_payer
    actor = factory(space, username="g6-owner-" + suffix, access_status="active") if staff else factory(
        "g6-owner-" + suffix, space)
    outsider = make_staff(other, username="g6-foreign-" + suffix, access_status="active") if staff else factory(
        "g6-foreign-" + suffix, other)
    transport = client_for if staff else personal_client
    return space, actor, transport(actor, space, native), outsider, transport(outsider, other, native)


def snapshot():
    # Hash every column and every child, including connected sources and outbox rows.
    # The tenant switch row itself changes intentionally; authentication accounting
    # stays outside the domain fence. Batched reads keep these route shards small.
    labels = {"notifications", "presence", "audit", "integrations", "bookings", "events",
              "machines", "payments", "makerspaces"}
    quote, statements, result = connection.ops.quote_name, [], {}
    for model in apps.get_models(include_auto_created=True):
        if (model._meta.app_label not in labels or not model._meta.managed or model._meta.proxy
                or model._meta.swapped or model._meta.label == "makerspaces.Makerspace"):
            continue
        statements.append(f"SELECT '{model._meta.label}', count(*), "
            f"md5(COALESCE(string_agg(to_jsonb(t)::text, '' ORDER BY t.{quote(model._meta.pk.column)}), '')) "
            f"FROM {quote(model._meta.db_table)} t")
    with connection.cursor() as cursor:
        for start in range(0, len(statements), 128):
            cursor.execute(" UNION ALL ".join(statements[start:start + 128]))
            result.update({row[0]: (row[1], row[2]) for row in cursor.fetchall()})
    return result


def send(client, method, url, body=None):
    return getattr(client, method)(url, body or {}, format="json")


def cycle(space, key, call, check, *, on=(200, None), off=(404, "not_found"),
          probes=(), actions=(), prepare=None, off_check=None, off_mutates=False):
    """A saved-on command is checked twice; refusal forbids attempts, not only commits.

    Probes are (call, on_pair, off_pair) under the route's decided standing contract.
    Successful public/owner-only fallbacks may supply off_check instead of a refusal.
    """
    def request():
        cache.clear()
        if prepare:
            prepare()
        return call()

    def success():
        before = list(AuditLog.objects.order_by("pk").values_list("pk", flat=True))
        response = request()
        assert response_pair(response) == on, getattr(response, "data", None)
        check(response)
        assert list(AuditLog.objects.exclude(pk__in=before).order_by("pk").values_list(
            "action", flat=True)) == list(actions)

    def outsiders(disabled):
        for probe, allowed, refused in probes:
            cache.clear()
            before = snapshot()
            with no_domain_writes():
                response = probe()
            assert response_pair(response) == (refused if disabled else allowed), getattr(response, "data", None)
            assert snapshot() == before

    with rolled_back():
        success()
    outsiders(False)
    before = snapshot()
    original = switch(space, key)
    outsiders(True)
    if off_mutates:
        # Decided retirement/registration paths remain writable while a display switch is off.
        with rolled_back():
            audits = list(AuditLog.objects.values_list("pk", flat=True))
            response = request()
            assert response_pair(response) == off, getattr(response, "data", None)
            off_check(response)
            assert list(AuditLog.objects.exclude(pk__in=audits).order_by("pk").values_list(
                "action", flat=True)) == list(actions)
    else:
        with no_domain_writes():
            response = request()
        assert response_pair(response) == off, getattr(response, "data", None)
        if off_check:
            off_check(response)
    assert snapshot() == before
    switch(space, key, original=original)
    assert snapshot() == before
    outsiders(False)
    success()
    written = snapshot()
    original = switch(space, key)
    # Terminal operations have already changed their object. Retention is still exact.
    assert snapshot() == written
    switch(space, key, original=original)
    assert snapshot() == written


def hidden(call, *, native_staff=False):
    # 494 preserves cross-tenant native selection refusals for member and staff
    # grants; 481/520 conceal browser lookups and same-tenant owner rows.
    pair = (403, "permission_denied") if native_staff else (404, "not_found")
    return call, pair, pair
