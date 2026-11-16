"""Bucket history floors cannot be erased by a credential/configuration change."""
from django.db import migrations

FORWARD = """
CREATE FUNCTION public.operations_storage_capability_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog, public AS $$
BEGIN
  IF TG_OP='DELETE' THEN
    RAISE EXCEPTION 'storage history floor cannot be deleted';
  END IF;
  IF NEW.identity IS DISTINCT FROM OLD.identity
     OR NEW.identity_fingerprint IS DISTINCT FROM OLD.identity_fingerprint
     OR NEW.generation < OLD.generation
     OR (OLD.history_possible AND NOT NEW.history_possible)
     OR (NEW.generation=OLD.generation AND NEW.configuration_fingerprint<>OLD.configuration_fingerprint)
     OR (OLD.logical_role IS NOT NULL AND NEW.logical_role IS DISTINCT FROM OLD.logical_role) THEN
    RAISE EXCEPTION 'storage identity/history change requires verified migration';
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER operations_storage_capability_history
BEFORE UPDATE OR DELETE ON public.operations_storagecapabilitystate
FOR EACH ROW EXECUTE FUNCTION public.operations_storage_capability_guard();
"""
REVERSE = """
DROP TRIGGER IF EXISTS operations_storage_capability_history ON public.operations_storagecapabilitystate;
DROP FUNCTION IF EXISTS public.operations_storage_capability_guard();
"""


class Migration(migrations.Migration):
    dependencies = [("operations", "0014_cloud_coordination")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
