"""Snapshot, suspend and reconstruct the exact supported view dependency graph."""
from . import migration_acl as acl
from .migration_dependencies import affected, closure, lock_relations, refuse_populated


def capture(cursor, q, oid):
    cursor.execute(
        "SELECT n.nspname,c.relname,c.relkind,pg_get_viewdef(c.oid), "
        "pg_get_userbyid(c.relowner),c.reloptions,obj_description(c.oid,'pg_class'), "
        "c.relispopulated,t.spcname,a.amname FROM pg_class c "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        "LEFT JOIN pg_tablespace t ON t.oid=c.reltablespace "
        "LEFT JOIN pg_am a ON a.oid=c.relam WHERE c.oid=%s", [oid],
    )
    keys = ('schema', 'name', 'kind', 'sql', 'owner', 'options', 'comment', 'populated', 'tablespace', 'method')
    view = dict(zip(keys, cursor.fetchone()))
    view['target'] = f"{q(view['schema'])}.{q(view['name'])}"
    cursor.execute(
        "SELECT t.reloptions FROM pg_class c JOIN pg_class t ON t.oid=c.reltoastrelid WHERE c.oid=%s", [oid],
    )
    toast = cursor.fetchone()
    view['toast_options'] = toast[0] if toast else None
    view['acl'] = acl.capture(cursor, oid)
    cursor.execute(
        "SELECT a.attnum,a.attname,col_description(a.attrelid,a.attnum), "
        "pg_get_expr(d.adbin,d.adrelid) FROM pg_attribute a "
        "LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum "
        "WHERE a.attrelid=%s AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum", [oid],
    )
    view['columns'] = {number: dict(name=name, comment=comment, default=default)
                       for number, name, comment, default in cursor.fetchall()}
    cursor.execute(
        "SELECT pg_get_ruledef(oid),ev_enabled,obj_description(oid,'pg_rewrite'),rulename "
        "FROM pg_rewrite WHERE ev_class=%s AND rulename<>'_RETURN' ORDER BY oid", [oid],
    )
    view['rules'] = cursor.fetchall()
    cursor.execute(
        "SELECT ev_enabled,obj_description(oid,'pg_rewrite') FROM pg_rewrite "
        "WHERE ev_class=%s AND rulename='_RETURN'", [oid],
    )
    view['return_rule'] = cursor.fetchone()
    if view['return_rule'][0] != 'O':
        raise RuntimeError(f"Cannot preserve nonstandard SELECT rule state: {view['target']}")
    cursor.execute(
        "SELECT pg_get_triggerdef(oid),tgenabled,obj_description(oid,'pg_trigger'),tgname "
        "FROM pg_trigger WHERE tgrelid=%s ORDER BY oid", [oid],
    )
    view['triggers'] = cursor.fetchall()
    cursor.execute(
        "SELECT pg_get_indexdef(i.indexrelid),obj_description(i.indexrelid,'pg_class'), "
        "n.nspname,c.relname,i.indisclustered,i.indisreplident,i.indisvalid,i.indisready "
        "FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid "
        "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE i.indrelid=%s ORDER BY c.oid", [oid],
    )
    view['indexes'] = cursor.fetchall()
    for _, _, _, name, _, replica, valid, ready in view['indexes']:
        if replica or not valid or not ready:
            raise RuntimeError(f"Cannot preserve index state: {view['target']}.{name}")
    return view


def suspend(db, columns=None, *, roots=None):
    """Capture and validate the WHOLE closure before the first DROP; never CASCADE."""
    if not db.in_atomic_block:
        raise RuntimeError("View suspension requires a transaction holding relation locks through restore.")
    q = db.ops.quote_name
    with db.cursor() as cursor:
        ordered = closure(cursor, roots) if roots is not None else affected(cursor, columns)
        lock_relations(cursor, ordered)
        # Discovery is only provisional: a refresh may have committed while we
        # waited for a lock. Recheck the entire graph/population under ALL locks,
        # before capturing metadata or dropping even its first dependent.
        checked = closure(cursor, roots) if roots is not None else affected(cursor, columns)
        if checked != ordered:
            raise RuntimeError("Affected view dependencies changed while acquiring locks; retry before dropping any objects.")
        snapshot = [capture(cursor, q, oid) for oid in ordered]
        refuse_populated(view['target'] for view in snapshot if view['kind'] == 'm' and view['populated'])
        for view in snapshot:
            _preflight_states(view)
            acl.preflight(cursor, q, view)
        for view in reversed(snapshot):
            kind = 'MATERIALIZED VIEW' if view['kind'] == 'm' else 'VIEW'
            with acl.as_role(cursor, q, view['owner']):
                cursor.execute(f"DROP {kind} {view['target']} RESTRICT")
    return snapshot


