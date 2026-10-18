"""Shared transaction locks. Acquire WhatsApp sender lock before any row lock."""
import hashlib

from django.db import connection
from django.db.transaction import TransactionManagementError


def advisory_lock(key):
    if not connection.in_atomic_block:
        raise TransactionManagementError("Messaging locks require transaction.atomic().")
    value = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big", signed=True)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [value])


def lock_whatsapp_sender(sender_key):
    advisory_lock("whatsapp:" + sender_key)
