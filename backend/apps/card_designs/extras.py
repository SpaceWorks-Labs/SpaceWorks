"""Opt-in sensitive extras: blood group and emergency contact (#132, Q-I5).

Only the holder reads or writes them, and only the printed card shows them, where
the design places them. They never appear in staff lists, exports (other than none),
reports, the public check, wallet passes or audit meta, and are deleted on revoke
and erasure. Organisers see them only behind the per-event switch (events/id_cards_views_settings.py).
"""
from django.utils.translation import gettext
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit

from .models import CardHolderExtras

CONSENT_VERSION = "2026-11"
BLOOD_GROUPS = ("", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")


def read(kind, card):
    row = CardHolderExtras.objects.filter(**{kind: card}).first()
    if row is None or row.consent_at is None:
        return {"opted_in": False, "blood_group": "", "emergency_contact_name": "", "emergency_contact_phone": ""}
    return {"opted_in": True, "blood_group": row.blood_group, "emergency_contact_name": row.emergency_contact_name,
            "emergency_contact_phone": row.emergency_contact_phone}


def write(actor, kind, card, *, opted_in, blood_group="", emergency_contact_name="", emergency_contact_phone=""):
    if not opted_in:
        deleted, _ = CardHolderExtras.objects.filter(**{kind: card}).delete()
        if deleted:
            audit.record(actor, "card.extras_optin_changed", makerspace=card.makerspace, target=card,
                         meta={"card_id": card.pk, "holder_kind": kind, "opted_in": False})
        return read(kind, card)
    if blood_group not in BLOOD_GROUPS:
        raise ValidationError({"blood_group": gettext("Choose a blood group from the list.")})
    if len(emergency_contact_name) > 80 or len(emergency_contact_phone) > 32:
        raise ValidationError({"emergency_contact": gettext("Keep the contact to a short name and one phone number.")})
    CardHolderExtras.objects.update_or_create(
        **{kind: card}, defaults={"makerspace_id": card.makerspace_id, "blood_group": blood_group,
                                  "emergency_contact_name": emergency_contact_name.strip(),
                                  "emergency_contact_phone": emergency_contact_phone.strip(),
                                  "consent_at": timezone.now(), "consent_version": CONSENT_VERSION})
    # Never the values: only that the holder changed their opt-in.
    audit.record(actor, "card.extras_optin_changed", makerspace=card.makerspace, target=card,
                 meta={"card_id": card.pk, "holder_kind": kind, "opted_in": True})
    return read(kind, card)
