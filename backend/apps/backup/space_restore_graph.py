"""Rows that point at what a restore removes, resolved with Django's on_delete rules.

A restore replaces the space's dataset rows with the archive's. A live row the archive
does not carry (created after the restore point) is gone afterwards, so every row that
still points at it must be resolved, exactly as deleting it would:

* a row of THIS space (or a global dependent) follows its foreign key's ``on_delete``:
  CASCADE deletes it, SET_NULL clears the reference;
* a row of ANOTHER space is never changed (#113), an append-only record is never
  touched, and PROTECT/RESTRICT stay protective: each of those BLOCKS the restore.

Rows that point at a row the archive brings back need nothing: identity primary keys
re-link them. The same walk runs read-only for the preview and for real on apply.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache

from django.apps import apps
from django.db import connection, models

from .slice_rows import SLICE_ROW_SPECS
from .space_restore_plan import KEPT_LIVE, live_queryset, restorable_labels

CHUNK = 1000
_APPEND_ONLY_APPS = frozenset({"audit"})


@dataclass
class GraphOutcome:
    deleted: dict = field(default_factory=lambda: defaultdict(int))
    nulled: dict = field(default_factory=lambda: defaultdict(int))
    blocked: list = field(default_factory=list)

    def summary(self):
        return {
            "cascade_deleted": dict(self.deleted),
            "references_cleared": dict(self.nulled),
            "blocking": self.blocked[:200],
            "blocking_count": len(self.blocked),
        }


@lru_cache(maxsize=None)
def inbound_edges(target_label):
    target = apps.get_model(target_label)
    edges = []
    for model in apps.get_models(include_auto_created=True):
        for item in model._meta.concrete_fields:
            if item.is_relation and item.related_model is target and (item.many_to_one or item.one_to_one):
                edges.append((model, item))
    return tuple(edges)


def resolve(makerspace_id, gone, *, apply):
    """Walk every reference into ``gone`` ({label: pks}); mutate only when ``apply``."""
    outcome = GraphOutcome()
    queue = [(label, set(pks)) for label, pks in gone.items() if pks]
    seen = defaultdict(set)
    while queue:
        label, pks = queue.pop()
        pks -= seen[label]
        if not pks:
            continue
        seen[label] |= pks
        for model, fk in inbound_edges(label):
            for chunk in _chunks(sorted(pks, key=str)):
                rows = list(model._base_manager.filter(**{f"{fk.attname}__in": chunk}).values_list("pk", flat=True))
                if not rows:
                    continue
                cascaded = _resolve_rows(makerspace_id, model, fk, rows, outcome, apply=apply)
                if cascaded:
                    queue.append((model._meta.label, set(cascaded)))
    return outcome


def _resolve_rows(makerspace_id, model, fk, pks, outcome, *, apply):
    label = model._meta.label
    foreign = foreign_pks(makerspace_id, model, pks)
    if label in restorable_labels():
        # This space's own dataset rows are replaced wholesale by the archive's.
        pks = [pk for pk in pks if pk in foreign]
    on_delete = fk.remote_field.on_delete
    cascaded = []
    for pk in pks:
        reason = None
        if pk in foreign:
            reason = "other_space"
        elif label in KEPT_LIVE or model._meta.app_label in _APPEND_ONLY_APPS:
            reason = "append_only"
        elif on_delete is models.CASCADE:
            cascaded.append(pk)
            continue
        elif on_delete is models.SET_NULL and fk.null:
            outcome.nulled[f"{label}.{fk.name}"] += 1
            if apply:
                _raw_update_null(model, fk, pk)
            continue
        else:
            reason = "protected"
        outcome.blocked.append({"model": label, "pk": str(pk), "field": fk.name,
                                "references": fk.related_model._meta.label, "reason": reason})
    if cascaded:
        outcome.deleted[label] += len(cascaded)
        if apply:
            raw_delete(model, cascaded)
    return cascaded


def foreign_pks(makerspace_id, model, pks):
    """Rows that belong to another makerspace: by their canonical owner, or by a
    ``makerspace`` column naming another space (a collaborator row names its own)."""
    label = model._meta.label
    foreign = set()
    if label in SLICE_ROW_SPECS:
        own = set(live_queryset(label, makerspace_id).filter(pk__in=pks).values_list("pk", flat=True))
        foreign |= set(model._base_manager.filter(pk__in=pks).exclude(pk__in=own).values_list("pk", flat=True))
    if any(item.name == "makerspace" for item in model._meta.concrete_fields):
        foreign |= set(model._base_manager.filter(pk__in=pks).exclude(makerspace_id=makerspace_id)
                       .exclude(makerspace_id__isnull=True).values_list("pk", flat=True))
    return foreign


def raw_delete(model, pks):
    quote = connection.ops.quote_name
    pk = model._meta.pk
    with connection.cursor() as cursor:
        for chunk in _chunks(list(pks)):
            cursor.execute(
                f"DELETE FROM {quote(model._meta.db_table)} WHERE {quote(pk.column)} = ANY(%s)",
                [[pk.get_db_prep_value(value, connection) for value in chunk]],
            )


def _raw_update_null(model, fk, pk):
    quote = connection.ops.quote_name
    with connection.cursor() as cursor:
        cursor.execute(
            f"UPDATE {quote(model._meta.db_table)} SET {quote(fk.column)} = NULL "
            f"WHERE {quote(model._meta.pk.column)} = %s",
            [model._meta.pk.get_db_prep_value(pk, connection)],
        )


def _chunks(values):
    values = list(values)
    for start in range(0, len(values), CHUNK):
        yield values[start:start + CHUNK]
