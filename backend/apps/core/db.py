"""Driver-independent PostgreSQL error inspection."""


def sqlstate(exc):
    """Return the first SQLSTATE, checking causes before implicit contexts.

    Django wraps driver exceptions. psycopg 3 exposes ``sqlstate`` while
    psycopg2 exposes ``pgcode``; other wrappers may add more chain links.
    """
    pending, seen = [exc], set()
    while pending:
        current = pending.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        code = getattr(current, "sqlstate", None) or getattr(current, "pgcode", None)
        if code:
            return code
        pending.extend((current.__context__, current.__cause__))
    return None
