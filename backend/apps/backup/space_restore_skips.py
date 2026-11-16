"""Archived rows a restore must not bring back, and everything that hangs off them.

A membership whose account has since been retired (or is a platform account) cannot
exist again: the account guards refuse it, and a retired account is never resurrected.
Such a row is skipped, and so is every archived row that depends on a skipped row,
following the foreign key's ``on_delete`` exactly as a delete would: CASCADE skips the
dependent, SET_NULL clears the reference, anything else refuses the restore.
"""

from collections import defaultdict
from functools import lru_cache

from django.db import models

from .space_restore_plan import SpaceRestoreError


@lru_cache(maxsize=None)
def _relations(model):
    return tuple(field for field in model._meta.concrete_fields if field.is_relation and field.related_model)


class ArchiveSkips:
    def __init__(self):
        self.skipped = defaultdict(set)
        self._unavailable_users = None

    def admit(self, model, record):
        """The record to insert (possibly with references cleared), or None to skip it."""
        label = model._meta.label
        if label == "makerspaces.MakerspaceMembership" and int(record["fields"]["user"]) in self._users():
            return self._skip(label, model, record)
        fields = None
        for field in _relations(model):
            target = field.related_model._meta.label
            value = record["fields"].get(field.name)
            if not self.skipped.get(target) or value in (None, ""):
                continue
            if field.related_model._meta.pk.to_python(value) not in self.skipped[target]:
                continue
            on_delete = field.remote_field.on_delete
            if on_delete is models.CASCADE:
                return self._skip(label, model, record)
            if on_delete is models.SET_NULL and field.null:
                fields = fields or dict(record["fields"])
                fields[field.name] = None
                continue
            raise SpaceRestoreError(
                "archive_conflict", f"{label} row {record['pk']} depends on a row that cannot come back.")
        return record if fields is None else {**record, "fields": fields}

    def counts(self):
        return {label: len(pks) for label, pks in self.skipped.items()}

    def _skip(self, label, model, record):
        self.skipped[label].add(model._meta.pk.to_python(record["pk"]))
        return None

    def _users(self):
        if self._unavailable_users is None:
            from django.db.models import Q

            from apps.accounts.models import User
            from apps.accounts.staff_identity import platform_q
            self._unavailable_users = set(User.objects.filter(
                Q(retired_at__isnull=False) | platform_q()).values_list("pk", flat=True))
        return self._unavailable_users
