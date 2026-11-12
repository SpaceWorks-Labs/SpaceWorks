"""Decision 314(c): the eraser provider settings, card-photo cut-outs and bulk photo batches.

Ids, counts and machine-readable codes only: never a name, an address, a secret or a photo.
"""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("image_adapter.saved", gettext_noop("Eraser provider saved"), ("scope", "fingerprint")),
    P("image_adapter.rotated", gettext_noop("Eraser provider secret rotated"), ("scope", "fingerprint")),
    P("image_adapter.removed", gettext_noop("Eraser provider removed"), ("scope", "fingerprint")),
    P("image_adapter.platform_switch", gettext_noop("Platform eraser fallback switched"),
      ("scope", "fingerprint", "use_platform_provider")),
    P("image_adapter.tested", gettext_noop("Eraser provider tested"), ("scope", "fingerprint", "outcome")),
    P("card.photo_cutout_requested", gettext_noop("Card photo background removal requested"),
      ("card_id", "holder_kind", "cutout_id", "by_holder")),
    P("card.photo_cutout_done", gettext_noop("Card photo cut-out ready"),
      ("card_id", "holder_kind", "cutout_id", "provider_scope")),
    P("card.photo_cutout_failed", gettext_noop("Card photo background removal failed"),
      ("card_id", "holder_kind", "cutout_id", "error_code")),
    P("card.photo_cutout_choice", gettext_noop("Card photo cut-out or original chosen"),
      ("card_id", "holder_kind", "cutout_id", "use")),
    P("card.photo_cutout_discarded", gettext_noop("Card photo cut-out discarded"),
      ("card_id", "holder_kind", "cutout_id")),
    # Decision 345(b): the photo owner's background-removal opt-out.
    P("card.photo_eraser_opted_out", gettext_noop("Card photo opted out of background removal")),  # metadata is denied: the emitter picks the action at runtime
    P("card.photo_eraser_opted_in", gettext_noop("Card photo opted back into background removal")),  # metadata is denied: the emitter picks the action at runtime
    P("card_photo_batch.created", gettext_noop("Bulk card photo upload started"),
      ("batch_id", "holder_kind", "event_id", "holders_consented", "remove_backgrounds")),
    P("card_photo_batch.applied", gettext_noop("Bulk card photo upload applied"),
      ("batch_id", "holder_kind", "count")),
    P("card_photo_batch.item_applied", gettext_noop("Bulk upload photo attached to a card"),
      ("batch_id", "item_id", "card_id", "holder_kind")),
    P("card_photo_batch.finished", gettext_noop("Bulk card photo upload finished"),
      ("batch_id", "holder_kind", "applied", "skipped", "failed")),
    P("card_photo_batch.cancelled", gettext_noop("Bulk card photo upload cancelled"), ("batch_id", "holder_kind")),
)
