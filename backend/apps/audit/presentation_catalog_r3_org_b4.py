"""Parity O-B4 part 2: staff ID cards. Ids, counts and machine-readable reasons only: never a person's name or the
roles' names (the card and membership ids identify the row)."""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("staff_card.issued", gettext_noop("Staff card issued")),  # metadata is denied: the emitter builds meta at runtime
    P("staff_card.auto_issued", gettext_noop("Staff card issued automatically")),  # metadata is denied: the emitter builds meta at runtime
    P("staff_card.auto_issue_skipped", gettext_noop("Automatic staff card skipped"), ("membership_id", "reason")),
    P("staff_card.reissued", gettext_noop("Staff card reissued"), ("card_id", "card_number", "reason")),
    P("staff_card.revoked", gettext_noop("Staff card revoked"), ("card_id", "card_number", "reason")),
    P("staff_card.printed", gettext_noop("Staff card printed"), ("card_id", "card_number", "count")),
    P("staff_card.downloaded", gettext_noop("Staff card downloaded"), ("card_id", "format", "side")),
    P("staff_card.numbering_changed", gettext_noop("Staff card numbering changed"), ("prefix", "pattern")),
)
