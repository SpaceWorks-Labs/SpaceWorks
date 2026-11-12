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
from .merge_registry_rows_finance import ROWS as _FINANCE
from .merge_registry_rows_membership import ROWS as _MEMBERSHIP
from .merge_registry_rows_pricing import ROWS as _PRICING
from .merge_registry_rows_l12 import ROWS as _L12
from .merge_registry_rows_l23 import ROWS as _L23
from .merge_registry_rows_l16 import ROWS as _L16
from .merge_registry_rows_l3 import ROWS as _L3
from .merge_registry_rows_l3a import ROWS as _L3A
from .merge_registry_rows_l6 import ROWS as _L6
from .merge_registry_rows_l18 import ROWS as _L18
from .merge_registry_rows_l21a import ROWS as _L21A
from .merge_registry_rows_r3_events_badges import ROWS as _E_B2_BADGES
from .merge_registry_rows_l21b import ROWS as _L21B
from .merge_registry_rows_hackmoney import ROWS as _HACKMONEY
from .merge_registry_rows_l22 import ROWS as _L22
from .merge_registry_rows_tokens import ROWS as _TOKENS
from .merge_registry_rows_submit_content import ROWS as _SUBMIT_CONTENT
from .merge_registry_rows_peoples_choice import ROWS as _PEOPLES_CHOICE
from .merge_registry_rows_certificates import ROWS as _CERTIFICATES
from .merge_registry_rows_operations import ROWS as _OPERATIONS
from .merge_registry_rows_superadmin import ROWS as _SUPERADMIN
from .merge_registry_rows_guest_passes import ROWS as _GUEST_PASSES
from .merge_registry_rows_l3b import ROWS as _L3B
from .merge_registry_rows_account_profile import ROWS as _ACCOUNT_PROFILE
from .merge_registry_types import (  # noqa: F401 -- re-exported
    KEEP_ON_SHELL, REPOINT, UNIQUE_RESOLVE, compose,
)

USER_REFERENCES, USER_ID_COLUMNS = compose(_ACCOUNTS, _COMMUNITY, _EVENTS, _OPERATIONS, _MEMBERSHIP, _FINANCE, _PRICING, _L12, _L23, _L16, _L3, _L3A, _L6, _L18, _L21A, _L21B, _L22, _SUBMIT_CONTENT, _HACKMONEY, _PEOPLES_CHOICE, _CERTIFICATES, _SUPERADMIN, _TOKENS, _GUEST_PASSES, _L3B, _E_B2_BADGES, _ACCOUNT_PROFILE)


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
