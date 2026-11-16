"""G4: effect assertions, real MFA transports and three-state standing probes."""
from django.apps import apps
from django.core.cache import cache
from django.db import connection

from apps.audit.models import AuditLog
from tests.accounts.account_factories import make_staff
from tests.modules.switch_matrix_helpers import MODULE_KEYS, live_space
from tests.modules.switch_matrix_object_helpers import client_for, response_pair
from tests.modules.test_switch_matrix_objects_rest_isolation import rolled_back, separate_on_case
from tests.modules.test_switch_matrix_objects_rest_support import no_domain_writes, switch


def outsider(native):
    space = live_space("g4-foreign", MODULE_KEYS)
    actor = make_staff(space, username="g4-foreign-manager", access_status="active")
    return client_for(actor, space, native)


def snapshot():
    """Raw domain rows, including children/audits; exclude transport bookkeeping."""
    labels = {"operations", "inventory", "hardware_requests", "payments", "audit", "boxes",
              "evidence", "organizations", "procurement", "makerspaces", "bookings", "machines", "events", "maintenance", "integrations", "shop"}
    statements, result = [], {}
    quote = connection.ops.quote_name
    for model in apps.get_models():
        if model._meta.app_label not in labels and model._meta.label not in {
                "accounts.StaffInvitation", "accounts.EmailVerificationChallenge", "accounts.StaffMfaGrace"}:
            continue
        if not model._meta.managed or model._meta.proxy or model._meta.swapped:
            continue
        row_json = ("(to_jsonb(t) - 'enabled_modules' - 'enabled_features')"
                    if model._meta.label == "makerspaces.Makerspace" else "to_jsonb(t)")
        statements.append(f"SELECT '{model._meta.label}', count(*), "
            f"md5(COALESCE(string_agg({row_json}::text, '' ORDER BY t.{quote(model._meta.pk.column)}), '')) "
            f"FROM {quote(model._meta.db_table)} t")
    with connection.cursor() as cursor:
        for start in range(0, len(statements), 128):
            cursor.execute(" UNION ALL ".join(statements[start:start + 128]))
            result.update({row[0]: (row[1], row[2]) for row in cursor.fetchall()})
    return result


def send(client, method, url, body=None):
    cache.clear()
    return getattr(client, method.lower())(url, body or {}, format="json")


def cycle(space, key, call, check, *, on=(200, None), off=(404, "module_disabled"),
          foreign=None, foreign_pair=(404, "not_found"), audit=(), refusal_key=None, off_check=None,
          named_switch=True, foreign_native=False, extra_probes=()):
    """One independent switch per case; both successful calls must prove their effect.

    Browser staff makerspace paths use 481/494; scoped object paths use 520.
    Native foreign fixed-tenant grants keep authentication's 403 (494/524).
    Public/personal callers pass their own decided standing contract explicitly.
    """
    def success():
        baseline = AuditLog.objects.count()
        response = call()
        assert response_pair(response) == on, getattr(response, "data", None)
        check(response)
        assert list(AuditLog.objects.order_by("pk").values_list("action", flat=True)[baseline:]) == list(audit)
        return response

    def concealed(disabled=False):
        expected = ((403, "permission_denied") if foreign_native else
                    foreign_pair(disabled) if callable(foreign_pair) else foreign_pair)
        probes = ([(foreign, expected)] if foreign is not None else []) + list(extra_probes)
        for probe, expected in probes:
            before = snapshot()
            with no_domain_writes():
                response = probe()
            assert response_pair(response) == expected, getattr(response, "data", None)
            assert snapshot() == before

    concealed()
    if connection.get_autocommit():
        if separate_on_case():
            return success()
    else:
        with rolled_back():
            success()
    before = snapshot()
    original = switch(space, key) if key else None
    concealed(disabled=bool(key))
    if key:
        with no_domain_writes():
            response = call()
        assert response_pair(response) == off, getattr(response, "data", None)
        if off_check:
            off_check(response)
        if named_switch and off[1] in {"module_disabled", "feature_disabled"}:
            assert response.data["module" if off[1] == "module_disabled" else "feature"] == (refusal_key or key)
        assert snapshot() == before
        switch(space, key, original=original)
    assert snapshot() == before
    concealed()
    response = success()
    written = snapshot()
    if key:
        switch(space, key)
        assert snapshot() == written
        switch(space, key, original=original)
        assert snapshot() == written
    return response


def cleanup_cycle(space, key, call, check, *, on, foreign, audit):
    """537: only the three decided cleanup commands may change data while off."""
    from contextlib import nullcontext
    from django.test import TestCase

    def messages():
        result, quote = {}, connection.ops.quote_name
        with connection.cursor() as cursor:
            for model in apps.get_models():
                if (model._meta.app_label not in {"integrations", "notifications"}
                        or not model._meta.managed or model._meta.proxy or model._meta.swapped):
                    continue
                cursor.execute("SELECT count(*), md5(COALESCE(string_agg(to_jsonb(t)::text, '' ORDER BY t."
                    + quote(model._meta.pk.column) + "), '')) FROM " + quote(model._meta.db_table) + " t")
                result[model._meta.label] = cursor.fetchone()
        return result

    for phase in ("on", "off", "restored"):
        original = switch(space, key) if phase == "off" else None
        before = snapshot()
        for probe, expected in foreign:
            with no_domain_writes():
                response = probe()
            assert response_pair(response) == expected, getattr(response, "data", None)
            assert snapshot() == before
        with rolled_back() if phase != "restored" else nullcontext():
            baseline, queued = AuditLog.objects.count(), messages()
            with TestCase.captureOnCommitCallbacks(execute=True):
                response = call()
                assert response_pair(response) == on, getattr(response, "data", None)
                check(response)
            assert list(AuditLog.objects.order_by("pk").values_list("action", flat=True)[baseline:]) == list(audit)
            assert messages() == queued
        if phase != "restored":
            assert snapshot() == before
        if phase == "off":
            switch(space, key, original=original)


def rows(response):
    return response.data["results"] if isinstance(response.data, dict) else response.data


def contains(response, pk):
    assert [row["id"] for row in rows(response)] == [pk]
