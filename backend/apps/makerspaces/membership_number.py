"""Gapless per-space member numbers and how they are printed (X12; #71, #128 C-29).

The number lives on the membership, not the card, so it survives card reissue,
revocation, rejoining and role changes. `assign` runs inside `_activate_membership`,
which already holds the makerspace row lock: every assignment in one space is
serialized behind it, so "highest + 1" never races and numbers never skip. The unique
constraint `uniq_makerspace_member_number` is the backstop. Memberships are never deleted
outside a tenant purge, so a number is never reused.

The printed form follows the space's pattern (`member_number_pattern`): `{number}` or
`{number:N}` (zero-padded to N digits, exactly once) and `{year}` (the year the person
first joined), around literal letters, digits and `- / _ .` -- e.g. `TNK-{number:4}`.
An empty pattern prints four digits.
"""
import re

from django.db.models import Max
from rest_framework.exceptions import ValidationError

SOURCES = {"approval": "join", "open": "join", "referral": "join", "claim": "join", "invite": "join",
           "join": "join", "walk_in": "manual", "staff_create": "manual", "manual": "manual",
           "import": "import"}
DEFAULT_PATTERN = "{number:4}"
_TOKEN = re.compile(r"\{(number(?::([1-8]))?|year)\}")
_LITERAL = re.compile(r"^[A-Za-z0-9\-/_. ]*$")


def validate_pattern(pattern):
    """Refuse a pattern without exactly one number token or with stray characters."""
    pattern = (pattern or "").strip()
    if not pattern:
        return ""
    numbers = [m for m in _TOKEN.finditer(pattern) if m.group(1).startswith("number")]
    if len(numbers) != 1:
        raise ValidationError({"member_number_pattern": "Use {number} or {number:N} exactly once."})
    if not _LITERAL.match(_TOKEN.sub("", pattern)):
        raise ValidationError({"member_number_pattern": "Use letters, digits, spaces and - / _ . around the tokens."})
    return pattern


def next_number(makerspace_id):
    from apps.makerspaces.models import MakerspaceMembership
    top = MakerspaceMembership.objects.filter(makerspace_id=makerspace_id).aggregate(top=Max("member_number"))["top"]
    return (top or 0) + 1


def assign(membership, *, source):
    """Give a membership its number and first source if it has none. Caller holds the
    makerspace lock. Returns the fields it changed."""
    fields = []
    if membership.member_number is None:
        membership.member_number = next_number(membership.makerspace_id)
        fields.append("member_number")
    if not membership.source and SOURCES.get(source):
        membership.source = SOURCES[source]
        fields.append("source")
    if fields:
        membership.save(update_fields=fields)
    return fields


def pattern_for(makerspace):
    from apps.makerspaces.models import MakerspaceMembershipSettings
    return MakerspaceMembershipSettings.objects.filter(makerspace=makerspace).values_list(
        "member_number_pattern", flat=True).first() or ""


def formatted(number, pattern="", year=None):
    """`TNK-0042` for pattern `TNK-{number:4}`; four digits for an empty pattern."""
    if number is None:
        return ""

    def token(match):
        if match.group(1) == "year":
            return str(year or "")
        return f"{number:0{int(match.group(2) or 1)}d}"

    return _TOKEN.sub(token, pattern or DEFAULT_PATTERN)


def display_number(membership, pattern=None):
    if pattern is None:
        pattern = pattern_for(membership.makerspace_id)
    # The membership row outlives revocation and rejoining, so its creation year is fixed.
    joined = membership.created_at
    return formatted(membership.member_number, pattern, joined.year if joined else None)
