"""Cursor selection for the owned evidence sweeps; full-profile behavior is inert."""

from django.conf import settings

from .budget import checkpoint
from .contracts import CapabilityError


class FreeSweep:
    def __init__(self, summary, cursor):
        self.enabled = getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") == "free"
        self.summary = summary
        self.cursor = {"makerspace_id": 0, "evidence_after": 0}
        self.more_tenants = False
        if not self.enabled:
            return
        if cursor is not None:
            if (
                not isinstance(cursor, dict) or set(cursor) != set(self.cursor)
                or any(type(value) is not int or value < 0 for value in cursor.values())
            ):
                raise CapabilityError("storage_sweep_cursor_invalid")
            self.cursor = dict(cursor)
        summary.update(next_cursor=dict(self.cursor), budget_deferred=False)

    def batch_size(self, value):
        return min(value, 5) if self.enabled else value

    def makerspaces(self, queryset):
        if not self.enabled:
            return queryset.iterator(chunk_size=100)
        checkpoint()
        rows = list(queryset.filter(pk__gte=self.cursor["makerspace_id"])[:2])
        self.more_tenants = len(rows) > 1
        if not rows:
            self.summary["next_cursor"] = None
        return rows[:1]

    def candidates(self, queryset, makerspace_id):
        if self.enabled and makerspace_id == self.cursor["makerspace_id"]:
            return queryset.filter(pk__gt=self.cursor["evidence_after"])
        return queryset

    def before_item(self, makerspace_id, evidence_id):
        if not self.enabled:
            return True
        self.summary["next_cursor"] = {
            "makerspace_id": makerspace_id, "evidence_after": evidence_id - 1,
        }
        try:
            checkpoint()
        except CapabilityError as exc:
            if exc.code != "storage_budget_exhausted":
                raise
            self.summary.update(budget_deferred=True, continuation_required=True)
            return False
        return True

    def finish_page(self, makerspace_id, ids, has_more):
        if not self.enabled:
            return
        self.summary["next_cursor"] = (
            {"makerspace_id": makerspace_id, "evidence_after": ids[-1]}
            if has_more and ids else
            {"makerspace_id": makerspace_id + 1, "evidence_after": 0}
            if self.more_tenants else None
        )
        self.summary["continuation_required"] = self.summary["next_cursor"] is not None

    def skip(self, makerspace_id):
        self.finish_page(makerspace_id, [], False)
