"""Accounts across a per-space restore: never touched, never resurrected (#111 Q5).

Archived rows keep pointing at the same account ids. An account row that no longer exists
is re-attributed to the space's anonymous principal. An account deleted since the
restore point (its tenant data already scrubbed) is scrubbed again in this space, so the
restore cannot bring its personal data back. An account merged since then (#128 C-17, once
``User.merged_into`` exists) is followed to its survivor: a merge is never undone and a
shell is never re-activated.
"""

from functools import lru_cache

from apps.accounts.models import User


@lru_cache(maxsize=None)
def user_fk_names(model):
    return tuple(
        field.name for field in model._meta.concrete_fields
        if field.is_relation and field.related_model is User
    )


class UserRemap:
    def __init__(self, makerspace):
        self.makerspace = makerspace
        self.referenced = set()
        self.reattributed = 0
        self.followed_merges = 0
        self._known = {}
        self._anonymous = None

    def remap(self, model, record):
        names = user_fk_names(model)
        if not names:
            return record
        fields = dict(record["fields"])
        for name in names:
            value = fields.get(name)
            if value in (None, ""):
                continue
            user_id = self._survivor(int(value))
            if self._exists(user_id):
                self.referenced.add(user_id)
                fields[name] = user_id
                continue
            fields[name] = self._anonymous_id()
            self.reattributed += 1
        return {**record, "fields": fields}

    def _survivor(self, user_id):
        if not any(field.name == "merged_into" for field in User._meta.concrete_fields):
            return user_id
        seen = set()
        while user_id not in seen:
            seen.add(user_id)
            following = User.objects.filter(pk=user_id).values_list("merged_into_id", flat=True).first()
            if following is None:
                return user_id
            self.followed_merges += 1
            user_id = following
        return user_id

    def _exists(self, user_id):
        if user_id not in self._known:
            self._known[user_id] = User.objects.filter(pk=user_id).exists()
        return self._known[user_id]

    def _anonymous_id(self):
        if self._anonymous is None:
            from apps.makerspaces.anonymous_requesters import get_or_create_anonymous_requester
            self._anonymous = get_or_create_anonymous_requester(self.makerspace).pk
        return self._anonymous


def rescrub_deleted_accounts(makerspace, user_ids):
    """Re-run the tenant scrub for every referenced account already erased here."""
    from django.db.models import Q

    from apps.accounts.account_purge import deleted_username, recorded_address
    from apps.accounts.account_purge_scrub import scrub_tenant

    erased = User.objects.filter(pk__in=user_ids, deletion_requested_at__isnull=False).filter(
        Q(account_purged_at__isnull=False)
        | Q(accountpurgeprogress__makerspace=makerspace, accountpurgeprogress__done_at__isnull=False)
    ).distinct().order_by("pk")
    count = 0
    for user in erased:
        scrub_tenant(user, makerspace.pk, username=deleted_username(user), address=recorded_address(user))
        count += 1
    return count
