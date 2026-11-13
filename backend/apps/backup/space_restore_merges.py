"""Merged people across a per-space restore (#128 C-17).

An archived row that names a person merged since the restore point follows
``merged_into`` to the survivor: a merge is never undone and a shell is never re-activated.
A relation the merge registry marks UNIQUE_RESOLVE (one row per person in its scope)
follows the merge engine's rule instead: the row moves to the survivor unless the archive
already gives the survivor that unique slot, in which case the survivor's own row wins and
the merged row comes back on the shell. A membership kept on a shell comes back REVOKED,
the only state a shell may hold one in.
"""

from functools import lru_cache

from django.db.models import UniqueConstraint

from apps.accounts.models import User

MEMBERSHIP = "makerspaces.MakerspaceMembership"


@lru_cache(maxsize=None)
def unique_slots(model, field_name):
    """Every unique field set of ``model`` that contains the user field ``field_name``."""
    from apps.accounts.merge_registry import UNIQUE_RESOLVE, disposition_for

    if disposition_for(model._meta.label, field_name) != UNIQUE_RESOLVE:
        return ()
    sets = [tuple(constraint.fields) for constraint in model._meta.constraints
            if isinstance(constraint, UniqueConstraint) and field_name in constraint.fields]
    sets += [tuple(names) for names in model._meta.unique_together if field_name in names]
    if model._meta.get_field(field_name).unique:
        sets.append((field_name,))
    return tuple(sets)


class MergeFollow:
    def __init__(self, archive):
        self.archive = archive
        self.followed = 0
        self.kept_on_shell = 0
        self._survivors = {}
        self._direct = {}
        self._moved = set()

    def survivor(self, user_id):
        """The live person ``user_id`` was merged into, transitively (itself if never merged)."""
        if user_id not in self._survivors:
            current, seen = user_id, set()
            while current not in seen:
                seen.add(current)
                following = (User._base_manager.filter(pk=current)
                             .values_list("merged_into_id", flat=True).first())
                if following is None:
                    break
                current = following
            self._survivors[user_id] = current
        return self._survivors[user_id]

    def resolve(self, model, field_name, fields, source, survivor):
        """The user id this row's ``field_name`` takes; ``fields`` may be marked revoked."""
        slot_sets = unique_slots(model, field_name)
        for index, names in enumerate(slot_sets):
            slot = (model._meta.label, index, *(survivor if name == field_name else fields.get(name)
                                                for name in names))
            if slot in self._direct_slots(model, field_name, index, names) or slot in self._moved:
                self.kept_on_shell += 1
                if model._meta.label == MEMBERSHIP:
                    merged_at = User._base_manager.filter(pk=source).values_list("merged_at", flat=True).first()
                    fields["status"] = "revoked"
                    fields["revoked_at"] = fields.get("revoked_at") or (merged_at.isoformat() if merged_at else None)
                return source
        for index, names in enumerate(slot_sets):
            self._moved.add((model._meta.label, index, *(survivor if name == field_name else fields.get(name)
                                                         for name in names)))
        self.followed += 1
        return survivor

    def _direct_slots(self, model, field_name, index, names):
        """Slots the archive gives people who were never merged."""
        key = (model._meta.label, field_name, index)
        if key not in self._direct:
            slots = set()
            for row in self.archive.rows(model._meta.label) if self.archive is not None else ():
                value = row["fields"].get(field_name)
                if value in (None, "") or self.survivor(int(value)) != int(value):
                    continue
                slots.add((model._meta.label, index, *(int(value) if name == field_name else row["fields"].get(name)
                                                       for name in names)))
            self._direct[key] = slots
        return self._direct[key]
