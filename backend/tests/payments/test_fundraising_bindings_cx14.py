"""R6 binding regressions overlay complete source through the real inventory."""

import ast
from pathlib import Path

import pytest

from tests.payments.fundraising_structure_cx14 import (
    PACKAGE, ROOT, call_targets, inventory, service_entries, violations,
)
from tests.payments.test_fundraising_structure_cx14 import SERVICES

pytestmark = pytest.mark.area_payments
MODULE = PACKAGE + ".services"
ENTRY = MODULE + ".new_entry"
REVIEWED = {PACKAGE + "." + name for name in SERVICES}
SINKS = [
    "Donation.objects.create", "consume_alias", "notify_alias", "_alias_sink",
    "getattr(Donation.objects, 'create')", "missing_callable", "holder.callback",
]
PRELUDE = (
    "\nfrom apps.hardware_requests.contact_verification import consume_code as consume_alias\n"
    "from apps.operations.notifications_p2 import fanout as notify_alias\n"
    "def _alias_sink(**kwargs):\n    row.save()\n"
)


@pytest.fixture
def source_overlay(monkeypatch):
    """Patch only source reads; never import or execute the planted application code."""
    path = ROOT / "services.py"
    original = Path.read_text
    source = original(path, encoding="utf-8-sig")
    assert service_entries() == REVIEWED

    def apply(addition):
        complete = source + PRELUDE + addition

        def read(candidate, *args, **kwargs):
            return complete if candidate == path else original(candidate, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", read)
        inventory.cache_clear()
        return ast.parse(complete)

    yield apply
    inventory.cache_clear()


def assert_planted_entry(tree, fenced, sink, count=1):
    functions, imports = inventory()
    discovered = service_entries(functions, imports)
    assert discovered == REVIEWED | {ENTRY}
    # Exercise the same closed-set assertion as the standing inventory guard.
    with pytest.raises(AssertionError):
        assert discovered == REVIEWED
    owner = MODULE + "._alias_sink" if sink == "_alias_sink" else ENTRY
    node = next(item for item in tree.body if isinstance(item, ast.FunctionDef)
                and item.name == owner.rsplit(".", 1)[-1])
    call = "row.save" if sink == "_alias_sink" else "write"
    line = node.body[-1].lineno
    assert violations(ENTRY, functions, imports) == ([] if fenced else [(owner, line, call)] * count)


@pytest.mark.parametrize("sink", SINKS)
@pytest.mark.parametrize("fenced", [False, True])
def test_module_bound_callables_fail_closed_inventory_and_ordering(source_overlay, sink, fenced):
    gate = "    require_fundraising_locked(space)\n" if fenced else ""
    tree = source_overlay(f"write = {sink}\ndef new_entry(space):\n" + gate
                          + "    return write(makerspace=space)\n")
    assert_planted_entry(tree, fenced, sink)


@pytest.mark.parametrize("sink", SINKS)
@pytest.mark.parametrize("signature", ["space, write={sink}", "space, write={sink}, /",
                                        "space, *, write={sink}"])
@pytest.mark.parametrize("fenced", [False, True])
def test_default_bound_callables_fail_closed_inventory_and_ordering(source_overlay, sink, signature, fenced):
    gate = "    require_fundraising_locked(space)\n" if fenced else ""
    tree = source_overlay("def new_entry(" + signature.format(sink=sink) + "):\n" + gate
                          + "    return write(makerspace=space)\n")
    assert_planted_entry(tree, fenced, sink)


@pytest.mark.parametrize("binding", [
    "write: object = Donation.objects.create",
    "alias = Donation.objects.create\nwrite = alias",
    "write = alias = Donation.objects.create",
    "write, unused = Donation.objects.create, None",
    "write, *unused = Donation.objects.create, None",
    "write = Donation.objects.create if enabled else harmless",
    "if enabled:\n    write = Donation.objects.create\nelse:\n    write = harmless",
    "if (write := Donation.objects.create):\n    pass",
    "write = alias\nalias = write",
])
@pytest.mark.parametrize("default", [False, True])
@pytest.mark.parametrize("fenced", [False, True])
def test_module_binding_forms_and_default_alias_chains_fail_closed(source_overlay, binding, default, fenced):
    signature = "space, write=write" if default else "space"
    gate = "    require_fundraising_locked(space)\n" if fenced else ""
    tree = source_overlay(binding + "\ndef new_entry(" + signature + "):\n" + gate
                          + "    return write(makerspace=space)\n")
    assert_planted_entry(tree, fenced, "Donation.objects.create", count=2 if binding.startswith("if enabled") else 1)


def test_default_alias_uses_definition_binding_before_local_rebinding(source_overlay):
    tree = source_overlay("alias = Donation.objects.create\ndef new_entry(space, write=alias):\n"
                          "    alias = harmless\n    return write(makerspace=space)\n")
    assert_planted_entry(tree, False, "Donation.objects.create")
    functions, imports = inventory()
    assert call_targets(ENTRY, "write", functions, imports) == {PACKAGE + ".models.Donation.objects.create"}


def test_module_branch_rebinding_preserves_all_callable_targets(source_overlay):
    tree = source_overlay("if enabled:\n    write = Donation.objects.create\nelse:\n"
                          "    write = Donation.objects.delete\ndef new_entry(space):\n"
                          "    return write(makerspace=space)\n")
    functions, imports = inventory()
    assert service_entries(functions, imports) == REVIEWED | {ENTRY}
    assert call_targets(ENTRY, "write", functions, imports) == {
        PACKAGE + ".models.Donation.objects.create", PACKAGE + ".models.Donation.objects.delete",
    }
    line = tree.body[-1].body[-1].lineno
    assert violations(ENTRY, functions, imports) == [(ENTRY, line, "write"), (ENTRY, line, "write")]
