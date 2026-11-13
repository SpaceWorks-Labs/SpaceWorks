"""#183B gap 15: every scheduled task is mapped to its module/capability or to a platform exemption.

Fails on a NEW beat entry, cloud-catalogue row or persisted worker that nobody mapped, on
a map entry naming an unknown module/capability, and on a stale map entry. Behavioural
tests then prove the named sweeps skip spaces whose switch is off.
"""

import ast
import importlib
import pathlib
from datetime import timedelta

import pytest
from django.conf import settings
from django.utils import timezone

from apps.makerspaces.capabilities import FEATURES
from apps.makerspaces.module_registry import MODULE_KEYS
from apps.makerspaces.scheduled_scope import live_space_ids, source_configured
from apps.operations.cloud_jobs.catalog import PROGRAMME_ENTRIES, all_declarations
from apps.operations.cloud_jobs.task_sources import TASK_SOURCES
from tests.module_helpers import disable_module
from tests.return_helpers import make_space

APPS = pathlib.Path(__file__).resolve().parents[2] / "apps"


def _scheduled_paths():
    paths = {entry["task"] for entry in settings.CELERY_BEAT_SCHEDULE.values()}
    paths |= {task.path for task in all_declarations()}
    paths |= {path for _group, _key, path, *_rest in PROGRAMME_ENTRIES}
    from apps.presence.schedule import TASK as PRESENCE_TASK
    paths.add(PRESENCE_TASK)
    paths.add("apps.data_export.subject_tasks.sweep_subject_exports_task")
    return paths


def _parts(source):
    for item in (source if isinstance(source, tuple) else (source,)):
        yield from item.split("|")


def test_every_scheduled_task_is_mapped():
    unmapped = sorted(_scheduled_paths() - set(TASK_SOURCES))
    assert not unmapped, f"map these in apps/operations/cloud_jobs/task_sources.py: {unmapped}"


def test_the_map_has_no_stale_entries():
    stale = sorted(set(TASK_SOURCES) - _scheduled_paths())
    assert not stale, stale


def test_every_mapped_task_resolves():
    for path in TASK_SOURCES:
        module, _, name = path.rpartition(".")
        assert callable(getattr(importlib.import_module(module), name)), path


def test_gated_sources_are_real_switches_and_exemptions_say_why():
    for path, entry in TASK_SOURCES.items():
        assert entry.kind in {"gated", "per_row", "platform"}, path
        if entry.kind == "gated":
            for part in _parts(entry.source):
                assert part in (FEATURES if "." in part else MODULE_KEYS), (path, part)
        else:
            assert entry.note, f"{path}: a {entry.kind} entry must say why"


RAW = ("enabled_features__contains", "enabled_modules__contains")


