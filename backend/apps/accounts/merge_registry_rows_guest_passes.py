"""Account-merge dispositions for decision 223 (guest passes)."""

from .merge_registry_types import KEEP_ON_SHELL as K, REPOINT as R

ROWS = (
    (K, "makerspaces.GuestPass", "holder",
     "A pass is accountability history for the account that held it; actor_ids_for follows the alias."),
    (R, "makerspaces.GuestPass", "sponsor issued_by revoked_by", "Mutable attribution; moves to the survivor."),
    (R, "makerspaces.GuestPassPolicy", "updated_by", "Mutable attribution; moves to the survivor."),
)
