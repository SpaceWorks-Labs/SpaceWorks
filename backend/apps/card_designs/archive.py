"""Removing a card-design override (owner decision 219(h)).

Only overrides can be removed -- the space default is reset, never removed. An override
that was never published reached no holder, so it is hard-deleted. One that was ever
published is ARCHIVED instead: `archived_at` is set, resolution skips it (holders fall
back to the next design in the chain), and its revision and approval history stays.
Asking for the same target's design again (`resolution.get_or_create`) restores it.
"""
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.exceptions import APIException, ValidationError

from apps.audit import services as audit

from .models import CardDesign


class ArchiveInstead(APIException):
    status_code = 409
    default_code = "archive_instead"
    default_detail = {"code": "archive_instead",
                      "detail": "This design was published to holders. Archive it instead of deleting it."}


def is_override(design):
    return bool(design.plan_id or design.title_id or design.ticket_type_id or
                (design.event_id and design.domain in (CardDesign.Domain.EVENT_CARD, CardDesign.Domain.EVENT_TICKET)))


def was_used(design):
    return design.published_revision is not None or design.published_at is not None


def _require_override(design):
    if not is_override(design):
        raise ValidationError({"detail": gettext("The default design cannot be removed; reset it instead.")})


@transaction.atomic
def delete(actor, design):
    _require_override(design)
    design = CardDesign.objects.select_for_update().get(pk=design.pk)
    if was_used(design):
        raise ArchiveInstead()
    audit.record(actor, "card_design.deleted", makerspace=design.makerspace, target=design,
                 meta={"design_id": design.pk, "domain": design.domain})
    design.delete()


@transaction.atomic
def archive(actor, design):
    _require_override(design)
    design = CardDesign.objects.select_for_update().get(pk=design.pk)
    if design.archived_at is None:
        design.archived_at = timezone.now()
        design.save(update_fields=["archived_at", "updated_at"])
        audit.record(actor, "card_design.archived", makerspace=design.makerspace, target=design,
                     meta={"design_id": design.pk, "domain": design.domain})
    return design


@transaction.atomic
def unarchive(actor, design):
    design = CardDesign.objects.select_for_update().get(pk=design.pk)
    if design.archived_at is not None:
        design.archived_at = None
        design.save(update_fields=["archived_at", "updated_at"])
        audit.record(actor, "card_design.unarchived", makerspace=design.makerspace, target=design,
                     meta={"design_id": design.pk, "domain": design.domain})
    return design
