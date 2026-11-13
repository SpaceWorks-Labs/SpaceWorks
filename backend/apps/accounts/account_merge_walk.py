"""Walk ``accounts.merge_registry`` for one source account (read by preview and engine).

Every reference to ``accounts.User`` has exactly one disposition (system check
``accounts.E003``). This module only READS the registry; it never classifies. A row is
found through the model's base manager (every stored row: both membership tracks, and no
custom queryset that would hide history) by its user column.

UNIQUE_RESOLVE: a row moves unless the survivor already holds its unique slot (a unique
field set that includes the user column, evaluated with the constraint's condition).
Then the survivor wins and the loser stays on the shell, revoked where the model has a
revocation field.
"""

from django.apps import apps
from django.db import models
from django.db.models import UniqueConstraint
from django.utils import timezone

from apps.accounts import merge_registry
from apps.accounts.merge_registry_types import KEEP_ON_SHELL, REPOINT, UNIQUE_RESOLVE


class UnclassifiedReference(Exception):
    """The installed model graph has a user reference the registry does not classify."""


def assert_classified():
    problems = merge_registry.problems()
    if problems["unclassified_relations"] or problems["unclassified_columns"]:
        raise UnclassifiedReference(problems)


def references():
    """``(model, column, disposition)`` for every installed classified reference."""
    entries = [*merge_registry.USER_REFERENCES.items(), *merge_registry.USER_ID_COLUMNS.items()]
    for (label, name), disposition in sorted(entries):
        try:
            model = apps.get_model(label)
        except LookupError:
            continue
        field = model._meta.get_field(name)
        if isinstance(field, models.ManyToManyField):
            if disposition != KEEP_ON_SHELL:
                raise UnclassifiedReference({"many_to_many": f"{label}.{name}"})
            continue
        if label == "accounts.User":
            continue  # merged_into: alias chains stay intact.
        yield model, field.attname, disposition


def rows(model, column, user_id):
    return model._base_manager.filter(**{column: user_id})


def _unique_sets(model, column):
    field_names = {field.name: field.attname for field in model._meta.concrete_fields}
    attname_to_name = {attname: name for name, attname in field_names.items()}
    name = attname_to_name.get(column, column)
    sets = []
    for field in model._meta.concrete_fields:
        if field.unique and not field.primary_key and field.attname == column:
            sets.append(((column,), None))
    for together in model._meta.unique_together:
        if name in together:
            sets.append((tuple(field_names[item] for item in together), None))
    for constraint in model._meta.constraints:
        if isinstance(constraint, UniqueConstraint) and constraint.fields and name in constraint.fields:
            sets.append((tuple(field_names[item] for item in constraint.fields), constraint.condition))
    return sets


def conflicts(model, column, row, survivor_id):
    """True when moving ``row`` to the survivor would take a slot the survivor holds."""
    for columns, condition in _unique_sets(model, column):
        if condition is not None and not model._base_manager.filter(pk=row.pk).filter(condition).exists():
            continue
        values = {item: getattr(row, item) for item in columns if item != column}
        if any(value is None for value in values.values()):
            continue  # NULL never collides in a unique index.
        taken = model._base_manager.filter(**{column: survivor_id}, **values)
        if condition is not None:
            taken = taken.filter(condition)
        if taken.exclude(pk=row.pk).exists():
            return True
    return False


def plan(source_id, survivor_id):
    """Counts per reference: ``{(label, column): {"disposition", "rows", "move", "keep"}}``."""
    result = {}
    for model, column, disposition in references():
        found = rows(model, column, source_id)
        count = found.count()
        if not count:
            continue
        entry = {"disposition": disposition, "rows": count, "move": 0, "keep": 0}
        if disposition == REPOINT:
            entry["move"] = count
        elif disposition == KEEP_ON_SHELL:
            entry["keep"] = count
        else:
            for row in found.iterator():
                entry["keep" if conflicts(model, column, row, survivor_id) else "move"] += 1
        result[(model._meta.label, column)] = entry
    return result


def revoke_loser(model, row, now=None):
    """Mark a UNIQUE_RESOLVE loser revoked when the model can say so; else leave it inert."""
    now = now or timezone.now()
    names = {field.name: field for field in model._meta.concrete_fields}
    changes = {}
    if "status" in names and any(value == "revoked" for value, _label in (names["status"].choices or ())):
        changes["status"] = "revoked"
    if "revoked_at" in names:
        changes["revoked_at"] = getattr(row, "revoked_at", None) or now
    for flag in ("active", "is_active", "enabled"):
        if flag in names and isinstance(names[flag], models.BooleanField):
            changes[flag] = False
    if changes:
        model._base_manager.filter(pk=row.pk).update(**changes)
    return bool(changes)


__all__ = ["KEEP_ON_SHELL", "REPOINT", "UNIQUE_RESOLVE", "UnclassifiedReference", "assert_classified",
           "conflicts", "plan", "references", "revoke_loser", "rows"]
