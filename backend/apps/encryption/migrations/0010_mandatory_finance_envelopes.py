"""Mandatory core envelopes and key retirement guards, independent of PII mode."""
from django.db import migrations

FORWARD = r"""
CREATE FUNCTION reimbursement_maintenance_allowed(tenant_id bigint) RETURNS boolean
LANGUAGE sql STABLE AS $$
  SELECT EXISTS (
    SELECT 1 FROM encryption_piiglobalwritefence g
    JOIN encryption_piimakerspacewritefence t ON t.makerspace_id=tenant_id
    WHERE g.id=1 AND g.state='closed' AND t.state='closed'
      AND g.operation_id=t.operation_id AND g.operation_kind=t.operation_kind
      AND g.operation_kind IN ('enable_transition','search_rotation','decrypt_rollback','tenant_import')
      AND g.operation_id::text=current_setting('app.pii_fence_operation',true)
  );
$$;

CREATE FUNCTION finance_mandatory_envelope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE tenant_id bigint; payload text; field_name text; version_no integer;
BEGIN
  SELECT makerspace_id INTO tenant_id FROM payments_eventpayoutobligation WHERE id=NEW.obligation_id;
  IF tenant_id IS NULL THEN RAISE EXCEPTION 'mandatory finance host missing'; END IF;
  PERFORM pii_assert_mapped_write_allowed(tenant_id);
  FOREACH field_name IN ARRAY TG_ARGV LOOP
    payload := to_jsonb(NEW)->>field_name;
    IF field_name='cancellation_note' AND payload='' THEN CONTINUE; END IF;
    IF TG_TABLE_NAME='payments_eventpayeerevision' AND to_jsonb(NEW)->>'state'='purged' AND payload='' THEN CONTINUE; END IF;
    IF payload IS NULL OR payload !~ '^pii:gcm:v1:[1-9][0-9]*:[A-Za-z0-9_-]+:[A-Za-z0-9_-]+$'
      THEN RAISE EXCEPTION 'mandatory finance envelope required'; END IF;
    version_no:=split_part(payload,':',4)::integer;
    IF NOT EXISTS (SELECT 1 FROM encryption_makerspaceencryptionkey
      WHERE makerspace_id=tenant_id AND version=version_no AND status IN ('active','rotated'))
      THEN RAISE EXCEPTION 'mandatory finance key unavailable'; END IF;
  END LOOP;
  RETURN NEW;
END; $$;
CREATE TRIGGER finance_payee_mandatory BEFORE INSERT OR UPDATE ON payments_eventpayeerevision
  FOR EACH ROW EXECUTE FUNCTION finance_mandatory_envelope_guard('details');
CREATE TRIGGER finance_decision_mandatory BEFORE INSERT OR UPDATE ON payments_eventpayoutobligationrevision
  FOR EACH ROW EXECUTE FUNCTION finance_mandatory_envelope_guard('decision_summary','cancellation_note');

CREATE FUNCTION finance_referenced_key_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE key_tenant_id bigint; version_no integer; prefix text;
BEGIN
  IF TG_OP='UPDATE' AND NEW.status<>'disabled' THEN RETURN NEW; END IF;
  key_tenant_id:=OLD.makerspace_id; version_no:=OLD.version;
  PERFORM pg_advisory_xact_lock_shared(734201,0);
  PERFORM pg_advisory_xact_lock(734202,key_tenant_id::integer);
  prefix:='pii:gcm:v1:' || version_no::text || ':%';
  IF EXISTS (SELECT 1 FROM payments_eventpayeerevision p
      JOIN payments_eventpayoutobligation o ON o.id=p.obligation_id
      WHERE o.makerspace_id=key_tenant_id AND p.details LIKE prefix)
    OR EXISTS (SELECT 1 FROM payments_eventpayoutobligationrevision r
      JOIN payments_eventpayoutobligation o ON o.id=r.obligation_id
      WHERE o.makerspace_id=key_tenant_id AND (r.decision_summary LIKE prefix OR r.cancellation_note LIKE prefix))
    THEN RAISE EXCEPTION 'mandatory finance key remains referenced'; END IF;
  IF TG_OP='DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER finance_key_retirement BEFORE UPDATE OF status OR DELETE ON encryption_makerspaceencryptionkey
  FOR EACH ROW EXECUTE FUNCTION finance_referenced_key_guard();
"""

REVERSE = """
DROP TRIGGER finance_key_retirement ON encryption_makerspaceencryptionkey;
DROP FUNCTION finance_referenced_key_guard();
DROP TRIGGER finance_decision_mandatory ON payments_eventpayoutobligationrevision;
DROP TRIGGER finance_payee_mandatory ON payments_eventpayeerevision;
DROP FUNCTION finance_mandatory_envelope_guard();
DROP FUNCTION reimbursement_maintenance_allowed(bigint);
"""


class Migration(migrations.Migration):
    dependencies = [
        ("encryption", "0009_account_programme_guards"),
        ("payments", "0024_reimbursement_relations_1"),
    ]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
