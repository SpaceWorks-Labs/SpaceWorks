"""Preparation guards: broker, storage and key work must precede domain transactions."""
from django.db import transaction


def in_domain_transaction(using=None):
    """True inside any atomic block opened by application code.

    Mirrors Django's own ``atomic(durable=True)`` rule rather than plain
    ``connection.in_atomic_block``: the wrapping transaction of a database test
    case (Django marks it ``_from_testcase``) is not a domain transaction, so a
    preparation guard refuses exactly the same caller-held transactions in tests
    as in production. It reads connection state only and never opens a query.
    """
    connection = transaction.get_connection(using)
    if not connection.in_atomic_block:
        return False
    blocks = connection.atomic_blocks
    return not (blocks and getattr(blocks[-1], "_from_testcase", False))
