"""SWITCH-MATRIX 3-5 (shared setup): the seeded showcase world through every switch, and purge versus off.

One rich, fictional makerspace (`seed_showcase`: requests in every state, loans, bookings, events with paid tickets,
machine jobs, membership dues, charges, notifications, report rows ...) is built through the real services, then:

* off keeps data: for every optional module, switching it off (with whatever depends on it) deletes and rewrites no
  row of any table; after it is on again every table is row-for-row identical (the state diff);
* money stays visible: the ledger rows and the member's own payment history are identical with every charging
  module off (the ledger is core);
* purge deletes exactly what the plan declares: tables that change are a subset of the plan's own labels plus the
  documented side tables; the payment ledger is never touched; purge is refused while installed, for a
  non-superuser, and for modules that store nothing.
"""

import hashlib

import pytest
from django.apps import apps as django_apps
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.makerspaces import module_purge
from apps.makerspaces.models import Makerspace
from apps.makerspaces.module_install import install_module
from apps.makerspaces.module_purge import purge_module
from apps.makerspaces.module_purge_plans import PLANS
from apps.makerspaces.module_registry import MODULE_KEYS
from apps.operations.management.commands import _showcase_data as data
from apps.payments.models import Payment
from tests.module_helpers import disable_module
from tests.modules.switch_matrix_helpers import OPTIONAL


# Rows that legitimately change when a switch flips: the audit trail grows, the tenant row holds the switches.
SWITCH_TABLES = {"audit.AuditLog", "makerspaces.Makerspace"}
VOLATILE = {"updated_at", "modified_at", "last_seen_at", "last_login"}
PLAN_KEYS = [plan.key for plan in PLANS if plan.key in MODULE_KEYS]
SIDE_TABLES = {"encryption.PiiBlindIndex", "operations.ReportMetricRollup", "operations.ReportRollupCursor",
               "tenant_migration.ExternalTenantReference"}


def _models():
    for model in django_apps.get_models():
        if model._meta.managed and not model._meta.proxy and not model._meta.swapped:
            yield model


def snapshot(*, values=False):
    out = {}
    for model in _models():
        label = model._meta.label
        if label in SWITCH_TABLES:
            continue
        rows = model._base_manager.order_by("pk")
        if values:
            fields = [f.attname for f in model._meta.concrete_fields if f.attname not in VOLATILE]
            digest = hashlib.sha1()
            for row in rows.values_list(*fields):
                digest.update(repr(row).encode())
            out[label] = (rows.count(), digest.hexdigest())
        else:
            out[label] = rows.count()
    return out


def diff(before, after):
    return {label: (before.get(label), after.get(label))
            for label in set(before) | set(after) if before.get(label) != after.get(label)}


def _ledger(space):
    return list(Payment.objects.filter(makerspace=space).order_by("pk")
                .values_list("pk", "status", "amount", "provider", "subject_type"))


@pytest.fixture(autouse=True)
def showcase_environment(settings):
    """The showcase reads the migration-seeded machine types (a transactional test flushes them) and uploads evidence."""
    from importlib import import_module

    from apps.evidence import storage

    import_module("apps.machines.migrations.0002_seed_builtin_machine_types").seed_builtins(django_apps, None)
    import_module("apps.machines.migrations.0017_seed_machine_type_metering_packs").forward(django_apps, None)
    try:
        storage._client().create_bucket(Bucket=settings.AWS_STORAGE_BUCKET_NAME)
    except Exception:  # noqa: BLE001 - already there
        pass


@pytest.fixture
def world(settings):
    settings.DEBUG = True
    call_command("seed_showcase", password="pw-switch-matrix-1")
    return Makerspace.objects.get(slug=data.SLUG), User.objects.filter(is_superuser=True).first()


# --- scheduled work ---------------------------------------------------------------------------------------------


def _run_every_scheduled_task():
    """{path: error-or-None}: each scheduled task run once, inline, in the current tenant state."""
    import importlib

    from apps.operations.cloud_jobs.task_sources import TASK_SOURCES

    outcome = {}
    for path in sorted(TASK_SOURCES):
        module, _, name = path.rpartition(".")
        task = getattr(importlib.import_module(module), name)
        try:
            if hasattr(task, "apply"):
                task.apply(throw=True)
            else:
                task()
            outcome[path] = None
        except Exception as exc:  # noqa: BLE001 - the point is to see every failure
            outcome[path] = f"{type(exc).__name__}: {exc}"[:200]
    return outcome


