"""Relation/column ACL preservation, including grantors and ACL array ordering."""
from contextlib import contextmanager

from django.db import DatabaseError


@contextmanager
def as_role(cursor, q, role):
    cursor.execute("SELECT current_user")
    original = cursor.fetchone()[0]
    cursor.execute(f"SET LOCAL ROLE {q(role)}")
    try:
        yield
    finally:
        # Do not mask a failed SQL statement with an aborted-transaction error.
        if cursor.db.connection.info.transaction_status != 3:  # psycopg INERROR
            cursor.execute(f"SET LOCAL ROLE {q(original)}")


def capture(cursor, oid):
    cursor.execute(
        "SELECT 0,relacl::text FROM pg_class WHERE oid=%s UNION ALL "
        "SELECT attnum,attacl::text FROM pg_attribute "
        "WHERE attrelid=%s AND attnum>0 AND NOT attisdropped ORDER BY 1", [oid, oid],
    )
    raw = cursor.fetchall()
    entries = []
    for number, acl in raw:
        if acl is None:
            continue
        entries.extend((number, *row) for row in _entries(cursor, acl))
    return raw, entries


def _entries(cursor, value):
    cursor.execute(
        "SELECT pg_get_userbyid(a.grantor), "
        "CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END, "
        "a.privilege_type,a.is_grantable FROM unnest(%s::aclitem[]) WITH ORDINALITY e(item,pos), "
        "LATERAL aclexplode(ARRAY[e.item]) a ORDER BY e.pos", [value],
    )
    return cursor.fetchall()


def preflight(cursor, q, view):
    roles = {view['owner'], *(entry[1] for entry in view['acl'][1])}
    for role in sorted(roles):
        # A NOINHERIT migrator must explicitly be able to SET every grantor.
        try:
            with as_role(cursor, q, role):
                cursor.execute("SELECT current_user")
        except DatabaseError as exc:
            raise RuntimeError(f"Cannot preserve {view['target']}: cannot SET ROLE {role}") from exc


@contextmanager
def null_acl_defaults(cursor, q, view):
    """A NULL relacl cannot be produced by REVOKE (which stores an explicit ACL).

    For this case only, temporarily neutralize the original owner's defaults in
    this transaction, create as that owner, then replay/verify those defaults.
    Other sessions see the committed defaults throughout (catalogue MVCC).
    """
    if view['acl'][0][0][1] is not None:
        yield
        return

    def read():
        cursor.execute(
            "SELECT d.defaclnamespace,d.defaclacl::text FROM pg_default_acl d "
            "JOIN pg_namespace n ON n.nspname=%s "
            "WHERE d.defaclrole=(SELECT oid FROM pg_roles WHERE rolname=%s) "
            "AND d.defaclobjtype='r' AND d.defaclnamespace IN (0,n.oid) ORDER BY 1",
            [view['schema'], view['owner']],
        )
        return cursor.fetchall()

    original = read()
    statements = []
    for namespace, value in original:
        scope = f" IN SCHEMA {q(view['schema'])}" if namespace else ''
        prefix = f"ALTER DEFAULT PRIVILEGES FOR ROLE {q(view['owner'])}{scope}"
        entries = _entries(cursor, value)
        for role in dict.fromkeys([view['owner'], *(row[1] for row in entries)]):
            recipient = 'PUBLIC' if role == 'PUBLIC' else q(role)
            cursor.execute(f"{prefix} REVOKE ALL ON TABLES FROM {recipient}")
        if not namespace:
            cursor.execute(f"{prefix} GRANT ALL ON TABLES TO {q(view['owner'])}")
        statements.append((prefix, namespace, entries))
    yield
    for prefix, namespace, entries in statements:
        if not namespace:
            cursor.execute(f"{prefix} REVOKE ALL ON TABLES FROM {q(view['owner'])}")
        for _, role, privilege, grantable in entries:
            recipient = 'PUBLIC' if role == 'PUBLIC' else q(role)
            cursor.execute(f"{prefix} GRANT {privilege} ON TABLES TO {recipient}"
                           + (' WITH GRANT OPTION' if grantable else ''))
    if read() != original:
        raise RuntimeError(f"Default ACL restoration differs for {view['target']}")


def restore(cursor, q, view):
    target, owner = view['target'], view['owner']
    expected, grants = view['acl']
    cursor.execute("SELECT oid FROM pg_class WHERE oid=to_regclass(%s)", [target])
    oid = cursor.fetchone()[0]
    current, introduced = capture(cursor, oid)
    if current == expected:
        return
    changed = {number for number, value in current if dict(expected)[number] != value}
    with as_role(cursor, q, owner):
        # Clear ALL explicit grantees, including owner and non-PUBLIC defaults.
        if 0 in changed:
            for role in dict.fromkeys(['PUBLIC', owner, *(entry[2] for entry in introduced if entry[0] == 0)]):
                recipient = 'PUBLIC' if role == 'PUBLIC' else q(role)
                cursor.execute(f"REVOKE ALL ON TABLE {target} FROM {recipient} CASCADE")
        for number, _, role, _, _ in introduced:
            if number and number in changed:
                column = q(view['columns'][number]['name'])
                recipient = 'PUBLIC' if role == 'PUBLIC' else q(role)
                cursor.execute(f"REVOKE ALL ({column}) ON TABLE {target} FROM {recipient} CASCADE")
    for number, grantor, role, privilege, grantable in grants:
        if number not in changed:
            continue
        column = f" ({q(view['columns'][number]['name'])})" if number else ''
        recipient = 'PUBLIC' if role == 'PUBLIC' else q(role)
        with as_role(cursor, q, grantor):
            cursor.execute(f"GRANT {privilege}{column} ON TABLE {target} TO {recipient}"
                           + (' WITH GRANT OPTION' if grantable else ''))
    actual, _ = capture(cursor, oid)
    if actual != expected:
        raise RuntimeError(f"ACL restoration differs for {target}: {actual!r} != {expected!r}")