def _preflight_states(view):
    # PostgreSQL 16 restricts ENABLE/DISABLE RULE/TRIGGER to tables (and
    # foreign tables for triggers). CREATE restores the normal origin state
    # on views; any other state must refuse before the first DROP.
    for kind, rows in (('RULE', view['rules']), ('TRIGGER', view['triggers'])):
        for _, enabled, _, name in rows:
            if enabled != 'O':
                raise RuntimeError(
                    f"Cannot preserve nonstandard {kind} state: {view['target']}.{name} ({enabled})"
                )


def _options(cursor, q, options):
    rendered = []
    for option in options or []:
        key, _, value = option.partition('=')
        cursor.execute("SELECT quote_literal(%s)", [value])
        rendered.append(f"{'.'.join(q(part) for part in key.split('.'))}={cursor.fetchone()[0]}")
    return ' WITH (' + ','.join(rendered) + ')' if rendered else ''


def restore(db, snapshot):
    refuse_populated(view['target'] for view in snapshot if view['kind'] == 'm' and view['populated'])
    for view in snapshot:
        _preflight_states(view)
    q = db.ops.quote_name
    with db.cursor() as cursor:
        for view in snapshot:
            target = view['target']
            materialized = view['kind'] == 'm'
            kind = 'MATERIALIZED VIEW' if materialized else 'VIEW'
            columns = ','.join(q(column['name']) for column in view['columns'].values())
            method = f" USING {q(view['method'])}" if materialized and view['method'] else ''
            options = _options(cursor, q, [*(view['options'] or []),
                                          *('toast.' + option for option in view['toast_options'] or [])])
            tablespace = f" TABLESPACE {q(view['tablespace'])}" if materialized and view['tablespace'] else ''
            data = ' WITH NO DATA' if materialized else ''
            # Create as the ORIGINAL owner, not the migrator. This also preserves
            # NULL ACLs and the NOINHERIT/SET-only owner membership contract.
            with acl.as_role(cursor, q, view['owner']):
                with acl.null_acl_defaults(cursor, q, view):
                    cursor.execute(f"CREATE {kind} {target} ({columns}){method}{options}{tablespace} "
                                   f"AS {view['sql'].rstrip(';')}{data}")
                cursor.execute(f"COMMENT ON {kind} {target} IS %s", [view['comment']])
                cursor.execute(f'COMMENT ON RULE "_RETURN" ON {target} IS %s', [view['return_rule'][1]])
                for column in view['columns'].values():
                    name = q(column['name'])
                    cursor.execute(f"COMMENT ON COLUMN {target}.{name} IS %s", [column['comment']])
                    if column['default'] is not None:
                        cursor.execute(f"ALTER VIEW {target} ALTER COLUMN {name} SET DEFAULT {column['default']}")
                for statement, comment, schema, name, clustered, _, _, _ in view['indexes']:
                    cursor.execute(statement)
                    cursor.execute(f"COMMENT ON INDEX {q(schema)}.{q(name)} IS %s", [comment])
                    if clustered:
                        cursor.execute(f"ALTER MATERIALIZED VIEW {target} CLUSTER ON {q(name)}")
                for object_kind, rows in (('RULE', view['rules']), ('TRIGGER', view['triggers'])):
                    for statement, _, comment, name in rows:
                        cursor.execute(statement)
                        cursor.execute(f"COMMENT ON {object_kind} {q(name)} ON {target} IS %s", [comment])
            acl.restore(cursor, q, view)
