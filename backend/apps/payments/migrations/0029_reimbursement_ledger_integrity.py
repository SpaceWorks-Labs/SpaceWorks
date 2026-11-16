"""Core liability totals and immutable routing snapshots survive domain removal."""
from django.db import migrations

FORWARD = r"""
CREATE FUNCTION event_payout_parent_lock() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE tenant_id bigint;
BEGIN
  SELECT makerspace_id INTO tenant_id FROM payments_eventpayoutobligation WHERE id=NEW.obligation_id;
  PERFORM pii_assert_mapped_write_allowed(tenant_id);
  PERFORM 1 FROM payments_eventpayoutobligation WHERE id=NEW.obligation_id FOR UPDATE;
  RETURN NEW;
END; $$;
CREATE TRIGGER event_payout_parent_lock BEFORE INSERT ON payments_eventpayoutentry
  FOR EACH ROW EXECUTE FUNCTION event_payout_parent_lock();

CREATE FUNCTION event_payout_total_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE target_id uuid; approved numeric; paid numeric;
BEGIN
  IF TG_TABLE_NAME='payments_eventpayoutobligation' THEN target_id:=NEW.id;
  ELSE target_id:=NEW.obligation_id; END IF;
  SELECT approved_minor INTO approved FROM payments_eventpayoutobligation o WHERE o.id=target_id;
  SELECT COALESCE(SUM(e.amount_minor),0) INTO paid FROM payments_eventpayoutentry e
    WHERE e.obligation_id=target_id AND NOT e.is_void
      AND NOT EXISTS (SELECT 1 FROM payments_eventpayoutentry a WHERE a.amends_id=e.id);
  IF paid<0 OR paid>approved THEN RAISE EXCEPTION 'effective payout exceeds approved obligation'; END IF;
  RETURN NEW;
END; $$;
CREATE CONSTRAINT TRIGGER event_payout_entry_total AFTER INSERT ON payments_eventpayoutentry
  DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION event_payout_total_guard();
CREATE CONSTRAINT TRIGGER event_payout_obligation_total AFTER UPDATE ON payments_eventpayoutobligation
  DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION event_payout_total_guard();

CREATE FUNCTION event_payee_snapshot_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE tenant_id bigint;
BEGIN
  IF TG_OP='DELETE' THEN
    IF current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
    RAISE EXCEPTION 'core finance rows require whole tenant purge';
  END IF;
  SELECT makerspace_id INTO tenant_id FROM payments_eventpayoutobligation WHERE id=NEW.obligation_id;
  IF (NEW.obligation_id,NEW.country,NEW.template_key,NEW.template_version,NEW.method,NEW.submitted_at,NEW.disclosure_version)
    IS DISTINCT FROM (OLD.obligation_id,OLD.country,OLD.template_key,OLD.template_version,OLD.method,OLD.submitted_at,OLD.disclosure_version)
    THEN RAISE EXCEPTION 'payee revision snapshot is immutable'; END IF;
  IF NEW.details IS DISTINCT FROM OLD.details AND NOT (
    (NEW.state='purged' AND NEW.details='' AND NEW.purged_at IS NOT NULL)
    OR reimbursement_maintenance_allowed(tenant_id))
    THEN RAISE EXCEPTION 'payee revision payload is immutable'; END IF;
  IF OLD.state='purged' AND (NEW.state<>'purged' OR NEW.details<>'')
    THEN RAISE EXCEPTION 'purged payee cannot be restored'; END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER event_payee_snapshot BEFORE UPDATE OR DELETE ON payments_eventpayeerevision
  FOR EACH ROW EXECUTE FUNCTION event_payee_snapshot_guard();

CREATE FUNCTION event_finance_delete_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  RAISE EXCEPTION 'core finance rows require whole tenant purge';
END; $$;
CREATE TRIGGER event_obligation_delete BEFORE DELETE ON payments_eventpayoutobligation
  FOR EACH ROW EXECUTE FUNCTION event_finance_delete_guard();
CREATE TRIGGER event_finance_attachment_delete BEFORE DELETE ON payments_financeattachment
  FOR EACH ROW EXECUTE FUNCTION event_finance_delete_guard();
CREATE TRIGGER event_receipt_use_delete BEFORE DELETE ON payments_receiptuse
  FOR EACH ROW EXECUTE FUNCTION event_finance_delete_guard();
"""

REVERSE = """
DROP TRIGGER event_receipt_use_delete ON payments_receiptuse;
DROP TRIGGER event_finance_attachment_delete ON payments_financeattachment;
DROP TRIGGER event_obligation_delete ON payments_eventpayoutobligation;
DROP FUNCTION event_finance_delete_guard();
DROP TRIGGER event_payee_snapshot ON payments_eventpayeerevision;
DROP FUNCTION event_payee_snapshot_guard();
DROP TRIGGER event_payout_obligation_total ON payments_eventpayoutobligation;
DROP TRIGGER event_payout_entry_total ON payments_eventpayoutentry;
DROP FUNCTION event_payout_total_guard();
DROP TRIGGER event_payout_parent_lock ON payments_eventpayoutentry;
DROP FUNCTION event_payout_parent_lock();
"""


class Migration(migrations.Migration):
    dependencies = [("payments", "0028_reimbursement_guards")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
