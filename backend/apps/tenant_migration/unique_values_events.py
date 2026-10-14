"""Event access-code uniqueness follows target-owned credential reconstruction."""

from .unique_values_policy import REMAP, _policy


# EventStaffGrant partial unique keys and EventStaffGrantInvite.token_digest need no
# materialization rule: both entire models are DROP, so no source credential is inserted.
EVENT_UNIQUE_RULES = {
    ("events.EventInvite", "event_invite_unique_code"): _policy(
        REMAP,
        "The event FK is remapped and the source code digest is replaced; the "
        "imported invitation is revoked before it can grant target admission.",
    ),
    ("events.EventPromoCode", "event_promo_unique_code"): _policy(
        REMAP,
        "The event FK is remapped and the source code digest is replaced; the "
        "imported promotion is revoked before it can grant target discounts.",
    ),
}
