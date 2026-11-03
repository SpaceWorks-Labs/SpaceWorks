"""The SQL functions every generated policy calls (created by 0001, re-ensured by sync).

The GUC contract (all set transaction-locally by ``wrapper``; L25's fixed roles ignore it):

* ``app.rls_bound`` - ``on`` when a binding is active; anything else is an open context.
* ``app.makerspace_id`` - comma-separated bound makerspace ids; empty means none.
* ``app.rls_capability`` - a registered cross-tenant capability name, or empty.
* ``app.rls_mode`` - ``enforce`` or ``report``.
"""

FUNCTION_NAMES = (
    "spaceworks_rls_open",
    "spaceworks_rls_scope",
    "spaceworks_rls_reporting",
    "spaceworks_rls_report",
    "spaceworks_rls_fixed_scope",
)

FUNCTIONS = (
    """
CREATE OR REPLACE FUNCTION spaceworks_rls_open() RETURNS boolean
LANGUAGE sql STABLE PARALLEL SAFE AS $$
  SELECT coalesce(current_setting('app.rls_bound', true), '') <> 'on'
      OR coalesce(current_setting('app.rls_capability', true), '') <> ''
$$
""",
    """
CREATE OR REPLACE FUNCTION spaceworks_rls_scope() RETURNS bigint[]
LANGUAGE sql STABLE PARALLEL SAFE AS $$
  SELECT string_to_array(nullif(coalesce(current_setting('app.makerspace_id', true), ''), ''), ',')::bigint[]
$$
""",
    """
CREATE OR REPLACE FUNCTION spaceworks_rls_reporting() RETURNS boolean
LANGUAGE sql STABLE PARALLEL SAFE AS $$
  SELECT coalesce(current_setting('app.rls_mode', true), '') = 'report'
$$
""",
    """
CREATE OR REPLACE FUNCTION spaceworks_rls_report(relation text) RETURNS boolean
LANGUAGE plpgsql VOLATILE AS $$
BEGIN
  IF coalesce(current_setting('app.rls_reported', true), '') <> 'on' THEN
    PERFORM set_config('app.rls_reported', 'on', true);
    RAISE NOTICE 'spaceworks_rls_violation %', relation;
  END IF;
  RETURN true;
END
$$
""",
    """
CREATE OR REPLACE FUNCTION spaceworks_rls_fixed_scope(role_name text) RETURNS bigint[]
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT coalesce(array_agg(makerspace_id), '{}'::bigint[])
  FROM tenant_rls_fixedrolescope WHERE tenant_rls_fixedrolescope.role_name = $1
$$
""",
)

DROP_FUNCTIONS = tuple(
    f"DROP FUNCTION IF EXISTS {name}({args})"
    for name, args in (
        ("spaceworks_rls_open", ""), ("spaceworks_rls_scope", ""), ("spaceworks_rls_reporting", ""),
        ("spaceworks_rls_report", "text"), ("spaceworks_rls_fixed_scope", "text"),
    )
)
