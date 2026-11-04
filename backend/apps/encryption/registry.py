"""Fixed, query-free allowlist for the narrow scoped-PII boundary."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PiiField:
    model_label: str
    field_name: str
    makerspace_path: str | None
    max_length: int | None
    classification: str
    index_kind: str
    encryption_required: bool = False


def _fields(label, names, path, classification, indexes):
    return tuple(
        PiiField(label, name, path, limit, classification, index)
        for name, limit, index in zip(names, indexes[0], indexes[1], strict=True)
    )


from .registry_7b import printer_pii_fields
from .registry_p2_bookings import booking_departure_pii_fields
from .registry_events_programme import programme_pii_fields
from .registry_reimbursements import reimbursement_pii_fields
from .registry_r2_l4 import membership_lifecycle_pii_fields
from .registry_r2_l16 import repairs_pii_fields
from .registry_r2_l3 import id_card_pii_fields
from .registry_r2_l6 import ticketing_pii_fields
from .registry_r2_l18 import donation_pii_fields

SOURCE_FIELDS = (
    *_fields("integrations.MessagingConsent", ("phone_e164",), "makerspace_id", "source", ((32,), ("none",))),
    *reimbursement_pii_fields(PiiField),
    *programme_pii_fields(PiiField),
    *printer_pii_fields(PiiField),
    *booking_departure_pii_fields(PiiField),
    *membership_lifecycle_pii_fields(PiiField),
    *repairs_pii_fields(PiiField),
    *id_card_pii_fields(PiiField),
    *ticketing_pii_fields(PiiField),
    *donation_pii_fields(PiiField),
    *_fields("hardware_requests.HardwareRequest", ("requester_username", "requester_name", "requester_contact_email", "requester_contact_phone"), "makerspace_id", "source", ((150, 200, 254, 32), ("none", "bloom", "bloom_exact", "none"))),
    *_fields("events.EventRegistration", ("name", "email", "phone"), "event.makerspace_id", "source", ((200, 254, 32), ("none", "event_exact", "none"))),
    *_fields("events.EventFeedbackResponse", ("answers_snapshot",), "survey.event.makerspace_id", "source", ((None,), ("none",))),
    *_fields("events.EventAttendanceCertificate", ("recipient_name",), "event.makerspace_id", "source", ((None,), ("none",))),
    *_fields("makerspaces.MemberCard", ("printed_name",), "makerspace_id", "source", ((200,), ("none",))),
    *_fields("makerspaces.InvitationRequest", ("name", "email", "phone"), "makerspace_id", "source", ((200, 254, 32), ("none", "none", "none"))),
    *_fields("makerspaces.MembershipRequest", ("application_answers",), "makerspace_id", "source", ((None,), ("none",))),
    *_fields("bookings.Booking", ("name", "email", "phone", "note"), "space.makerspace_id", "source", ((200, 254, 32, None), ("none", "none", "none", "none"))),
    *_fields("machines.MachineServiceRequest", ("requester_name", "contact_email", "contact_phone", "collected_by_name"), "makerspace_id", "source", ((None, None, None, None), ("bloom", "bloom_exact", "none", "none"))),
    *_fields("machines.MachineUsageEntry", ("requester_name", "contact_email", "contact_phone", "note"), "machine.makerspace_id", "source", ((120, 254, 40, None), ("bloom", "bloom_exact", "none", "none"))),
)

SECONDARY_FIELDS = _fields(
    "integrations.EmailLog", ("to_email", "subject", "text_body", "html_body"),
    "makerspace_id", "secondary", ((255, 255, None, None), ("none",) * 4),
) + _fields(
    "notifications.NotificationInboxRow", ("title", "summary"),
    "makerspace_id", "secondary", ((None, None), ("none", "none")),
)
SECONDARY_FIELDS += _fields("notifications.MemberBroadcast", ("title", "body"),
                            "makerspace_id", "secondary", ((None, None), ("none", "none")))
SECONDARY_FIELDS += _fields("events.EventBroadcast", ("subject", "body"),
                            "makerspace_id", "secondary", ((None, None), ("none", "none")))
SECONDARY_FIELDS += _fields("bookings.BookingBroadcast", ("subject", "body"),
                            "makerspace_id", "secondary", ((None, None), ("none", "none")))
SECONDARY_FIELDS += _fields("integrations.NotificationEnvelope", ("message_body",),
                            "makerspace_id", "secondary", ((None,), ("none",)))
SECONDARY_FIELDS += _fields("integrations.NotificationEndpoint", ("destination", "provider_subject"),
                            "makerspace_id", "secondary", ((None, None), ("none", "none")))
SECONDARY_FIELDS += _fields("integrations.NotificationEndpointChallenge", ("candidate_destination",),
                            "makerspace_id", "secondary", ((None,), ("none",)))
# Cutover ingress.payload, legacy_mapping.snapshot and credential_version.credentials
# use deployment encrypt_value/decrypt_value in models_cutover. They deliberately
# stay outside scoped PII backfill: receipts/verifiers must survive tenant purge.
ALL_FIELDS = SOURCE_FIELDS + SECONDARY_FIELDS
BY_MODEL = {}
for _field in ALL_FIELDS:
    BY_MODEL.setdefault(_field.model_label, []).append(_field)
BY_MODEL = {label: tuple(fields) for label, fields in BY_MODEL.items()}


def fields_for_label(model_label):
    """Accessor for callers holding a label rather than a model.

    Call this instead of importing ``BY_MODEL``. A module-level ``from ... import
    BY_MODEL`` binds whatever the map contained at import time, which stops being
    the truth the moment registration becomes per-app (plan B2).
    """
    return BY_MODEL.get(model_label, ())


def all_fields():
    """Accessor for the full field list; see ``fields_for_label`` for why."""
    return ALL_FIELDS


def registered_labels():
    """Accessor for every mapped model label; see ``fields_for_label`` for why."""
    return tuple(BY_MODEL)


def register_retained_pii(prefix):
    """Publish package mappings even when its operational app is tombstoned."""
    from apps.separability.registry import register_pii_fields, registered_pii_models

    already = registered_pii_models()
    for label in registered_labels():
        if label.startswith(prefix) and label not in already:
            register_pii_fields(label, fields_for_label(label))


def fields_for(model_or_instance):
    meta = model_or_instance._meta
    return BY_MODEL.get(meta.label, ())


def field_for(model_or_instance, name):
    return next((item for item in fields_for(model_or_instance) if item.field_name == name), None)


def makerspace_id_for(instance, field):
    """Resolve only the registry-declared tenant relationship, never a fallback."""
    if field.makerspace_path == "makerspace_id":
        return instance.makerspace_id
    current = instance
    for component in field.makerspace_path.split("."):
        current = getattr(current, component)
    return current
