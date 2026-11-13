"""Compile each scoped table's ownership predicate into its RLS policy SQL.

One permissive policy per table, ``spaceworks_rls_tenant``, for every command and role::

    CASE WHEN spaceworks_rls_open() THEN true            -- unbound, or a capability
         WHEN <owned by a bound makerspace> THEN true
         WHEN spaceworks_rls_reporting() THEN spaceworks_rls_report('<table>')
         ELSE false END

"Owned" follows the predicate: any of its ``any_paths`` points at a bound makerspace,
or none of them names an owner at all (a platform row is nobody else's row); every
``local_or_global_paths`` entry is unset or bound. A one-hop path compares the column;
a longer path is an ``EXISTS`` join to the makerspace column; when any link after the first is
nullable, a chain that ends at no makerspace is a platform row too. When the L25 group role
``spaceworks_rls_fixed`` exists, a restrictive ``spaceworks_rls_fixed`` policy limits its
members to their fixed space whatever settings they send.
"""

import hashlib
from dataclasses import dataclass

from django.apps import apps

from .scope_registry import ROOT, predicates

GENERATOR_VERSION = "1"
TENANT_POLICY = "spaceworks_rls_tenant"
FIXED_POLICY = "spaceworks_rls_fixed"
FIXED_ROLE = "spaceworks_rls_fixed"
SCOPE = "spaceworks_rls_scope()"
FIXED_SCOPE = "spaceworks_rls_fixed_scope(current_user::text)"


class Unresolvable(Exception):
    pass


@dataclass(frozen=True)
class TablePlan:
    label: str
    table: str
    tenant_sql: str
    fixed_sql: str

    def fingerprint(self, *, fixed):
        body = f"{GENERATOR_VERSION}\n{self.tenant_sql}\n{self.fixed_sql if fixed else ''}"
        return "spaceworks-rls:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def q(name):
    return '"' + name.replace('"', '""') + '"'


def _hops(model, path):
    hops, current = [], model
    for part in path.split("__"):
        try:
            field = current._meta.get_field(part)
        except Exception as exc:
            raise Unresolvable(f"{path}: no field {part!r}") from exc
        if not (field.concrete and field.is_relation and (field.many_to_one or field.one_to_one)):
            raise Unresolvable(f"{path}: {part!r} is not a forward foreign key")
        if field.model._meta.concrete_model is not current._meta.concrete_model:
            raise Unresolvable(f"{path}: {part!r} is inherited from another table")
        hops.append(field)
        current = field.related_model
    if current._meta.label != ROOT:
        raise Unresolvable(f"{path}: does not end at the makerspace")
    return hops


def _path_sql(table, hops, scope):
    first = hops[0]
    outer = f"{q(table)}.{q(first.column)}"
    unowned = f"{outer} IS NULL"
    if len(hops) == 1:
        return f"{outer} = ANY({scope})", unowned
    joins, alias = [], "spaceworks_j1"
    source = f"{q(first.related_model._meta.db_table)} {alias}"
    condition = f"{alias}.{q(first.target_field.column)} = {outer}"
    broken = False  # once a nullable link is LEFT JOINed, every later link must be too
    for index, field in enumerate(hops[1:-1], start=2):
        nxt = f"spaceworks_j{index}"
        broken = broken or field.null
        joins.append(f"{'LEFT JOIN' if broken else 'JOIN'} {q(field.related_model._meta.db_table)} {nxt} "
                     f"ON {nxt}.{q(field.target_field.column)} = {alias}.{q(field.column)}")
        alias = nxt
    last = hops[-1]
    chain = f"EXISTS (SELECT 1 FROM {source} {' '.join(joins)} WHERE {condition} AND {alias}.{q(last.column)}"
    owned = f"{chain} = ANY({scope}))".replace("  ", " ")
    if last.null or broken:
        # The chain may end at no makerspace: a credential row of an account with no
        # staff_makerspace_id (a person, the superadmin) is nobody's tenant row, exactly
        # as accounts_user's own one-hop policy already admits. Without this every
        # tenant-bound request hid the session marker of every person (#194 VPS boot).
        # A nullable INTERMEDIATE link ends the chain the same way (a blacklisted token
        # whose outstanding token has no user, token__user__staff_makerspace).
        unowned = f"({unowned} OR {chain} IS NULL))".replace("  ", " ")
    return owned, unowned


def owned_sql(model, predicate, scope, *, platform_rows=True):
    table = model._meta.db_table
    any_terms = [_path_sql(table, _hops(model, path), scope) for path in predicate.any_paths]
    if not any_terms:
        raise Unresolvable("predicate names no ownership path")
    alternatives = [owned for owned, _ in any_terms]
    if platform_rows:
        alternatives.append("(" + " AND ".join(unowned for _, unowned in any_terms) + ")")
    clauses = ["(" + " OR ".join(alternatives) + ")"]
    for path in predicate.local_or_global_paths:
        owned, unowned = _path_sql(table, _hops(model, path), scope)
        clauses.append(f"({unowned} OR {owned})")
    return " AND ".join(clauses)


def tenant_expression(model, predicate):
    table = model._meta.db_table.replace("'", "''")
    return (
        "CASE WHEN spaceworks_rls_open() THEN true "
        f"WHEN {owned_sql(model, predicate, SCOPE)} THEN true "
        f"WHEN spaceworks_rls_reporting() THEN spaceworks_rls_report('{table}') "
        "ELSE false END"
    )


def build_plans():
    """(plans by label, unresolvable reasons by label) over the live app registry."""
    plans, unresolvable = {}, {}
    for label, predicate in sorted(predicates().items()):
        model = apps.get_model(label)
        try:
            plans[label] = TablePlan(
                label=label, table=model._meta.db_table,
                tenant_sql=tenant_expression(model, predicate),
                fixed_sql=owned_sql(model, predicate, FIXED_SCOPE, platform_rows=False),
            )
        except Unresolvable as exc:
            unresolvable[label] = str(exc)
    return plans, unresolvable
