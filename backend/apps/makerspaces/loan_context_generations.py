"""Internal concurrency generations for optional loan contexts."""
from uuid import UUID, uuid4
from django.core.exceptions import ValidationError
from django.utils.translation import gettext

DOMAINS = frozenset(("events", "bookings"))


def new_generations():
    return {name: str(uuid4()) for name in sorted(DOMAINS)}


def validate_generations(value):
    if not isinstance(value, dict) or set(value) != DOMAINS:
        raise ValidationError(gettext("Loan-context generations have an invalid shape."))
    tokens = []
    for name in sorted(DOMAINS):
        raw = value[name]
        try:
            parsed = UUID(raw) if isinstance(raw, str) else None
        except ValueError as exc:
            raise ValidationError(gettext("Loan-context generation is invalid.")) from exc
        if parsed is None or parsed.version != 4 or str(parsed) != raw:
            raise ValidationError(gettext("Loan-context generation is invalid."))
        tokens.append(raw)
    if tokens[0] == tokens[1]:
        raise ValidationError(gettext("Loan-context generations must be distinct."))


def rotate(locked_makerspace, domains=DOMAINS):
    if not domains or not set(domains) <= DOMAINS:
        raise ValueError("Unknown loan-context domain.")
    value = dict(locked_makerspace.loan_context_generations)
    validate_generations(value)
    for name in sorted(domains):
        value[name] = str(uuid4())
    validate_generations(value)
    locked_makerspace.loan_context_generations = value
    locked_makerspace.save(update_fields=["loan_context_generations"])
