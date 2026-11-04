"""0054's replacement body for ``accounts_guard_device_context`` (#173, lane L21b).

Adds the ``event`` authority: a step-up on a person limited to one event. It carries no staff
tenant, names its event (immutable provenance, like the staff tenant), needs attestation and the
same enabled factor or passkey a staff grant needs, and a space-locked app registration must belong
to the event's space. Whether the person still holds a live event role is checked in Python on every
request and refresh (``services_event_grants``), exactly like the staff role. The reverse restores
0051's body exactly.
"""

from ._0051_passkey_device_guard import AFTER as BEFORE, _FACTOR_OR_PASSKEY


def _swap(text, old, new):
    assert text.count(old) == 1, f"0051's device-context body moved; re-derive 0054 ({old[:40]!r})."
    return text.replace(old, new)


AFTER = _swap(BEFORE, "NEW.environment, NEW.signing_identity, NEW.attestation_subject_fingerprint,\n"
                      "               NEW.attestation_key_id, NEW.attestation_public_key, NEW.attested_at)",
              "NEW.environment, NEW.signing_identity, NEW.attestation_subject_fingerprint,\n"
              "               NEW.attestation_key_id, NEW.attestation_public_key, NEW.attested_at, NEW.event_id)")
AFTER = _swap(AFTER, "OLD.environment, OLD.signing_identity, OLD.attestation_subject_fingerprint,\n"
                     "               OLD.attestation_key_id, OLD.attestation_public_key, OLD.attested_at)",
              "OLD.environment, OLD.signing_identity, OLD.attestation_subject_fingerprint,\n"
              "               OLD.attestation_key_id, OLD.attestation_public_key, OLD.attested_at, OLD.event_id)")
AFTER = _swap(AFTER, "NEW.authority NOT IN ('member', 'staff')", "NEW.authority NOT IN ('member', 'staff', 'event')")
AFTER = _swap(AFTER, "OR (NEW.authority = 'member') <> (NEW.staff_makerspace_id IS NULL)",
              "OR (NEW.authority = 'staff') <> (NEW.staff_makerspace_id IS NOT NULL)\n"
              "       OR (NEW.authority = 'event') <> (NEW.event_id IS NOT NULL)")
_EVENT_BLOCK = (
    "    -- #173: an event grant is a step-up limited to one event: attestation, a factor, and a\n"
    "    -- space-locked registration only for that event's space. The live role is checked per request.\n"
    "    IF NEW.authority = 'event' AND (\n"
    "       NEW.signing_identity = '' OR NEW.attestation_subject_fingerprint = ''\n"
    "       OR NOT EXISTS (SELECT 1 FROM events_event WHERE id = NEW.event_id)\n"
    "       OR registration.makerspace_id IS NOT NULL\n"
    "          AND registration.makerspace_id <> (SELECT makerspace_id FROM events_event WHERE id = NEW.event_id)\n"
    + _FACTOR_OR_PASSKEY +
    "    ) THEN\n"
    "        RAISE EXCEPTION 'Native event authority requires its event, a factor and attestation'\n"
    "            USING ERRCODE = '23514';\n"
    "    END IF;\n"
    "    RETURN NEW;\nEND $$;"
)
AFTER = _swap(AFTER, "    RETURN NEW;\nEND $$;", _EVENT_BLOCK)
