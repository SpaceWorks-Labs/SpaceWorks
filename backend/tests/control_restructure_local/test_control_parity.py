"""#190: every /control/ write has a web superadmin console path, or is host-only by design.

The required keys are derived from the LIVE admin, so a new admin model, action or page
without a parity row fails here, and so does a row for something /control/ no longer has.
"""

from pathlib import Path

import pytest
from django.contrib import admin
from django.test import RequestFactory
from django.urls import get_resolver

from config.control_parity import KEYS_PAGE_OPERATIONS, PARITY
from tests.r2_superadmin_local.helpers import superadmin

pytestmark = pytest.mark.django_db
STANDARD_SUFFIXES = ("_changelist", "_add", "_history", "_delete", "_change")
SIDEBAR_PAGES = {"view:control-storage", "view:control-rls"}
HOST_ONLY_THEMES = ("credentials", "key rotation", "backup_keys", "restore", "recovery command", "raw record repair",
                    "rls_sync", "set once", "typed back", "manage.py")


def required_keys():
    request = RequestFactory().get("/control/")
    request.user = superadmin("parity-root")
    keys = set(SIDEBAR_PAGES) | {f"keys:{operation}" for operation in KEYS_PAGE_OPERATIONS}
    for model, model_admin in admin.site._registry.items():
        label = model._meta.label_lower
        if (model_admin.has_add_permission(request) or model_admin.has_change_permission(request)
                or model_admin.has_delete_permission(request)):
            keys.add(label)
        keys |= {f"{label}.{name}" for name in model_admin.get_actions(request) if name != "delete_selected"}
        keys |= {f"view:{pattern.name}" for pattern in model_admin.get_urls()
                 if pattern.name and not pattern.name.endswith(STANDARD_SUFFIXES)}
    return keys


def _shipped(key):
    """False for a row whose model belongs to an app this deployment tombstoned."""
    models = {model._meta.label_lower for model in admin.site._registry}
    if key.startswith("keys:") or key in SIDEBAR_PAGES:
        return True
    if key.startswith("view:"):
        name = key.removeprefix("view:")
        return any(name.startswith(label.replace(".", "_") + "_") for label in models)
    return ".".join(key.split(".")[:2]) in models


def test_every_control_write_has_a_parity_row():
    missing = required_keys() - set(PARITY)
    assert missing == set(), "add a row to config/control_parity_entries*.py: " + ", ".join(sorted(missing))


def test_no_parity_row_outlives_what_it_maps():
    required = required_keys()
    assert {key for key in PARITY if key not in required and _shipped(key)} == set()


def route_names(resolver=None, prefix=""):
    """Every URL name, namespaced ones as `namespace:name`."""
    resolver = resolver or get_resolver()
    names = {prefix + name for name in resolver.reverse_dict if isinstance(name, str)}
    for namespace, (_pattern, sub) in resolver.namespace_dict.items():
        names |= route_names(sub, f"{prefix}{namespace}:")
    return names


def test_every_web_row_names_real_console_routes():
    names = route_names()
    required = required_keys()
    for key, row in PARITY.items():
        assert row.kind in {"web", "host"}, key
        assert row.where, key
        if row.kind == "web" and key in required:
            assert row.routes, key
            assert set(row.routes) <= names, (key, set(row.routes) - names)


def test_host_only_rows_are_the_decided_kinds_and_say_where_to_run():
    for key, row in PARITY.items():
        if row.kind == "host":
            assert not row.routes, key
            assert any(theme in row.where.lower() for theme in HOST_ONLY_THEMES), (key, row.where)


def test_the_keys_page_operations_are_the_ones_its_form_posts():
    source = (Path(__file__).resolve().parents[2] / "apps/backup/admin_keys.py").read_text(encoding="utf-8")
    for operation in KEYS_PAGE_OPERATIONS:
        assert f'"{operation}"' in source, operation


def test_platform_key_rotation_and_raw_repair_stay_on_the_server():
    assert PARITY["keys:rotate_platform"].kind == "host"
    assert PARITY["axes.accesslog"].kind == "host"
    for key in ("accounts.ipaccessrule", "accounts.ipautoblock.unblock_selected", "accounts.user.disable_account",
                "accounts.user.reset_two_step", "tenant_migration.selfhostmoverequest.approve_moves",
                "view:tenant_migration_selfhostmoverequest_run", "keys:settings"):
        assert PARITY[key].kind == "web", key
