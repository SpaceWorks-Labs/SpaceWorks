"""AST discovery of audit call sites the presentation catalogue cannot treat as literal.

``tenant_migration.audit_reference_guards`` already finds every ``audit.record`` call and
reports the ones whose action or metadata is not a literal. This walks the same calls and
says, for each of those, WHAT it can emit, so the presentation guard can hold the deny
policy exact without keying anything on line numbers (which every unrelated edit moves):

- ``non_literal_meta`` -- a literal action whose ``meta`` is built at runtime;
- ``exact`` -- a dynamic action that only ever yields string constants (``a if x else b``
  or a local variable assigned only such constants);
- ``wrapper`` -- anything else (a parameter, an attribute, an f-string): the emitted
  action set is unknowable here and must be covered by a reviewed namespace prefix.
"""

import ast
from dataclasses import dataclass
from pathlib import Path

from apps.tenant_migration.audit_reference_guards import (
    APPS_DIR,
    _argument,
    _audit_record_imports,
    _is_record_call,
)


@dataclass(frozen=True)
class DynamicAuditSite:
    path: str
    kind: str  # "non_literal_meta" | "exact" | "wrapper"
    actions: frozenset[str]  # literal/resolved actions; empty for a wrapper


def _constants(node):
    """Every string a constant-only expression can evaluate to, or None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}
    if isinstance(node, ast.IfExp):
        body, orelse = _constants(node.body), _constants(node.orelse)
        return None if body is None or orelse is None else body | orelse
    return None


def _enclosing_function(tree, call):
    found = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if any(child is call for child in ast.walk(node)):
                found = node  # keep walking: the innermost one wins
    return found


def _resolve_name(function, name):
    if function is None:
        return None
    arguments = function.args
    parameters = {
        item.arg
        for item in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs)
    }
    if name in parameters:
        return None
    values = set()
    for node in ast.walk(function):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            resolved = _constants(node.value)
            if resolved is None:
                return None
            values |= resolved
    return values or None


def _relative(path, apps_dir):
    return str(Path(path).relative_to(apps_dir)).replace("\\", "/")


def discover_dynamic_audit_sites(apps_dir=APPS_DIR):
    sites = []
    for path in sorted(Path(apps_dir).rglob("*.py")):
        if "migrations" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        module_aliases, direct_names = _audit_record_imports(tree)
        relative = _relative(path, apps_dir)
        page_finish_names = {"finish"} if relative == "makerspaces/public_page_services.py" else set()
        for item in ast.walk(tree):
            if isinstance(item, ast.ImportFrom) and item.module in {
                "public_page_services", "apps.makerspaces.public_page_services",
            }:
                page_finish_names.update(alias.asname or alias.name for alias in item.names if alias.name == "finish")
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) in page_finish_names:
                # This reviewed wrapper accepts action as its fifth positional
                # argument. Enumerate its call sites; a parameter/new expression
                # cannot silently expand the staff audit vocabulary.
                actions = _constants(node.args[4]) if len(node.args) > 4 else None
                if actions is None:
                    raise ValueError("Public page audit wrapper action must be a closed literal expression")
                sites.append(DynamicAuditSite(relative, "exact", frozenset(actions)))
                continue
            if not _is_record_call(node, module_aliases, direct_names):
                continue
            action_node = _argument(node, 1, "action")
            meta = _argument(node, None, "meta")
            literal = _constants(action_node) if isinstance(action_node, ast.Constant) else None
            if literal is None:
                resolved = _constants(action_node)
                if resolved is None and isinstance(action_node, ast.Name):
                    resolved = _resolve_name(
                        _enclosing_function(tree, node), action_node.id
                    )
                if resolved is None:
                    sites.append(DynamicAuditSite(relative, "wrapper", frozenset()))
                else:
                    sites.append(DynamicAuditSite(relative, "exact", frozenset(resolved)))
                continue
            if meta is not None and (
                not isinstance(meta, ast.Dict)
                or any(
                    not isinstance(key, ast.Constant) for key in _all_dict_keys(meta)
                )
            ):
                sites.append(DynamicAuditSite(relative, "non_literal_meta", frozenset(literal)))
    return sites


def _all_dict_keys(mapping):
    for key, value in zip(mapping.keys, mapping.values):
        yield key  # ``None`` for ``**spread``: not a Constant, so it is non-literal
        if isinstance(value, ast.Dict):
            yield from _all_dict_keys(value)
