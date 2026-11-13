"""Programme card numbers `{PREFIX}-{YYYY}-{SEQ:4}` (#71, C-29) and expiry (SPEC §4.3).

The sequence never resets; the year is the approval year (Q9); numbers survive revoke
and reinstate; past 9999 the sequence simply widens. Assignment locks the programme
row, so concurrent approvals never share a number.
"""
from django.utils.translation import gettext
import re
from datetime import datetime, time, timedelta

from django.utils import timezone
from rest_framework.exceptions import ValidationError

PATTERN = "{PREFIX}-{YYYY}-{SEQ:4}"
PREFIX = re.compile(r"^[A-Z0-9]{2,6}$")


def prefix_from(name):
    letters = "".join(word[:1] for word in re.findall(r"[A-Za-z0-9]+", name)).upper()
    return (letters or "ID")[:6].ljust(2, "X")


def validate_prefix(value):
    if not isinstance(value, str) or not PREFIX.match(value):
        raise ValidationError({"id_prefix": gettext("Use 2-6 capital letters or digits.")})
    return value


def formatted(prefix, year, sequence, pattern=PATTERN):
    def token(match):
        name, width = match.group(1), match.group(2)
        if name == "PREFIX":
            return prefix
        if name == "YYYY":
            return str(year)
        return f"{sequence:0{int(width or 1)}d}"

    return re.sub(r"\{(PREFIX|YYYY|SEQ)(?::([1-8]))?\}", token, pattern)


def expiry_for(programme, issued_at):
    if programme.validity_mode == "fixed_date" and programme.valid_until:
        return timezone.make_aware(datetime.combine(programme.valid_until, time.max), timezone.get_current_timezone())
    if programme.validity_mode == "days" and programme.validity_days:
        return issued_at + timedelta(days=programme.validity_days)
    return None


def assign(programme, cards, now=None):
    """Number `cards` (approved now, oldest first); caller holds the programme row lock."""
    now = now or timezone.now()
    for card in sorted(cards, key=lambda row: (row.created_at, row.pk)):
        if card.id_number:
            continue
        card.sequence = programme.next_sequence
        card.id_number = formatted(programme.id_prefix, now.year, card.sequence)
        programme.next_sequence += 1
    programme.save(update_fields=["next_sequence", "updated_at"])
