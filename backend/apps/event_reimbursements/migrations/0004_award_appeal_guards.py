"""Accepted caps and appeal submission evidence cannot be rewritten."""
from django.db import migrations

FORWARD = """
CREATE FUNCTION reimbursement_accepted_award_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.accepted_at IS NOT NULL AND
    (NEW.amount_minor,NEW.currency,NEW.rule_revision,NEW.calculation_snapshot,NEW.accepted_at)
    IS DISTINCT FROM (OLD.amount_minor,OLD.currency,OLD.rule_revision,OLD.calculation_snapshot,OLD.accepted_at)
    THEN RAISE EXCEPTION 'accepted reimbursement cap is immutable'; END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER reimbursement_accepted_award BEFORE UPDATE ON event_reimbursements_grantaward
  FOR EACH ROW EXECUTE FUNCTION reimbursement_accepted_award_guard();

CREATE FUNCTION reimbursement_appeal_resolution_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' THEN
    IF current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
    RAISE EXCEPTION 'appeal evidence is immutable';
  END IF;
  IF to_jsonb(NEW)-'statement'=to_jsonb(OLD)-'statement'
    AND reimbursement_maintenance_allowed((SELECT e.makerspace_id
      FROM event_reimbursements_reimbursementclaim c JOIN events_event e ON e.id=c.event_id
      WHERE c.id=NEW.claim_id)) THEN RETURN NEW; END IF;
  IF to_jsonb(NEW)-ARRAY['resolved_decision_id','resolved_by_cancellation_revision_id','resolution_at']::text[]
    IS DISTINCT FROM to_jsonb(OLD)-ARRAY['resolved_decision_id','resolved_by_cancellation_revision_id','resolution_at']::text[]
    THEN RAISE EXCEPTION 'appeal submission is immutable'; END IF;
  IF OLD.resolution_at IS NOT NULL AND NEW IS DISTINCT FROM OLD
    THEN RAISE EXCEPTION 'appeal resolution is one way'; END IF;
  IF (NEW.resolved_decision_id IS NOT NULL)::integer
    + (NEW.resolved_by_cancellation_revision_id IS NOT NULL)::integer > 1
    OR (NEW.resolution_at IS NOT NULL) IS DISTINCT FROM
       (NEW.resolved_decision_id IS NOT NULL OR NEW.resolved_by_cancellation_revision_id IS NOT NULL)
    THEN RAISE EXCEPTION 'appeal resolution shape mismatch'; END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER reimbursement_appeal_resolution BEFORE UPDATE OR DELETE ON event_reimbursements_claimappeal
  FOR EACH ROW EXECUTE FUNCTION reimbursement_appeal_resolution_guard();
"""
REVERSE = """
DROP TRIGGER reimbursement_appeal_resolution ON event_reimbursements_claimappeal;
DROP FUNCTION reimbursement_appeal_resolution_guard();
DROP TRIGGER reimbursement_accepted_award ON event_reimbursements_grantaward;
DROP FUNCTION reimbursement_accepted_award_guard();
"""


class Migration(migrations.Migration):
    dependencies = [("event_reimbursements", "0003_reimbursement_guards")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
