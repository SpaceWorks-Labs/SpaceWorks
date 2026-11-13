"""The staff number scheme (O-B4 part 2): separate from the member-card schemes, same token grammar.

`{PREFIX}`, `{SEQ:n}` (required, once), `{YYYY}`/`{YY}`; unit and member tokens make no sense on a staff card.
Without a saved scheme a space numbers staff cards `STF-0001`. The counter lives in `CardNumberCounter` under
the scheme key `staff`, so it never collides with a member scheme.
"""
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from . import numbering
from .models_numbering import CardNumberCounter
from .models_staff_cards import StaffCard, StaffCardNumbering

SCHEME_KEY = "staff"
DEFAULT = ("STF", "{PREFIX}-{SEQ:4}")
_FORBIDDEN = ("{MEMBER", "{UNIT}", "{U1}", "{U2}", "{U3}", "{U4}")


def validate(prefix, pattern):
    prefix, pattern = numbering.validate(prefix, pattern)
    if any(token in pattern for token in _FORBIDDEN):
        raise ValidationError({"pattern": gettext("Staff numbers use {PREFIX}, {SEQ}, {YYYY} and {YY} only.")})
    return prefix, pattern


def current(makerspace_id):
    row = StaffCardNumbering.objects.filter(makerspace_id=makerspace_id).exclude(pattern="").first()
    return (row.prefix, row.pattern) if row else DEFAULT


def save(makerspace, prefix, pattern):
    prefix, pattern = validate(prefix, pattern)
    row, _created = StaffCardNumbering.objects.update_or_create(
        makerspace=makerspace, defaults={"prefix": prefix, "pattern": pattern})
    return row


def next_number(membership):
    """Allocate the next free staff number. Runs inside the issue transaction (the membership row is locked)."""
    space = membership.makerspace
    prefix, pattern = current(space.pk)
    now = timezone.now().astimezone(ZoneInfo(space.timezone or "UTC"))
    year = now.year if numbering.has_year(pattern) else 0
    with transaction.atomic():
        CardNumberCounter.objects.get_or_create(makerspace_id=space.pk, scheme_key=SCHEME_KEY, year=year)
        counter = CardNumberCounter.objects.select_for_update().get(
            makerspace_id=space.pk, scheme_key=SCHEME_KEY, year=year)
        for _ in range(numbering.MAX_ATTEMPTS):
            text = numbering.render(pattern, prefix=prefix, seq=counter.next_value, year=now.year)
            counter.next_value += 1
            if not StaffCard.objects.filter(makerspace_id=space.pk, number_text=text).exists():
                counter.save(update_fields=["next_value"])
                return text
        counter.save(update_fields=["next_value"])
    raise numbering.CardNumberExhausted({"detail": gettext("No free card number was found; change the numbering pattern.")})
