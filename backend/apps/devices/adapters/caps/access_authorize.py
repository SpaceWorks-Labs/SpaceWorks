from ..capability import Capability
from ..schema import CODE, EPOCH, UUID, num, obj, text

# card_qr identifies (the member card's desk QR, never a public check link) and must come with the member's ``pin``;
# a PIN alone needs ``member_number`` (lead 1, SECFIX-A).
CREDENTIAL = obj({"type": {"type": "string", "enum": ["card_qr", "nfc", "pin"]}, "value": text(256, minLength=1),
                  "member_number": text(40), "pin": text(12, minLength=1)}, ["type", "value"])
REQUEST = obj({"binding_id": UUID, "credential": CREDENTIAL}, ["binding_id", "credential"])
RESPONSE = obj({"allowed": {"type": "boolean"}, "decision": {"type": "string", "enum": ["allowed", "denied"]},
                "reason": CODE, "detail": {"type": "string", "maxLength": 200}, "max_seconds": num(0, 86400 * 2, "integer"), "session_id": num(1, 2 ** 62, "integer"),
                "time_limit_seconds": num(0, 86400 * 2, "integer"), "expires_at": EPOCH}, ["allowed", "reason"])
# Reason codes mirror machines.sessions_rules.SessionRefused codes plus the adapter-specific ones.
# Decision 319: `no_machine_access` / `machine_access_expired` replaced `certification_required`; a space
# manager's grant (machines.access_grants.can_use) decides, never a certification.
REASONS = ("ok", "unknown_credential", "credential_locked", "member_restricted", "membership_required",
           "waiver_acceptance_required", "presence_required", "no_machine_access", "machine_access_expired", "machine_unavailable",
           "machine_in_use", "session_already_live", "locked_out", "sessions_off", "capability_missing",
           "area_not_clear", "booking_conflict", "unsupported_target", "credential_disabled", "too_many_attempts",
           "booking_required", "booked_by_other", "outside_opening_hours", "supervision_required",
           "maintenance_lockout", "out_of_order", "clear_confirmation_pending", "interlock_open", "filter_alert",
           "internal_error_fail_closed", "session_closed", "pin_required")
# Every member-level credential failure (unknown card/number/tag, no PIN, wrong PIN, locked or disabled credential)
# answers ``unknown_credential``; ``credential_locked`` and ``credential_disabled`` stay in the enum for old bridges
# but are no longer sent. ``too_many_attempts`` means this binding or space is cooling down (decision 336j).
CAPABILITY = Capability(
    "access.authorize", "Member authorises at the machine; the server decides with the existing rules.",
    targets=("machine", "door", "space"), routes=("POST access/authorize",), switch="machines.integrations.access",
)
