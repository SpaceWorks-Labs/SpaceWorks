"""The public join page (SPEC §5.2): a signed-in, active account asks for a card.

The email comes from the account, never the form; one request per account or email;
the photo follows the programme's photo mode. (Saved-details prefill is bound to event
form contexts today, so programme answers are typed; the name comes from the account.)
With approval off the card is approved straight away. A holder needs no membership of the
host space (Q-I7).
"""
import uuid

from django.db import transaction
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.card_designs.images import ALLOWED, MAX_UPLOAD_BYTES

from .cards import add
from .models import IdProgramme, IdProgrammeCard


def open_programmes(organization_slug):
    from apps.card_designs.switches import programmes_on
    rows = IdProgramme.objects.filter(organization__slug=organization_slug, organization__is_active=True,
                                      status="active").select_related("organization", "makerspace")
    return [row for row in rows if programmes_on(row.makerspace)]


def programme_by_slug(organization_slug, slug):
    row = next((item for item in open_programmes(organization_slug) if item.slug == slug), None)
    if row is None:
        raise NotFound()
    return row


def require_joiner(user):
    if not user.is_authenticated or not user.is_active or getattr(user, "access_status", "active") != "active":
        raise PermissionDenied("Sign in with an active account to join.")


def photo_key(programme):
    return f"card-photos/{programme.makerspace_id}/{uuid.uuid4().hex}"


def presign_photo(programme, content_type):
    from apps.card_designs.storage import presign_staging
    if programme.photo_mode == "none":
        raise ValidationError({"detail": "This programme does not take photos."})
    if content_type not in ALLOWED:
        raise ValidationError({"content_type": "Upload a PNG, JPEG or WebP photo."})
    key = photo_key(programme)
    return {"object_key": key, "content_type": content_type, **presign_staging(key, content_type, MAX_UPLOAD_BYTES)}


@transaction.atomic
def join(user, programme, *, answers, photo_object_key="", photo_consent=False):
    from apps.card_designs.photos import finalize
    require_joiner(user)
    if not programme.registration_open:
        raise ValidationError({"detail": "This programme is not taking requests right now."})
    if IdProgrammeCard.objects.filter(programme=programme, user=user).exists():
        raise ValidationError({"detail": "You already asked to join this programme."})
    if programme.photo_mode == "required" and not photo_object_key:
        raise ValidationError({"photo": "This programme needs a photo."})
    name = user.display_name or user.get_full_name() or user.username
    card = add(user, programme, name=name, email=user.email, answers=answers, source=IdProgrammeCard.Source.FORM,
               user=user)
    if photo_object_key:
        finalize(user, "programme_card", card, object_key=photo_object_key, consent=photo_consent)
        card.refresh_from_db()
    return card

