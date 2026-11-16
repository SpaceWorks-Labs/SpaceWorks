"""Account-merge dispositions for lane L3 (ID cards, release 2)."""

from .merge_registry_types import KEEP_ON_SHELL as K, REPOINT as R, UNIQUE_RESOLVE as U

_MUTABLE = "Mutable ownership or attribution; moves to the survivor."
_HISTORY = "Append-only design history attribution; stays with the account that acted."

ROWS = (
    (R, "card_designs.CardDesign", "updated_by", _MUTABLE),
    (K, "card_designs.CardDesignRevision", "created_by", _HISTORY),
    (K, "card_designs.CardDesignApproval", "requested_by decided_by", _HISTORY),
    (R, "card_designs.CardDesignAsset", "uploaded_by", _MUTABLE),
    (R, "card_designs.CardJob", "requested_by", "A job and its temporary file belong to whoever asked; moves to the survivor."),
    (R, "card_designs.CardPhotoRequest", "requested_by", _MUTABLE),
    (R, "card_designs.CardPhotoCutout", "requested_by", "A derived cut-out belongs to whoever asked; moves to the survivor."),
    (R, "card_designs.CardPhotoBatch", "created_by", "A temporary photo batch belongs to its creator; moves to the survivor."),
    (R, "events.EventIdCard", "person revoked_by", "The holder's event card follows the person; one live card per registration."),
    (R, "id_programmes.IdProgramme", "created_by", _MUTABLE),
    (U, "id_programmes.IdProgrammeCard", "user",
     "One card per person and programme; the survivor keeps theirs and the loser's stays on the shell."),
    (R, "id_programmes.IdProgrammeImport", "created_by", _MUTABLE),
)
