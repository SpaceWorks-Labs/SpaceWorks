"""Constraint-backed usernames for credential-free person records."""

from collections.abc import Callable
from typing import TypeVar

from django.db import IntegrityError, transaction
from django.utils.crypto import get_random_string

ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
MAX_ATTEMPTS = 8

Created = TypeVar("Created")


class UsernameAllocationError(RuntimeError):
    """The bounded username namespace could not be allocated."""


def allocate_username(stem: str, *, create: Callable[[str], Created]) -> Created:
    """Create one row with a migration-compatible, collision-safe username.

    ``create`` performs the insert and receives the candidate username.  Each insert
    gets its own savepoint, so a uniqueness collision cannot poison a surrounding
    import transaction.
    """
    normalized = _normalize_stem(stem)
    with transaction.atomic():
        for _attempt in range(MAX_ATTEMPTS):
            username = f"walkin_{normalized}_{get_random_string(6, ALPHABET)}"
            try:
                with transaction.atomic():
                    return create(username)
            except IntegrityError as exc:
                if not _is_username_collision(exc):
                    raise
        raise UsernameAllocationError(
            f"Could not allocate a username after {MAX_ATTEMPTS} attempts."
        )


def _normalize_stem(value: str) -> str:
    stem = "".join(
        char if char.isalnum() else "_" for char in (value or "").lower()
    ).strip("_")[:24]
    return stem or "member"


def _is_username_collision(exc: IntegrityError) -> bool:
    cause = exc.__cause__
    constraint = getattr(getattr(cause, "diag", None), "constraint_name", "") or ""
    return constraint.endswith("_username_key")


def allocate_staff_username(handle: str, slug: str, *, create: Callable[[str], Created]) -> Created:
    """Capture the tenant slug once; retry only username collisions under savepoints."""
    from django.contrib.auth.validators import UnicodeUsernameValidator

    handle = (handle or "staff").strip()
    UnicodeUsernameValidator()(handle)
    suffix = f".{slug}"
    with transaction.atomic():
        for attempt in range(MAX_ATTEMPTS):
            discriminator = f"-{get_random_string(6, ALPHABET)}" if attempt else ""
            candidate = f"{handle[:150 - len(suffix) - len(discriminator)]}{discriminator}{suffix}"
            try:
                with transaction.atomic():
                    return create(candidate)
            except IntegrityError as exc:
                if not _is_username_collision(exc):
                    raise
    raise UsernameAllocationError("Could not allocate a staff username.")
