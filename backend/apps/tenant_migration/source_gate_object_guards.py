"""Lifecycle-exemption and object-mutation totality guards (split from `source_gate_guards`).

Re-exported from ``source_gate_guards``; import them from there.
"""

import ast

from .gate_policy import LIFECYCLE_EXEMPTIONS, OBJECT_MUTATION_PARTICIPANTS
from .source_gate_ast import (
    APPS_DIR,
    EntryPoint,
    all_functions as _all_functions,
    calls_gate as _calls_gate,
    is_object_mutation as _is_object_mutation,
    is_storage_primitive as _is_storage_primitive,
    owner as _owner,
    parents as _parents,
    relative as _relative,
    storage_imports as _storage_imports,
    trees as _trees,
)


class SourceGateCoverageError(AssertionError):
    pass


def validate_lifecycle_exemptions(apps_dir=APPS_DIR):
    actual = set()
    functions = _all_functions(apps_dir)
    for target in LIFECYCLE_EXEMPTIONS:
        if target not in functions:
            raise SourceGateCoverageError(f"stale lifecycle exemption: {target}")
        if _calls_gate(functions[target]):
            raise SourceGateCoverageError(
                f"lifecycle exemption unexpectedly participates: {target}"
            )
        actual.add(target)
    expected = {
        "apps.encryption.services.rotate_dek",
        "apps.encryption.services.disable_dek",
        "apps.encryption.services.rewrap_dek",
        "apps.makerspaces.lifecycle_archive.archive",
        "apps.makerspaces.lifecycle_archive._archive_locked",
        "apps.makerspaces.lifecycle_purge.purge",
    }
    _exact("lifecycle exemption", actual, expected)
    return frozenset(actual)


def discover_object_mutations(apps_dir=APPS_DIR):
    entries = []
    for path, module, tree in _trees(apps_dir):
        if _is_storage_primitive(module) or ".migrations." in f".{module}.":
            continue
        storage_aliases, direct_names = _storage_imports(tree)
        parents = _parents(tree)
        for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
            if not _is_object_mutation(call, storage_aliases, direct_names):
                continue
            owner = _owner(call, parents)
            if owner is None:
                continue
            target, owner_node = owner
            full_target = f"{module}.{target}"
            participates = (
                _calls_gate(owner_node)
                or "views" in path.stem
                or path.stem.startswith("admin")
                or path.stem == "tasks"
                or module.startswith("apps.backup.")
                or full_target in LIFECYCLE_EXEMPTIONS
            )
            entries.append(EntryPoint(
                full_target, _relative(path, apps_dir), call.lineno, participates,
            ))
    return tuple(sorted(entries))


def validate_object_mutation_coverage(
    apps_dir=APPS_DIR, *, participants=OBJECT_MUTATION_PARTICIPANTS
):
    entries = discover_object_mutations(apps_dir)
    actual = {entry.target for entry in entries}
    stale = set(participants) - actual
    if stale:
        raise SourceGateCoverageError(
            f"stale object-mutation participation: {sorted(stale)}"
        )
    missing = sorted({
        entry.target for entry in entries
        if not entry.participates
        and entry.target not in participants
    })
    if missing:
        raise SourceGateCoverageError(
            f"object mutations bypass source-gate participation: {missing}"
        )
    return entries


def _exact(kind, actual, declared):
    if actual != declared:
        raise SourceGateCoverageError(
            f"{kind} registry drifted; missing={sorted(actual - declared)}, "
            f"stale={sorted(declared - actual)}"
        )
