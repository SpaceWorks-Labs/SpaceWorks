"""An adapter-dispatched job is created with a `pending-<hex>` placeholder and bound to the vendor's own id at ack.

The printer-job guard froze `external_job_id` like the rest of the identity, which made the ack impossible. This
replaces the function body (same name, same trigger) so ONLY a still-unreported row holding the placeholder may
change that one column, once, to a real (non-placeholder, non-null) vendor id; every other identity column, the target and the reported facts stay frozen.
"""
from django.db import migrations

SQL = r"""
CREATE OR REPLACE FUNCTION devices_printer_job_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF current_setting('app.allow_immutable_delete', true) = 'on' THEN RETURN OLD; END IF;
    RAISE EXCEPTION 'printer history requires authorized purge';
  END IF;
  IF ROW(OLD.command_id, OLD.device_id, OLD.makerspace_id,
         OLD.machine_id_snapshot, OLD.machine_name, OLD.service_request_id_snapshot, OLD.service_request_name)
     IS DISTINCT FROM
     ROW(NEW.command_id, NEW.device_id, NEW.makerspace_id,
         NEW.machine_id_snapshot, NEW.machine_name, NEW.service_request_id_snapshot, NEW.service_request_name)
     OR (OLD.external_job_id IS DISTINCT FROM NEW.external_job_id
         AND NOT (OLD.external_job_id LIKE 'pending-%' AND OLD.reported_at IS NULL
                  AND NEW.external_job_id IS NOT NULL AND NEW.external_job_id NOT LIKE 'pending-%')) THEN
    RAISE EXCEPTION 'printer identity is immutable';
  END IF;
  IF (NEW.machine_id IS NOT NULL AND NEW.machine_id IS DISTINCT FROM OLD.machine_id) OR
     (NEW.service_request_id IS NOT NULL AND NEW.service_request_id IS DISTINCT FROM OLD.service_request_id) THEN
    RAISE EXCEPTION 'printer target is immutable';
  END IF;
  IF OLD.reported_at IS NOT NULL THEN
    IF ROW(OLD.terminal_operation_id, OLD.report_sha256, OLD.outcome, OLD.actual_minutes,
           OLD.percent_complete, OLD.actual_grams, OLD.actual_quantity, OLD.reported_at)
       IS DISTINCT FROM
       ROW(NEW.terminal_operation_id, NEW.report_sha256, NEW.outcome, NEW.actual_minutes,
           NEW.percent_complete, NEW.actual_grams, NEW.actual_quantity, NEW.reported_at) THEN
      RAISE EXCEPTION 'printer report is immutable';
    END IF;
    -- Authorized PII re-encryption may change ciphertext; adapter verifies plaintext hash.
    IF OLD.failure_reason IS DISTINCT FROM NEW.failure_reason AND
       COALESCE(current_setting('app.pii_fence_operation', true), '') = '' THEN
      RAISE EXCEPTION 'printer failure report is immutable';
    END IF;
  END IF;
  RETURN NEW;
END; $$;
"""


def _original_body() -> str:
    """The 0002 body from ``_printer_claim_guards`` (external_job_id fully frozen), for the reverse."""
    from ._printer_claim_guards import GUARD_SQL as GUARDS
    start = GUARDS.index("CREATE FUNCTION devices_printer_job_guard()")
    end = GUARDS.index("END; $$;", start) + len("END; $$;")
    return "CREATE OR REPLACE" + GUARDS[start + len("CREATE"):end]


class Migration(migrations.Migration):
    dependencies = [("devices", "0009_adapter_media_data")]
    operations = [migrations.RunSQL(SQL, _original_body())]
