"""SWITCH-MATRIX 4: purge versus off on the seeded showcase world (one seed, see the base module)."""

import pytest
from django.core.exceptions import ValidationError

from tests.modules.switch_matrix_world_base import (  # noqa: F401
    Makerspace, OPTIONAL, PLAN_KEYS, SIDE_TABLES, User, _ledger, diff, disable_module, module_purge, purge_module,
    showcase_environment, snapshot, world,
)

pytestmark = pytest.mark.django_db(transaction=True)


def test_purge_deletes_exactly_what_each_plan_declares_and_is_refused_in_every_other_case(world, monkeypatch):
    """ONE seed: refusals first (everything still installed), then each plan's purge, diffed table by table."""
    space, root = world
    problems = []

    # refused while the module is installed: nothing changes.
    before = snapshot()
    for key in PLAN_KEYS:
        try:
            purge_module(space, key, root)
            problems.append((key, "purged while installed"))
        except ValidationError:
            pass
    if diff(before, snapshot()):
        problems.append(("installed-refusals", "rows changed", diff(before, snapshot())))

    # refused for anyone but a superuser.
    other = User.objects.filter(is_superuser=False, is_active=True).first()
    disable_module(space, PLAN_KEYS[0], actor=root)
    try:
        purge_module(Makerspace.objects.get(pk=space.pk), PLAN_KEYS[0], other)
        problems.append((PLAN_KEYS[0], "purged by a non-superuser"))
    except ValidationError:
        pass

    # a module with no plan says why it cannot be purged.
    for key in sorted(set(OPTIONAL) - set(PLAN_KEYS)):
        disable_module(space, key, actor=root)
        try:
            purge_module(Makerspace.objects.get(pk=space.pk), key, root)
            problems.append((key, "has no plan yet purged"))
        except ValidationError as exc:
            if "nothing to purge" not in str(exc) and "cannot be purged on its own" not in str(exc):
                problems.append((key, "refused without saying why", str(exc)[:80]))

    # each plan deletes only what it declares (plus the documented side tables); the ledger is never touched.
    seen = {}
    real = module_purge._delete_external_references

    def capture(makerspace, labels):
        seen["labels"] = set(labels)
        return real(makerspace, labels)

    monkeypatch.setattr(module_purge, "_delete_external_references", capture)
    ledger = _ledger(space)
    purged = 0
    for key in PLAN_KEYS:
        disable_module(space, key, actor=root)
        snap = snapshot()
        seen.clear()
        try:
            purge_module(Makerspace.objects.get(pk=space.pk), key, root)
        except ValidationError as exc:
            problems.append((key, "blocked", str(exc)[:100]))
            continue
        purged += 1
        undeclared = {label: v for label, v in diff(snap, snapshot()).items()
                      if label not in seen.get("labels", set()) | SIDE_TABLES}
        if undeclared:
            problems.append((key, "changed tables its plan does not declare", undeclared))
    if _ledger(space) != ledger:
        problems.append(("ledger", "purge changed the payment ledger"))
    if not purged:
        problems.append(("purge", "no plan purged anything"))
    assert not problems, "\n" + "\n".join(map(str, problems[:15]))
