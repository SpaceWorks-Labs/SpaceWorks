"""Guards: every scoped table has a policy, and the runtime role can honour it.

* ``tenant_rls.E001`` (always): a makerspace-scoped model whose ownership predicate the
  generator cannot compile - it would ship without a policy. Fix the predicate, or add the
  model to ``scope_registry.EXEMPT`` with its reason.
* ``tenant_rls.W001`` (database): a scoped table without its current generated policy
  (run ``manage.py rls_sync``). A warning, because ``migrate`` runs database checks before
  the post-migrate step that applies the policies.
* ``tenant_rls.W002`` (database): the runtime role cannot be enforced (report-only or
  inactive, #128 C-25). Never an error: the app always starts and the free profile works.
"""

from django.core.checks import Error, Tags, Warning, register


@register()
def check_policy_generation(app_configs=None, **kwargs):
    from .policies import build_plans

    _plans, unresolvable = build_plans()
    return [
        Error(f"{label} is makerspace-scoped but has no compilable RLS policy: {reason}.",
              hint="Fix its ownership predicate or add it to tenant_rls.scope_registry.EXEMPT with a reason.",
              id="tenant_rls.E001")
        for label, reason in sorted(unresolvable.items())
    ]


def coverage_gaps(using="default"):
    from django.db import connections
    from .policies import build_plans
    from .sync import fixed_role_exists, live_state

    plans, _ = build_plans()
    with connections[using].cursor() as cursor:
        fixed = fixed_role_exists(cursor)
        live = live_state(cursor)
    gaps = []
    for plan in plans.values():
        state = live.get(plan.table)
        if state is None:
            continue
        enabled, forced, comment, _has_fixed, _other = state
        if not (enabled and forced and comment == plan.fingerprint(fixed=fixed)):
            gaps.append(plan.table)
    return sorted(gaps)


@register(Tags.database)
def check_live_policies(app_configs=None, databases=None, **kwargs):
    if not databases or "default" not in databases:
        return []
    from django.db import connections
    if connections["default"].vendor != "postgresql":
        return []
    from .role_contract import status
    messages = []
    try:
        gaps = coverage_gaps()
    except Exception:
        return []
    if gaps:
        messages.append(Warning(
            f"{len(gaps)} makerspace-scoped table(s) lack their current RLS policy: {', '.join(gaps[:10])}.",
            hint="Run `python manage.py rls_sync` (migrate does this automatically).", id="tenant_rls.W001"))
    mode = status()["mode"]
    if mode in {"report", "inactive"}:
        messages.append(Warning(
            f"Row-level security is {mode} for this runtime database role.",
            hint="Connect the app as a narrow role (the bundled compose spaceworks_app): it must own no table, "
                 "hold no BYPASSRLS and not be a superuser. See docs/INVARIANTS.md 'Row-level security backstop'.",
            id="tenant_rls.W002"))
    return messages
