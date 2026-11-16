"""Account-merge dispositions for the global profile (decision 305)."""

from .merge_registry_types import UNIQUE_RESOLVE as U

ROWS = (
    (U, "makerspaces.AccountProfile", "user",
     "One profile per person; `account_profile_account_merge` folds the source's content into the survivor's "
     "before the walk, so a loser row only remains when the combine was refused."),
)
