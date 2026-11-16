"""P1 switch proofs: real transports, forbidden SQL, and retained seeded rows."""
from django.core.cache import cache
from tests.modules.test_switch_matrix_objects_rest_isolation import separate_on_case
from django.apps import apps
from django.db import connection

from apps.audit.models import AuditLog
from tests.modules.switch_matrix_object_helpers import response_pair, retained
from tests.modules.test_switch_matrix_objects_rest_isolation import rolled_back
from tests.modules.test_switch_matrix_objects_rest_support import no_domain_writes, switch


def snapshot(objects):
    labels = {row._meta.app_label for row in objects.values()} | {
        "audit", "payments", "hardware_requests", "maintenance", "integrations"}
    statements, quote = [], connection.ops.quote_name
    for model in apps.get_models():
        # A valid signed request must claim its real authentication nonce before
        # entering the domain guard, including when the handler then refuses.
        # The Makerspace row is the deliberately changed switch configuration.
        # Counts-only transport activity runs before the domain fence (494/524).
        # Grants remain hashed below, except their documented request heartbeat.
        if model._meta.label in {"devices.DeviceRequestNonce", "makerspaces.Makerspace",
                "accounts.DeviceActivityDay", "accounts.WebSessionActivityDay", "accounts.ChannelUsageDay"}:
            continue
        if model._meta.app_label not in labels or not model._meta.managed or model._meta.proxy or model._meta.swapped:
            continue
        row_json = "(to_jsonb(t) - 'last_used_at')" if model._meta.label == "accounts.DeviceGrant" else "to_jsonb(t)"
        statements.append(f"SELECT '{model._meta.label}', count(*), "
            f"md5(COALESCE(string_agg({row_json}::text, '' ORDER BY t.{quote(model._meta.pk.column)}), '')) "
            f"FROM {quote(model._meta.db_table)} t")
    result = {}
    with connection.cursor() as cursor:
        for start in range(0, len(statements), 128):
            cursor.execute(" UNION ALL ".join(statements[start:start + 128]))
            result.update({row[0]: (row[1], row[2]) for row in cursor.fetchall()})
    return result


def prove_route(space, client, objects, key, call, *, off=(404, "feature_disabled"), on=(200, None),
                check=None, named_switch=True, refusal_key=None, outsiders=()):
    """Keep a successful command, then prove its rows survive a second off/on cycle."""
    def standing():
        before = snapshot(objects)
        for outsider, pair in outsiders:
            with no_domain_writes():
                response = call(outsider)
            assert response_pair(response) == pair, getattr(response, "data", None)
            assert snapshot(objects) == before

    standing()
    if separate_on_case():
        response = call(client)
        assert response_pair(response) == on, getattr(response, "data", None)
        if check:
            check(response)
        return
    if not connection.get_autocommit():
        with rolled_back():
            response = call(client)
            assert response_pair(response) == on, getattr(response, "data", None)
            if check:
                check(response)
    before, audits, rows = retained(objects), AuditLog.objects.count(), snapshot(objects)
    original = switch(space, key)
    standing()
    with no_domain_writes():
        response = call(client)
    assert response_pair(response) == off, getattr(response, "data", None)
    if named_switch and off[1] in {"feature_disabled", "module_disabled"}:
        assert response.data["feature" if off[1] == "feature_disabled" else "module"] == (refusal_key or key)
    assert retained(objects) == before
    assert AuditLog.objects.count() == audits
    assert snapshot(objects) == rows
    switch(space, key, original=original)
    assert retained(objects) == before
    standing()
    response = call(client)
    assert response_pair(response) == on, getattr(response, "data", None)
    if check:
        check(response)
    committed, audits, rows = retained(objects), AuditLog.objects.count(), snapshot(objects)
    switch(space, key)
    with no_domain_writes():
        response = call(client)
    assert response_pair(response) == off, getattr(response, "data", None)
    switch(space, key, original=original)
    standing()
    assert retained(objects) == committed
    assert AuditLog.objects.count() == audits
    assert snapshot(objects) == rows
    cache.clear()


def staff_outsiders(native):
    from tests.payments.route_support_cx11b_g5 import foreign_client
    return [(foreign_client(native), (403, "permission_denied") if native else (404, "not_found"))]
