"""Discover PostgreSQL dependents before issuing any destructive DDL."""
from .catalogue.types import q
from .migration_acl import as_role


def refuse_populated(targets):
    targets = sorted(targets)
    if targets:
        raise RuntimeError(
            "Unsupported populated materialized views: " + ', '.join(targets)
            + ". Drop them or refresh them WITH NO DATA yourself before retrying; no objects have been dropped."
        )


def lock_relations(cursor, ordered):
    """Hold AccessExclusiveLock until transaction end, including across restore.

    PG16 rejects LOCK TABLE on materialized views. ALTER OWNER to the existing
    owner takes AccessExclusiveLock without updating ownership or ACLs (see
    tablecmds.c: AlterTableGetLockLevel / ATExecChangeOwner). It blocks both
    refresh modes. Lock dependents first, before the relations a refresh reads.
    """
    for oid in reversed(ordered):
        cursor.execute(
            "SELECT n.nspname,c.relname,c.relkind,pg_get_userbyid(c.relowner) "
            "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.oid=%s", [oid],
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Affected view disappeared while acquiring locks; retry before dropping any objects.")
        schema, name, relkind, owner = row
        target = f'{q(schema)}.{q(name)}'
        kind = 'MATERIALIZED VIEW' if relkind == 'm' else 'VIEW'
        with as_role(cursor, q, owner):
            cursor.execute(f"ALTER {kind} {target} OWNER TO {q(owner)}")
        cursor.execute("SELECT to_regclass(%s)::oid", [target])
        if cursor.fetchone() != (oid,):
            raise RuntimeError("Affected view identity changed while acquiring locks; retry before dropping any objects.")


def affected(cursor, columns):
    roots = set()
    for table, column in columns:
        cursor.execute(
            "SELECT DISTINCT r.ev_class FROM pg_depend d "
            "JOIN pg_rewrite r ON d.classid='pg_rewrite'::regclass AND r.oid=d.objid "
            "JOIN pg_class c ON c.oid=r.ev_class "
            "JOIN pg_attribute a ON a.attrelid=to_regclass(%s) AND a.attname=%s "
            "JOIN pg_class b ON b.oid=a.attrelid "
            "WHERE c.relkind IN ('v','m') AND "
            "((d.refclassid='pg_class'::regclass AND d.refobjid=a.attrelid "
            "AND d.refobjsubid=a.attnum) OR "
            "(d.refclassid='pg_type'::regclass AND d.refobjid=b.reltype))",
            [table, column],
        )
        roots.update(row[0] for row in cursor.fetchall())
    return closure(cursor, roots)


def closure(cursor, roots):
    """Walk all object classes, including row types and external-schema dependents.

    PostgreSQL implements a view as a relation with an internally owned _RETURN
    rule. Follow that ownership edge back to its relation as DROP would do.
    Every other object is either explicitly reconstructed or refused by name.
    """
    if not roots:
        return []
    cursor.execute(
        "WITH RECURSIVE edges AS ("
        "SELECT refclassid AS parent_class, refobjid AS parent_id, "
        "classid AS child_class, objid AS child_id FROM pg_depend "
        "UNION SELECT 'pg_rewrite'::regclass::oid, oid, 'pg_class'::regclass::oid, ev_class "
        "FROM pg_rewrite WHERE rulename='_RETURN'), objects(classid,objid) AS ("
        "SELECT 'pg_class'::regclass::oid, unnest(%s::oid[]) UNION "
        "SELECT e.child_class,e.child_id FROM objects o JOIN edges e "
        "ON e.parent_class=o.classid AND e.parent_id=o.objid) "
        "SELECT o.classid::regclass::text,o.objid, "
        "pg_describe_object(o.classid,o.objid,0) FROM objects o",
        [sorted(roots)],
    )
    objects = cursor.fetchall()
    relation_ids = [oid for kind, oid, _ in objects if kind == 'pg_class']
    cursor.execute("SELECT oid,relkind,reltoastrelid FROM pg_class WHERE oid=ANY(%s)", [relation_ids])
    relations = {oid: (kind, toast) for oid, kind, toast in cursor.fetchall()}
    views = {oid for oid, (kind, _) in relations.items() if kind in ('v', 'm')}
    # Refuse the entire stored-snapshot set before other object checks or DROP.
    # Re-running even a stable definition cannot recover its materialized rows.
    cursor.execute(
        "SELECT n.nspname,c.relname FROM pg_class c "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE c.oid=ANY(%s::oid[]) AND c.relkind='m' AND c.relispopulated "
        "ORDER BY n.nspname,c.relname", [sorted(views)],
    )
    refuse_populated(f'{q(schema)}.{q(name)}' for schema, name in cursor.fetchall())
    toast_ids = {toast for oid, (_, toast) in relations.items() if oid in views and toast}
    for kind, oid, description in objects:
        supported = False
        if kind == 'pg_class':
            relkind = relations[oid][0]
            supported = oid in views or oid in toast_ids
            if relkind == 'i':
                cursor.execute("SELECT indrelid FROM pg_index WHERE indexrelid=%s", [oid])
                supported = cursor.fetchone()[0] in views | toast_ids
        elif kind == 'pg_type':
            cursor.execute(
                "SELECT typrelid,typelem FROM pg_type WHERE oid=%s", [oid],
            )
            relation, element = cursor.fetchone()
            cursor.execute("SELECT typrelid FROM pg_type WHERE oid=%s", [element])
            row = cursor.fetchone()
            supported = relation in views | toast_ids or bool(row and row[0] in views | toast_ids)
        elif kind in ('pg_rewrite', 'pg_trigger', 'pg_attrdef'):
            field = {'pg_rewrite': 'ev_class', 'pg_trigger': 'tgrelid', 'pg_attrdef': 'adrelid'}[kind]
            cursor.execute(f"SELECT {field} FROM {kind} WHERE oid=%s", [oid])
            supported = cursor.fetchone()[0] in views
            if kind == 'pg_trigger':
                cursor.execute("SELECT tgisinternal FROM pg_trigger WHERE oid=%s", [oid])
                supported = supported and not cursor.fetchone()[0]
        if not supported:
            raise RuntimeError(f"Cannot preserve dependent object: {description} ({kind})")
    # Extension ownership and security labels need extension/provider-specific DDL.
    cursor.execute(
        "WITH objects AS (SELECT * FROM unnest(%s::regclass[],%s::oid[]) AS o(classid,objid)) "
        "SELECT pg_describe_object(d.classid,d.objid,0) FROM pg_depend d "
        "JOIN objects o ON o.classid=d.classid AND o.objid=d.objid WHERE d.deptype='e' "
        "UNION SELECT pg_describe_object(s.classoid,s.objoid,s.objsubid) FROM pg_seclabel s "
        "JOIN objects o ON o.classid=s.classoid AND o.objid=s.objoid",
        [[kind for kind, _, _ in objects], [oid for _, oid, _ in objects]],
    )
    row = cursor.fetchone()
    if row:
        raise RuntimeError(f"Cannot preserve extension membership/security label: {row[0]}")
    cursor.execute(
        "SELECT DISTINCT r.ev_class, COALESCE(NULLIF(t.typrelid,0),e.typrelid,d.refobjid) FROM pg_rewrite r "
        "JOIN pg_depend d ON d.classid='pg_rewrite'::regclass AND d.objid=r.oid "
        "LEFT JOIN pg_type t ON d.refclassid='pg_type'::regclass AND t.oid=d.refobjid "
        "LEFT JOIN pg_type e ON e.oid=t.typelem "
        "WHERE r.ev_class=ANY(%s) AND d.refclassid IN ('pg_class'::regclass,'pg_type'::regclass)",
        [list(views)],
    )
    prerequisites = {oid: set() for oid in views}
    for child, parent in cursor.fetchall():
        if parent in views and child != parent:
            prerequisites[child].add(parent)
    ordered = []
    while prerequisites:
        ready = sorted(oid for oid, parents in prerequisites.items() if not parents)
        if not ready:
            raise RuntimeError(f"Cannot preserve cyclic view dependencies: {sorted(prerequisites)}")
        ordered.extend(ready)
        prerequisites = {oid: parents - set(ready) for oid, parents in prerequisites.items() if oid not in ready}
    return ordered