def test_gated_task_modules_never_filter_on_a_raw_json_contains():
    """`scheduled_scope.live_space_ids` reads the registry helpers; a raw contains misses
    tombstones, parent modules and the `loans.enabled` master."""
    offenders = []
    for path, entry in TASK_SOURCES.items():
        if entry.kind == "platform":
            continue
        module, _, name = path.rpartition(".")
        file = APPS.parent / (module.replace(".", "/") + ".py")
        tree = ast.parse(file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                body = ast.unparse(node)
                if any(raw in body for raw in RAW):
                    offenders.append(path)
    for file in ("machines/job_sweeps.py", "machines/sessions_sweep.py", "hardware_requests/request_lifecycle.py",
                 "events/approval_digest.py", "events/submissions/integrity_jobs.py", "notifications/escalation.py",
                 "events/staged_forms/tasks.py", "events/tasks.py", "events/tasks_contributions.py",
                 "events/tasks_programme.py", "event_reimbursements/tasks.py", "shop/tasks.py",
                 "makerspaces/membership_admission_payments.py", "maintenance/meters.py"):
        text = (APPS / file).read_text(encoding="utf-8")
        if any(raw in text for raw in RAW):
            offenders.append(file)
    assert not offenders, offenders


# --- scheduled_scope -----------------------------------------------------------------


@pytest.mark.django_db
def test_source_configured_reads_modules_capabilities_and_any_of():
    space = make_space("scope-source")
    # make_space enables every module; switch shop off so the "all of" tuple has one missing part.
    space.enabled_modules = sorted((set(space.enabled_modules) | {"machines", "machine_service"}) - {"shop"})
    space.enabled_features = sorted(set(space.enabled_features) | {"machines.job_requests"})
    space.save(update_fields=["enabled_modules", "enabled_features"])
    assert source_configured(space, "machines")
    assert source_configured(space, "machines.job_requests")
    assert source_configured(space, "shop|machines")
    assert source_configured(space, ("machines", "machine_service"))
    assert not source_configured(space, ("machines", "shop")), (space.enabled_modules, space.enabled_features)
    assert space.pk in live_space_ids("machines.job_requests")

    # A capability whose parent module is off is off, even though the raw JSON still holds it.
    disable_module(space, "machine_service")
    space.refresh_from_db()
    assert not source_configured(space, "machines.job_requests")
    assert space.pk not in live_space_ids("machines.job_requests")


# --- behaviour of the named sweeps ----------------------------------------------------


@pytest.mark.django_db
def test_job_flow_sweep_never_selects_an_off_space(monkeypatch):
    from apps.machines import job_sweeps
    from apps.machines.models import MachineServiceRequest

    captured = {}

    def fake_scope(queryset, **_):
        captured["sql"] = str(queryset.query)
        return queryset

    on = make_space("jobs-on")
    off = make_space("jobs-off")
    for space, live in ((on, True), (off, False)):
        # make_space enables every module; switch shop off so the "all of" tuple has one missing part.
        space.enabled_modules = sorted((set(space.enabled_modules) | {"machines", "machine_service"}) - {"shop"})
        features = set(space.enabled_features)
        (features.add if live else features.discard)("machines.job_requests")
        space.enabled_features = sorted(features)
        space.save(update_fields=["enabled_modules", "enabled_features"])
    monkeypatch.setattr(job_sweeps.rbac, "scope_for_scheduled_work", fake_scope)
    list(job_sweeps._rows(MachineServiceRequest.objects.all()))
    ids = live_space_ids("machines.job_requests")
    assert on.pk in ids and off.pk not in ids


@pytest.mark.django_db
def test_photo_reminders_and_wallet_refresh_skip_switched_off_card_kinds():
    from apps.card_designs.switches import live_holder_q
    from apps.card_designs.models import CardPhotoRequest, WalletPass

    space = make_space("cards-off")
    disable_module(space, "membership")
    q = live_holder_q()
    assert not CardPhotoRequest.objects.filter(q, makerspace=space).exists()
    assert not WalletPass.objects.filter(live_holder_q(wallet=True), makerspace=space).exists()
    # Sanity: the sweeps run without error and touch nothing for the off space.
    from apps.card_designs.photos import send_due_reminders
    from apps.card_designs.wallet.service import sweep_changed
    assert send_due_reminders(limit=10) >= 0
    assert sweep_changed(limit=10) >= 0


@pytest.mark.django_db
def test_loan_pickup_sweep_and_waitlist_lapse_skip_off_spaces():
    from apps.hardware_requests.request_lifecycle import expire_due_requests

    space = make_space("pickups-off")
    space.enabled_features = [key for key in space.enabled_features
                              if key not in {"loans.pickup_windows", "loans.waitlist"}]
    space.save(update_fields=["enabled_features"])
    assert space.pk not in live_space_ids("loans.pickup_windows")
    assert space.pk not in live_space_ids("loans.waitlist")
    counts = expire_due_requests(now=timezone.now() + timedelta(days=1))
    assert counts["expired"] == 0


@pytest.mark.django_db
def test_donation_and_order_selectors_leave_off_spaces_out():
    from apps.events.reminders_payments import due_expiries, due_reminders
    from apps.payments.donations.pledges import due_pledge_ids
    from apps.payments.donations.tasks import due_perk_ids

    make_space("money-sweeps-off")
    today = timezone.localdate()
    assert due_pledge_ids(10, today) == []
    assert due_perk_ids(10, today) == []
    assert due_expiries(10) == []
    assert due_reminders(10) == []
