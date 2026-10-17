"""Media-fetch capabilities belong to the issuing deployment only."""

from .unique_values_policy import UniqueValueDisposition, _policy


NOTIFICATION_MEDIA_UNIQUE_RULES = {
    ("integrations.NotificationMediaGrant", "field:token_digest"): _policy(
        UniqueValueDisposition.DROP_ROW,
        "Single-use document delivery authority never travels to a target deployment.",
    ),
}
