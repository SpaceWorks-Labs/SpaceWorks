"""Registry validation rejects invalid declarations without patching the live catalogue."""
from dataclasses import replace

import pytest

from apps.makerspaces.module_registry_definitions import GroupDefinition, ModuleDefinition
from apps.makerspaces.module_registry_validation import ImproperlyConfiguredRegistry, validate_registry


def module(key="example", **changes):
    return ModuleDefinition(key, "Example", "Example module", "inventory", "guard", group="example", **changes)


def group(**changes):
    return GroupDefinition("example", "Examples", "Example group", **changes)


def validate(modules, groups=None):
    groups = [group()] if groups is None else groups
    return validate_registry(MODULES=modules, BY_KEY={row.key: row for row in modules},
        GROUPS=groups, GROUPS_BY_KEY={row.key: row for row in groups}, GROUP_KEYS={row.key for row in groups},
        group_module_keys=lambda key: tuple(row.key for row in modules if row.group == key))


@pytest.mark.parametrize("modules,groups,message", [
    ([module(), module()], None, "Duplicate module keys: ['example']."),
    ([module(requires_modules=("missing",))], None, "example requires unknown module(s): missing."),
    ([module(is_core=True, default_enabled=True)], None, "example is core, which already implies default_enabled."),
    ([module(is_core=True, requires_modules=("optional",)), module("optional")], None,
     "example is core but requires optional module(s): optional. A core module must work with every optional module uninstalled."),
    ([replace(module(), enforcement="mystery")], None, "example has unknown enforcement 'mystery'."),
    ([replace(module(), group="missing")], None, "example declares unknown group 'missing'. Known groups: example."),
    ([module()], [group(), group()], "Duplicate group keys."),
    ([module()], [replace(group(), label="")], "Group example needs a label and description."),
    ([module()], [replace(group(), description="")], "Group example needs a label and description."),
    ([module()], [group(), GroupDefinition("empty", "Empty", "Empty group")], "Group empty contains no modules."),
    ([module()], [group(always_on=True)], "Group example claims always_on but holds no core module."),
])
def test_invalid_registry_declarations_have_exact_failure_reasons(modules, groups, message):
    with pytest.raises(ImproperlyConfiguredRegistry) as error:
        validate(modules, groups)
    assert str(error.value) == message


@pytest.mark.parametrize("changes", [{"default_enabled": True}, {"is_core": True},
    {"requires_modules": ()}, {"app_label": "inventory"}])
def test_reimbursements_cannot_lose_their_optional_event_owned_contract(changes):
    reimbursements = ModuleDefinition("event_reimbursements", "Reimbursements", "Expense claims",
        "event_reimbursements", "guard", group="example", requires_modules=("events",))
    with pytest.raises(ImproperlyConfiguredRegistry) as error:
        validate([module("events"), replace(reimbursements, **changes)])
    assert str(error.value) == "Event reimbursements must be optional and require Events alone."


def test_valid_core_group_and_optional_dependency_chain_are_accepted():
    assert validate([module(is_core=True), module("optional", requires_modules=("example",))],
                    [group(always_on=True)]) is None
