"""Phase 2 events lane: account-linked speaker identity is source-local and DROP on import.

A speaker row binds a source account to a source event; the target re-assigns or re-invites
its speakers, exactly as event staff grants are reissued. Its User edges never expand the
portable user closure.
"""

FIELD_NAMES = {
    "events.EventSpeaker": frozenset("id makerspace event user section display_name linked_via grants_check_in claim_token_digest claim_expires_at claimed_at assigned_by removed_at removed_by created_at".split()),
}
OMITTED_MODELS = {"events.EventSpeaker": "Account-linked speaker credit and its claim credential are reissued on the target; never portable."}
USER_FIELDS = frozenset({
    ("events.EventSpeaker", "user"),
    ("events.EventSpeaker", "assigned_by"),
    ("events.EventSpeaker", "removed_by"),
})
EXCLUDED_USER_EDGE_REASONS = {edge: OMITTED_MODELS["events.EventSpeaker"] for edge in USER_FIELDS}
