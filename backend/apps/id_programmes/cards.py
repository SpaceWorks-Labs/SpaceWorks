"""Programme cards: add, edit, delete, and the bulk decisions (SPEC §5.2).

Decisions: approve (numbered, expiry set), reject (private reason), revoke (private
reason), reinstate (keeps number and old expiry, Q8), renew (expiry from now). At most
500 cards per decision. Reasons are encrypted on the row, never in audit meta.
"""
from django.utils.translation import gettext
import json

from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.card_designs.lifecycle import on_issue, on_reissue, on_revoke

from .models import IdProgramme, IdProgrammeCard
from .numbering import assign, expiry_for
from .questions import validate_answers

MAX_DECISION = 500
ACTIONS = ("approve", "reject", "revoke", "reinstate", "renew")


def email_digest(email):
    from apps.encryption.blind_index import canonical_email
    value = canonical_email(email)
    return salted_hmac("id_programmes.email", value).hexdigest() if value else ""


def _store_answers(programme, raw):
    return json.dumps(validate_answers(programme.form_schema, raw), separators=(",", ":"))


@transaction.atomic
def add(actor, programme, *, name, email, answers=None, source=IdProgrammeCard.Source.MANUAL, user=None):
    name, email = (name or "").strip(), (email or "").strip().lower()
    if not 1 <= len(name) <= 120:
        raise ValidationError({"name": gettext("Give a name of up to 120 characters.")})
    digest = email_digest(email)
    if digest and IdProgrammeCard.objects.filter(programme=programme, email_digest=digest).exists():
        raise ValidationError({"email": gettext("This person is already in the programme.")})
    if user is not None and IdProgrammeCard.objects.filter(programme=programme, user=user).exists():
        raise ValidationError({"detail": gettext("You already asked to join this programme.")})
    card = IdProgrammeCard.objects.create(programme=programme, makerspace=programme.makerspace, user=user, name=name,
                                          email=email, email_digest=digest, source=source,
                                          answers=_store_answers(programme, answers or {}))
    if source == IdProgrammeCard.Source.FORM:
        audit.record(actor, "id_programme.card_requested", makerspace=programme.makerspace, target=card,
                     meta={"programme_id": programme.pk, "card_id": card.pk})
    else:
        audit.record(actor, "id_programme.card_added", makerspace=programme.makerspace, target=card,
                     meta={"programme_id": programme.pk, "card_id": card.pk})
    if not programme.requires_approval and source == IdProgrammeCard.Source.FORM:
        decide(actor, programme, "approve", [card.pk])
        card.refresh_from_db()
    return card


@transaction.atomic
def edit(actor, card, values):
    fields = []
    if "name" in values:
        card.name = values["name"].strip()[:120]
        fields.append("name")
    if "answers" in values:
        card.answers = _store_answers(card.programme, values["answers"])
        fields.append("answers")
    if fields:
        card.save(update_fields=[*fields, "updated_at"])
        audit.record(actor, "id_programme.card_updated", makerspace=card.makerspace, target=card,
                     meta={"card_id": card.pk, "fields": fields})
    return card


@transaction.atomic
def delete(actor, card):
    from apps.card_designs.photos import remove
    if card.photo_object_key:
        remove(actor, "programme_card", card)
    on_revoke("programme_card", card)
    audit.record(actor, "id_programme.card_deleted", makerspace=card.makerspace, target=card,
                 meta={"card_id": card.pk, "programme_id": card.programme_id})
    card.delete()


def _apply(card, action, now, reason):
    if action == "approve" and card.status in ("pending", "rejected"):
        card.status, card.issued_at = "approved", now
        card.expires_at = expiry_for(card.programme, now)
        return True
    if action == "reject" and card.status == "pending":
        card.status, card.status_reason = "rejected", reason
        return True
    if action == "revoke" and card.status == "approved":
        card.status, card.revoked_at, card.status_reason = "revoked", now, reason
        return True
    if action == "reinstate" and card.status == "revoked":
        card.status, card.revoked_at, card.status_reason = "approved", None, ""
        return True
    if action == "renew" and card.status == "approved":
        card.expires_at = expiry_for(card.programme, now)
        return True
    return False


@transaction.atomic
def decide(actor, programme, action, ids, reason=""):
    if action not in ACTIONS:
        raise ValidationError({"action": gettext("Unknown decision.")})
    if not 1 <= len(ids) <= MAX_DECISION:
        raise ValidationError({"ids": gettext('Choose 1-{MAX_DECISION} cards.').format(MAX_DECISION=MAX_DECISION)})
    if action in ("reject", "revoke") and not (reason or "").strip():
        raise ValidationError({"reason": gettext("Give a reason (it stays private to staff).")})
    programme = IdProgramme.objects.select_for_update().get(pk=programme.pk)
    now = timezone.now()
    cards = list(IdProgrammeCard.objects.select_for_update().filter(programme=programme, pk__in=ids))
    changed = [card for card in cards if _apply(card, action, now, (reason or "").strip()[:300])]
    if action == "approve":
        assign(programme, changed, now)
    for card in changed:
        card.save()
        if action == "approve":
            on_issue("programme_card", card)
        elif action == "reinstate":
            on_reissue("programme_card", card)
        elif action == "revoke":
            on_revoke("programme_card", card)
    past = {"approve": "approved", "reject": "rejected", "revoke": "revoked", "reinstate": "reinstated",
            "renew": "renewed"}[action]
    if past == "approved":
        audit.record(actor, "id_programme.cards_approved", makerspace=programme.makerspace, target=programme, meta={"programme_id": programme.pk, "count": len(changed)})
    elif past == "rejected":
        audit.record(actor, "id_programme.cards_rejected", makerspace=programme.makerspace, target=programme, meta={"programme_id": programme.pk, "count": len(changed)})
    elif past == "revoked":
        audit.record(actor, "id_programme.cards_revoked", makerspace=programme.makerspace, target=programme, meta={"programme_id": programme.pk, "count": len(changed)})
    elif past == "reinstated":
        audit.record(actor, "id_programme.cards_reinstated", makerspace=programme.makerspace, target=programme,
                     meta={"programme_id": programme.pk, "count": len(changed)})
    else:
        audit.record(actor, "id_programme.cards_renewed", makerspace=programme.makerspace, target=programme, meta={"programme_id": programme.pk, "count": len(changed)})
    if action in ("approve", "reject"):
        from apps.card_designs.notifications import programme_decided
        for card in changed:
            transaction.on_commit(lambda pk=card.pk: programme_decided(pk), robust=True)
    return changed
