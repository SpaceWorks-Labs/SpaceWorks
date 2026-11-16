"""The two privileged provisioning functions the runtime calls (built by ``db_sync``).

The web process connects as a narrow runtime role that cannot create roles (L8 keeps it
that way). Creating, re-keying and dropping an analytics login therefore runs inside these
SECURITY DEFINER functions, owned by the migrating (owner) role and executable only by the
runtime role. They accept nothing they do not check:

* the login name must be this database's analytics login pattern for that exact space (or
  the platform), so the runtime can never touch any other role;
* the password arrives as a SCRAM-SHA-256 verifier computed in the app, so the clear
  password is never sent to the server (nor to its statement log);
* the login is created LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS,
  owns nothing, is read-only by default, and joins one reader role. A space login also joins
  ``spaceworks_rls_fixed`` and is pinned by a ``tenant_rls_fixedrolescope`` row.
"""

from .db_names import ADMIN_SCHEMA, FIXED_GROUP, PLATFORM_SCHEMA, SPACE_SCHEMA

ENSURE_LOGIN = f"{ADMIN_SCHEMA}.ensure_login(text, text, bigint)"
DROP_LOGIN = f"{ADMIN_SCHEMA}.drop_login(text)"

_PRELUDE = """
  tag text := left(encode(sha256(convert_to(current_database(), 'UTF8')), 'hex'), 8);
"""

FUNCTIONS = (
    f"""
CREATE OR REPLACE FUNCTION {ADMIN_SCHEMA}.ensure_login(p_role text, p_verifier text, p_makerspace bigint)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $fn$
DECLARE{_PRELUDE}  scope text := CASE WHEN p_makerspace IS NULL THEN 'p' ELSE 's' || p_makerspace::text END;
  reader text := CASE WHEN p_makerspace IS NULL THEN 'sw_analytics_preader_' ELSE 'sw_analytics_reader_' END || tag;
  home text := CASE WHEN p_makerspace IS NULL THEN '{PLATFORM_SCHEMA}' ELSE '{SPACE_SCHEMA}' END;
BEGIN
  IF p_role IS NULL OR p_role !~ ('^sw_an_' || tag || '_' || scope || '_[0-9a-f]{{6}}$') THEN
    RAISE EXCEPTION 'spaceworks_analytics: refused login name';
  END IF;
  IF p_verifier IS NULL OR p_verifier !~ '^SCRAM-SHA-256\\$[0-9]+:[A-Za-z0-9+/=]+\\$[A-Za-z0-9+/=]+:[A-Za-z0-9+/=]+$' THEN
    RAISE EXCEPTION 'spaceworks_analytics: refused password verifier';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = p_role) THEN
    EXECUTE format('ALTER ROLE %I WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS '
                   'INHERIT CONNECTION LIMIT 10 PASSWORD %L', p_role, p_verifier);
  ELSE
    EXECUTE format('CREATE ROLE %I WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS '
                   'INHERIT CONNECTION LIMIT 10 PASSWORD %L', p_role, p_verifier);
  END IF;
  EXECUTE format('GRANT %I TO %I', reader, p_role);
  IF p_makerspace IS NOT NULL THEN
    EXECUTE format('GRANT %I TO %I', '{FIXED_GROUP}', p_role);
    INSERT INTO public.tenant_rls_fixedrolescope (role_name, makerspace_id, created_at)
      VALUES (p_role, p_makerspace, now())
      ON CONFLICT (role_name) DO UPDATE SET makerspace_id = EXCLUDED.makerspace_id;
  END IF;
  EXECUTE format('ALTER ROLE %I IN DATABASE %I SET default_transaction_read_only = on', p_role, current_database());
  EXECUTE format('ALTER ROLE %I IN DATABASE %I SET statement_timeout = %L', p_role, current_database(), '120s');
  EXECUTE format('ALTER ROLE %I IN DATABASE %I SET search_path = %I', p_role, current_database(), home);
END
$fn$
""",
    f"""
CREATE OR REPLACE FUNCTION {ADMIN_SCHEMA}.drop_login(p_role text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $fn$
DECLARE{_PRELUDE}BEGIN
  IF p_role IS NULL OR p_role !~ ('^sw_an_' || tag || '_(p|s[0-9]+)_[0-9a-f]{{6}}$') THEN
    RAISE EXCEPTION 'spaceworks_analytics: refused login name';
  END IF;
  DELETE FROM public.tenant_rls_fixedrolescope WHERE role_name = p_role;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = p_role) THEN
    EXECUTE format('ALTER ROLE %I NOLOGIN', p_role);
    BEGIN
      PERFORM pg_terminate_backend(pid) FROM pg_stat_activity WHERE usename = p_role;
    EXCEPTION WHEN OTHERS THEN
      NULL;  -- best effort: NOLOGIN already refuses new sessions
    END;
    EXECUTE format('DROP ROLE %I', p_role);
  END IF;
END
$fn$
""",
)
