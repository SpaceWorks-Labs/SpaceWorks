"""Card number schemes: tokens, validation and the gap-free counter (O-B4, parity C4).

Tokens: `{PREFIX}`, `{SEQ}`/`{SEQ:n}` (required, once), `{MEMBER}`/`{MEMBER:n}` (the membership number),
`{YYYY}`/`{YY}` (space timezone; the counter restarts each year), `{UNIT}` and `{U1}`..`{U4}` (unit codes;
`NA` while a member has none). Uppercase only, literals `A-Z0-9 ./_-`, longest output 32 characters.
A card's number is frozen on `MemberCard.number_text` at issue; reissue and renewal keep it. There is ONE
member card per member (space and organisation membership are the same card), so one scheme set serves it.
"""
import re
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from .models_numbering import CardNumberCounter, CardNumberScheme

MAX_LENGTH = 32
MAX_ATTEMPTS = 50
_TOKEN = re.compile(r"\{(PREFIX|SEQ|MEMBER|YYYY|YY|UNIT|U[1-4])(?::(\d{1,2}))?\}")
_LITERAL = re.compile(r"^[A-Z0-9 ./_-]*$")
_PREFIX = re.compile(r"^[A-Z0-9]{2,6}$")
UNIT_WIDTH = 8
_WIDTH_TOKENS = ("SEQ", "MEMBER")


class CardNumberExhausted(ValidationError):
    status_code = 409
    default_code = "card_number_exhausted"


def has_year(pattern):
    return any(m.group(1) in ("YYYY", "YY") for m in _TOKEN.finditer(pattern or ""))


def render(pattern, *, prefix="", seq=1, member=None, year=None, units=()):
    """Fill every token. `units` is the unit code chain, outermost first."""
    def fill(match):
        name, width = match.group(1), match.group(2)
        if name == "PREFIX":
            return prefix
        if name == "SEQ":
            return f"{seq:0{int(width or 1)}d}"
        if name == "MEMBER":
            return f"{member or 0:0{int(width or 1)}d}"
        if name == "YYYY":
            return f"{year:04d}"
        if name == "YY":
            return f"{year % 100:02d}"
        if name == "UNIT":
            return (units[-1] if units else "NA")[:UNIT_WIDTH]
        index = int(name[1]) - 1
        return (units[index] if index < len(units) else "NA")[:UNIT_WIDTH]
    return _TOKEN.sub(fill, pattern)


def validate(prefix, pattern):
    """-> (prefix, pattern) cleaned; an empty pattern means "no scheme" and is allowed."""
    prefix, pattern = (prefix or "").strip().upper(), (pattern or "").strip().upper()
    if prefix and not _PREFIX.match(prefix):
        raise ValidationError({"prefix": gettext("Use 2 to 6 capital letters or digits.")})
    if not pattern:
        return prefix, ""
    tokens = list(_TOKEN.finditer(pattern))
    if sum(1 for m in tokens if m.group(1) == "SEQ") != 1:
        raise ValidationError({"pattern": gettext("Use {SEQ} or {SEQ:n} exactly once.")})
    if any(m.group(2) and m.group(1) not in _WIDTH_TOKENS for m in tokens):
        raise ValidationError({"pattern": gettext("Only {SEQ} and {MEMBER} take a width.")})
    if any(m.group(1) == "PREFIX" for m in tokens) and not prefix:
        raise ValidationError({"prefix": gettext("Add a prefix, or remove {PREFIX} from the pattern.")})
    if not _LITERAL.match(_TOKEN.sub("", pattern)):
        raise ValidationError({"pattern": gettext("Use capital letters, digits, spaces and . / _ - around the tokens.")})
    longest = render(pattern, prefix=prefix, seq=10 ** 6 - 1, member=10 ** 6 - 1, year=2099,
                     units=("X" * UNIT_WIDTH,) * 4)
    if len(longest) > MAX_LENGTH:
        raise ValidationError({"pattern": gettext("A number can be at most {n} characters long.").format(n=MAX_LENGTH)})
    return prefix, pattern


def preview(prefix, pattern, count=3):
    """Three sample numbers for the settings screen."""
    year = timezone.now().year
    if not pattern:
        return []
    return [render(pattern, prefix=prefix, seq=i + 1, member=i + 1, year=year, units=("NA",) * 4)
            for i in range(count)]


def scheme_for(makerspace_id, title_id=None):
    """The live scheme a new card follows: the primary title's, then the space default; None = legacy."""
    rows = CardNumberScheme.objects.filter(makerspace_id=makerspace_id).exclude(pattern="")
    if title_id:
        row = rows.filter(title_id=title_id).first()
        if row is not None:
            return row
    return rows.filter(title__isnull=True).first()


def unit_codes(membership):
    """The member's unit code chain, outermost first (`NA` fills the missing levels); empty without units."""
    from .unit_chain import codes
    return codes(membership)


def next_number(membership, scheme):
    """Allocate and return the next free number for `membership` under `scheme`.

    Runs inside the issue transaction, which already holds the makerspace/membership lock. The counter
    row is locked with `select_for_update`; no advisory lock. Skips numbers already printed (50 attempts).
    """
    from apps.makerspaces.models import MemberCard
    space = membership.makerspace
    now = timezone.now().astimezone(ZoneInfo(space.timezone or "UTC"))
    year = now.year if has_year(scheme.pattern) else 0
    with transaction.atomic():
        CardNumberCounter.objects.get_or_create(makerspace_id=space.pk, scheme_key=scheme.key, year=year)
        counter = CardNumberCounter.objects.select_for_update().get(
            makerspace_id=space.pk, scheme_key=scheme.key, year=year)
        for _ in range(MAX_ATTEMPTS):
            text = render(scheme.pattern, prefix=scheme.prefix, seq=counter.next_value,
                          member=membership.member_number, year=now.year, units=unit_codes(membership))
            counter.next_value += 1
            if not MemberCard.objects.filter(makerspace_id=space.pk, number_text=text).exists():
                counter.save(update_fields=["next_value"])
                return text
        counter.save(update_fields=["next_value"])
    raise CardNumberExhausted({"detail": gettext("No free card number was found; change the numbering pattern.")})
