"""What an account merge does to every reference to ``accounts.User`` (one account per person).

When a shell is merged into its person (U-C's engine, decision #65), every relation to
``accounts.User`` follows exactly one disposition:

- ``REPOINT``: the row moves to the survivor (ownership and mutable attribution);
- ``KEEP_ON_SHELL``: the row keeps pointing at the shell (immutable history, append-only
  ledgers and evidence, credentials and sessions, platform authority);
  ``staff_identity.actor_ids_for`` follows the alias when reading history;
- ``UNIQUE_RESOLVE``: the row moves unless the survivor already holds the unique slot; then
  the survivor wins and the loser stays on the shell, revoked.

Integer columns that hold a user id without a foreign key (``*user_id``/``*actor_id``)
are listed with their disposition too. System check ``accounts.E003`` refuses the build
when a relation or such column is unclassified, or a row names one that no longer exists,
so a new model cannot silently escape the merge. Rows live in domain fragments; this
module only composes them (a hot file: lanes add rows, never edit others').
"""

from .merge_registry_rows_accounts import ROWS as _ACCOUNTS
from .merge_registry_rows_community import ROWS as _COMMUNITY
from .merge_registry_rows_events import ROWS as _EVENTS
from .merge_registry_rows_membership import ROWS as _MEMBERSHIP
from .merge_registry_rows_operations import ROWS as _OPERATIONS
from .merge_registry_types import (  # noqa: F401 -- re-exported
    KEEP_ON_SHELL, REPOINT, UNIQUE_RESOLVE, compose,
)

USER_REFERENCES, USER_ID_COLUMNS = compose(_ACCOUNTS, _COMMUNITY, _EVENTS, _OPERATIONS, _MEMBERSHIP)


def disposition_for(label, field_name):
    return USER_REFERENCES.get((label, field_name)) or USER_ID_COLUMNS.get((label, field_name))


def _is_user_id_column(field):
    from django.db import models

    return (not field.is_relation and isinstance(field, models.IntegerField)
            and (field.name.endswith("user_id") or field.name.endswith("actor_id")))


def discovered():
    """``(relations, id_columns)`` actually present in the installed model graph."""
    from django.apps import apps
    from django.contrib.auth import get_user_model
    from django.db import models

    user = get_user_model()
    relations, columns = set(), set()
    for model in apps.get_models(include_auto_created=True):
        for field in model._meta.get_fields():
            concrete = getattr(field, "concrete", False) or isinstance(field, models.ManyToManyField)
            if not concrete or field.auto_created:
                continue
            if field.is_relation and field.related_model is user:
                relations.add((model._meta.label, field.name))
            elif _is_user_id_column(field):
                columns.add((model._meta.label, field.name))
    return relations, columns


def problems():
    relations, columns = discovered()
    return {
        "unclassified_relations": sorted(relations - set(USER_REFERENCES)),
        "unclassified_columns": sorted(columns - set(USER_ID_COLUMNS)),
        "stale_relations": sorted(set(USER_REFERENCES) - relations),
        "stale_columns": sorted(set(USER_ID_COLUMNS) - columns),
    }
