"""The background-eraser processing notice and a member's opt-out (decision 345(b)).

A space that runs a background-removal service tells its members so, on the card photo upload and on its privacy
page, in one fixed text with a version. A member may opt out: their photo is then never sent to the eraser by anyone
(staff, bulk upload or themselves until they opt back in), any existing cut-out is deleted, and their card shows the
original photo. Every cut-out request stores the notice version that was in force (`CardPhotoCutout.notice_version`).

The opt-out is its own row (`CardPhotoEraserOptOut`) on the card that owns the photo (a staff card's photo is its member
card's), so it follows the photo, is purged with the card, travels with the space and is in the member's own export.
"""
from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit

NOTICE_VERSION = "2026-11-12"


def notice_text():
    return gettext("Card photos may be sent to this space's background-removal service, which cuts the person out of "
                   "the background for the card design. The original photo is always kept. You can opt out: your card "
                   "then always shows your original photo and your photo is never sent.")


class OptedOut(ValidationError):
    """Raised when someone asks to send an opted-out member's photo to the eraser."""
    default_code = "eraser_opted_out"

    def __init__(self):
        super().__init__({"detail": gettext("This member opted out of background removal; their original photo is used."),
                          "code": self.default_code})
        self.code = self.default_code


def _choice(kind, card):
    from .cutouts import owner
    from .models import CardPhotoEraserOptOut
    own = owner(kind, card)
    if own is None:
        return None, None
    return own, CardPhotoEraserOptOut.objects.filter(**{own[0]: own[1]}).first()


def opted_out(kind, card):
    return _choice(kind, card)[1] is not None


def refuse_if_opted_out(kind, card):
    if opted_out(kind, card):
        raise OptedOut()


def set_opt_out(actor, kind, card, value):
    """Opt the photo's owner out (deleting any cut-out) or back in; audited by id only."""
    from .cutouts import purge_row, row_for
    from .models import CardPhotoEraserOptOut
    own, row = _choice(kind, card)
    if own is None:
        raise ValidationError({"detail": gettext("Add a photo first.")})
    okind, ocard = own
    if value and row is None:
        CardPhotoEraserOptOut.objects.create(makerspace=ocard.makerspace, notice_version=NOTICE_VERSION, **{okind: ocard})
    elif not value and row is not None:
        row.delete()
    cutout = row_for(okind, ocard) if value else None
    if cutout is not None:
        purge_row(cutout)
    audit.record(actor, "card.photo_eraser_opted_out" if value else "card.photo_eraser_opted_in",
                 makerspace=ocard.makerspace, target=ocard, meta={"card_id": ocard.pk, "holder_kind": okind,
                                                                  "notice_version": NOTICE_VERSION})


def with_notice(kind, card, payload):
    """The cut-out status plus the notice the UI must show and the owner's choice."""
    return {**payload, "notice": notice_text(), "notice_version": NOTICE_VERSION, "opted_out": opted_out(kind, card)}


def privacy_section(makerspace):
    """Markdown appended to a space's public privacy page while its eraser can run; "" otherwise."""
    from .image_adapter import provider
    from .switches import cutout_on
    if makerspace is None or not cutout_on(makerspace) or not provider.configured(makerspace):
        return ""
    return "\n\n## " + gettext("Card photos and background removal") + "\n\n" + notice_text() + "\n"
