"""SQL for the integrator's forward migration; this file creates no migration."""

MANAGED_BINDING_GUARD_SQL = """
CREATE OR REPLACE FUNCTION public.backup_managed_binding_immutable()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
BEGIN
  RAISE EXCEPTION 'managed deployment binding is immutable';
END;
$$;
CREATE TRIGGER backup_managed_binding_no_mutation
BEFORE UPDATE OR DELETE ON public.backup_manageddeploymentstate
FOR EACH ROW EXECUTE FUNCTION public.backup_managed_binding_immutable();
"""
