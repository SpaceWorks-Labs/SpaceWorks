"""SWITCH-MATRIX 3-5: the seeded showcase world through every module switch (one seed, see the base module)."""

import pytest

from tests.modules.switch_matrix_world_base import *  # noqa: F401,F403
from tests.modules.switch_matrix_world_base import (  # noqa: F401
    APIClient, Makerspace, OPTIONAL, Payment, _ledger, _run_every_scheduled_task, diff, disable_module, install_module,
    reverse, showcase_environment, snapshot, world,
)

pytestmark = pytest.mark.django_db(transaction=True)


def test_the_showcase_world_survives_every_module_off_then_on_with_money_visible_and_tasks_safe(world):
    """ONE seed, several proofs (each proof appends to `problems`; one assertion at the end names them all)."""
    space, root = world
    problems = []
    original_modules = set(space.enabled_modules)
    original_features = sorted(space.enabled_features)
    start_rows, start_values = snapshot(), snapshot(values=True)
    ON_RUN = _run_every_scheduled_task()

    # 1. every optional module off -> no row anywhere changes; on again -> every table row-for-row identical.
    for key in OPTIONAL:
        if key not in set(space.enabled_modules):
            problems.append((key, "not installed in the showcase world"))
            continue
        removed = disable_module(space, key, actor=root)
        mid = diff(start_rows, snapshot())
        if mid:
            problems.append((key, "rows changed while off", mid))
        space.refresh_from_db()
        if key in space.enabled_modules:
            problems.append((key, "still enabled after uninstall"))
        for gone in removed:
            install_module(space, gone, actor=root)
        # Feature choices of an uninstalled module are pruned by design (capability_validation.prune_features);
        # the console's save puts the stored choice back, as here.
        Makerspace.objects.filter(pk=space.pk).update(enabled_features=original_features)
        space.refresh_from_db()
    if set(space.enabled_modules) != original_modules:
        problems.append(("modules", "set differs after off/on", original_modules ^ set(space.enabled_modules)))
    changed = diff(start_values, snapshot(values=True))
    if changed:
        problems.append(("values", "tables differ after off/on", changed))

    # 2. the ledger and the member's payment history survive every charging module being off.
    before = _ledger(space)
    owing = Payment.objects.filter(makerspace=space, member__isnull=False).select_related("member").first()
    client = APIClient(raise_request_exception=False)
    client.force_authenticate(owing.member)
    url = reverse("member-payment-history", args=[space.pk])
    on = client.get(url)
    for key in ("payments", "events", "bookings", "membership", "shop", "machine_service"):
        disable_module(space, key, actor=root)
    if _ledger(space) != before:
        problems.append(("ledger", "rows changed with charging modules off"))
    off = client.get(url)
    if on.status_code != 200:
        problems.append(("history", "on", on.status_code))
    if off.status_code == 200 and off.data != on.data:
        problems.append(("history", "payload differs with charging modules off"))
    if off.status_code not in (200, 403, 404):
        problems.append(("history", "off", off.status_code))

    # 3. every scheduled task, with every optional module off, raises no charge and fails only if it fails with them on.
    for key in reversed(OPTIONAL):
        disable_module(space, key, actor=root)
    ledger_before = _ledger(space)
    off_run = _run_every_scheduled_task()
    broke = {path: error for path, error in off_run.items() if error and not ON_RUN.get(path)}
    if broke:
        problems.append(("tasks", "fail only with modules off", broke))
    new = [row for row in _ledger(space) if row not in ledger_before]
    if new:
        problems.append(("tasks", "raised a charge with every optional module off", new))
    assert not problems, "\n" + "\n".join(map(str, problems[:15]))
