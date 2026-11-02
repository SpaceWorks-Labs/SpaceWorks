"""Pickup codes and the uncollected rule (#142 OQ-7/OQ-15).

A finished job gets a short code. Whoever shows it (on screen or as the QR the member
area draws from it) may collect; staff type or scan it and record the collector's name.
Without the code, staff may still hand over to the member in person.
"""

import secrets

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I/L
LENGTH = 6


def new_pickup_code():
    return "".join(secrets.choice(ALPHABET) for _ in range(LENGTH))


def normalize(code):
    return "".join(str(code or "").upper().split())


def matches(row, code):
    return bool(row.pickup_code) and secrets.compare_digest(row.pickup_code, normalize(code))
