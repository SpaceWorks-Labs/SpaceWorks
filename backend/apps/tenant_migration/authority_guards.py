"""Conservative authorization-input drift guard for portable tenant imports.

The mechanical part scans attribute access, ORM lookup names, ``getattr`` field names,
and ``values_list``/``only`` field strings in the ``accounts/rbac*.py`` implementation
modules, the locked makerspace role-authority/assignment modules and ``machines/access.py``.
It then intersects those names with a reviewed set of
exported authorization models. The explicit declarations also cover
authority/disclosure inputs identified by the migration threat model.

This cannot see authorization assembled dynamically, raw SQL, fields consulted only in
other modules, semantic changes to a declared field, or a new authorization module.  It
also deliberately over-approximates where the AST cannot infer an expression's model.
Code review remains necessary; this guard makes the mechanically visible subset fail
closed instead of claiming whole-program authorization analysis.

The scanned file list lives in ``authority_sources`` and the reviewed declarations in
``authority_explicit_fields``; both are re-exported here, so callers keep importing
``APPS_DIR``, ``AUTHORIZATION_SOURCES`` and ``EXPLICIT_AUTHORITY_FIELDS`` from this module.
"""

import ast
from pathlib import Path

from django.apps import apps

from apps.data_export.models import EXPORTED_MODEL_FIELDS

from .authority_events_programme import FIELDS as PROGRAMME_AUTHORITY_FIELDS, SCANNED_LABELS
from .authority_explicit_fields import EXPLICIT_AUTHORITY_FIELDS
from .authority_reimbursements import FIELDS as REIMBURSEMENT_AUTHORITY_FIELDS
from .authority_resource_fields import RESOURCE_SCANNED_MODEL_LABELS
from .authority_sources import APPS_DIR, AUTHORIZATION_SOURCES
from .catalog_p2_presence import FIELD_NAMES as PRESENCE_FIELDS
from .catalog_public_pages import EXPORTED_FIELDS as PAGE_EXPORTED_FIELDS
from .target_projection import TARGET_FIELD_PROJECTION


class AuthorityRegistryError(AssertionError):
    pass


SCANNED_MODEL_LABELS = frozenset({
    "makerspaces.MembershipAdditionalRole",
    "machines.MembershipMachineTypeScope",
    "makerspaces.Makerspace",
    "makerspaces.MakerspaceMembership",
    "makerspaces.MakerspaceRole",
    "machines.Machine",
    "machines.MachineOperator",
    "machines.MachineType",
}) | RESOURCE_SCANNED_MODEL_LABELS

DECLARED_AUTHORITY_FIELDS = {
    **{edge: policy.reason for edge, policy in TARGET_FIELD_PROJECTION.items()},
    **EXPLICIT_AUTHORITY_FIELDS,
}
SCANNED_MODEL_LABELS |= PAGE_EXPORTED_FIELDS.keys()
DECLARED_AUTHORITY_FIELDS.update({
    (label, field): "Authored page history is remapped with reset publication/disclosures and locked target-side owner authority."
    for label, fields in PAGE_EXPORTED_FIELDS.items() for field in fields.split() if field != "id"
})
DECLARED_AUTHORITY_FIELDS.update({
    ("events.EventPage", field): "Selected publication and editorial content travel only with reviewed page-pointer/disclosure resets."
    for field in ("draft_revision", "published_revision", "editorial_document")
})
SCANNED_MODEL_LABELS |= PRESENCE_FIELDS.keys()
DECLARED_AUTHORITY_FIELDS.update({
    (label, field): "Source-local presence/disclosure input; the entire model is DROP on tenant import."
    for label, fields in PRESENCE_FIELDS.items() for field in fields if field != "id"
})
SCANNED_MODEL_LABELS |= SCANNED_LABELS
DECLARED_AUTHORITY_FIELDS.update(PROGRAMME_AUTHORITY_FIELDS)
DECLARED_AUTHORITY_FIELDS.update(REIMBURSEMENT_AUTHORITY_FIELDS)
from .catalog_unified_accounts import AUTHORITY_DECLARATIONS as UNIFIED_ACCOUNT_AUTHORITY  # noqa: E402
DECLARED_AUTHORITY_FIELDS.update(UNIFIED_ACCOUNT_AUTHORITY)


def _normalise_field_name(name, model_fields):
    root = name.split("__", 1)[0]
    if root.endswith("_id") and root[:-3] in model_fields:
        return root[:-3]
    return root


def discover_authorization_field_names(paths=AUTHORIZATION_SOURCES):
    names = set()
    for path in paths:
        tree = ast.parse(Path(path).read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.keyword) and node.arg:
                names.update(node.arg.split("__"))
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "getattr" and len(node.args) > 1:
                    value = node.args[1]
                    if isinstance(value, ast.Constant) and isinstance(value.value, str):
                        names.add(value.value)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in {"values_list", "only", "defer"}:
                    for value in node.args:
                        if isinstance(value, ast.Constant) and isinstance(value.value, str):
                            names.update(value.value.split("__"))
    return frozenset(names)


def discover_exported_authority_fields(paths=AUTHORIZATION_SOURCES):
    names = discover_authorization_field_names(paths)
    discovered = set()
    for label in SCANNED_MODEL_LABELS:
        exported = set(EXPORTED_MODEL_FIELDS[label].split())
        for name in names:
            normalized = _normalise_field_name(name, exported)
            if normalized in exported and normalized not in {"id", "created_at", "updated_at"}:
                discovered.add((label, normalized))
    return frozenset(discovered)


def validate_authority_registry(
    declarations=DECLARED_AUTHORITY_FIELDS,
    *,
    paths=AUTHORIZATION_SOURCES,
    required_fields=None,
):
    required = (
        set(TARGET_FIELD_PROJECTION) | set(EXPLICIT_AUTHORITY_FIELDS)
        if required_fields is None
        else set(required_fields)
    )
    missing_required = required - set(declarations)
    if missing_required:
        raise AuthorityRegistryError(
            f"required authority declarations are missing: {sorted(missing_required)}"
        )
    discovered = discover_exported_authority_fields(paths)
    missing = discovered - set(declarations)
    if missing:
        raise AuthorityRegistryError(
            f"exported authorization inputs are undeclared: {sorted(missing)}"
        )
    for label, field_name in declarations:
        model = apps.get_model(label)
        try:
            model._meta.get_field(field_name)
        except Exception as exc:
            raise AuthorityRegistryError(
                f"declared authority field no longer exists: {label}.{field_name}"
            ) from exc
