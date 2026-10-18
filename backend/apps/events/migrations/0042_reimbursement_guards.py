"""Frozen scope, write-fence and append-only backstops for add-on rows."""
from django.db import migrations

# (table, tenant expression, relational checks, maintenance-only PII, immutable)
RULES = (
    (
        'events_eventstageform',
        '(SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=NEW.event_id)',
        [
            "IF NEW.event_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event r WHERE r.id=NEW.event_id AND r.makerspace_id IS NOT DISTINCT FROM tenant_id AND r.id IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.current_revision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventformrevision r WHERE r.id=NEW.current_revision_id AND (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM tenant_id AND (SELECT s2.id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.current_revision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventformrevision r WHERE r.id=NEW.current_revision_id AND r.form_key='stage' AND r.selector_kind='stage' AND r.selector_id=NEW.id) THEN RAISE EXCEPTION 'stage revision selector mismatch'; END IF;",
        ],
        [], False,
    ),
    (
        'events_eventstagemilestone',
        '(SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=NEW.event_id)',
        [
            "IF NEW.event_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event r WHERE r.id=NEW.event_id AND r.makerspace_id IS NOT DISTINCT FROM tenant_id AND r.id IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.registration_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventregistration r WHERE r.id=NEW.registration_id AND (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM tenant_id AND (SELECT s2.id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.application_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonapplication r WHERE r.id=NEW.application_id AND (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM tenant_id AND (SELECT s2.id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.member_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts_user WHERE id=NEW.member_id AND account_kind='member') THEN RAISE EXCEPTION 'reimbursement requires member identity'; END IF;",
            "IF NEW.registration_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventregistration r WHERE r.id=NEW.registration_id AND r.member_id=NEW.member_id) THEN RAISE EXCEPTION 'reimbursement owner mismatch'; END IF;",
            "IF NEW.application_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonapplication r WHERE r.id=NEW.application_id AND r.member_id=NEW.member_id) THEN RAISE EXCEPTION 'reimbursement owner mismatch'; END IF;",
        ],
        [], False,
    ),
    (
        'events_stageformassignment',
        '(SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=NEW.event_id)',
        [
            "IF NEW.stage_form_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventstageform r WHERE r.id=NEW.stage_form_id AND (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM tenant_id AND (SELECT s2.id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.event_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event r WHERE r.id=NEW.event_id AND r.makerspace_id IS NOT DISTINCT FROM tenant_id AND r.id IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.owner_member_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts_user WHERE id=NEW.owner_member_id AND account_kind='member') THEN RAISE EXCEPTION 'reimbursement requires member identity'; END IF;",
            "IF NEW.registration_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventregistration r WHERE r.id=NEW.registration_id AND (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM tenant_id AND (SELECT s2.id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.application_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonapplication r WHERE r.id=NEW.application_id AND (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM tenant_id AND (SELECT s2.id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.pinned_form_revision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventformrevision r WHERE r.id=NEW.pinned_form_revision_id AND (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM tenant_id AND (SELECT s2.id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.completed_response_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_stageformresponse r WHERE r.id=NEW.completed_response_id AND (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM tenant_id AND (SELECT s2.id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.registration_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventregistration r WHERE r.id=NEW.registration_id AND r.member_id=NEW.owner_member_id) THEN RAISE EXCEPTION 'reimbursement owner mismatch'; END IF;",
            "IF NEW.application_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonapplication r WHERE r.id=NEW.application_id AND r.member_id=NEW.owner_member_id) THEN RAISE EXCEPTION 'reimbursement owner mismatch'; END IF;",
            "IF NOT EXISTS (SELECT 1 FROM events_eventformrevision r WHERE r.id=NEW.pinned_form_revision_id AND r.form_key='stage' AND r.selector_kind='stage' AND r.selector_id=NEW.stage_form_id) THEN RAISE EXCEPTION 'stage assignment revision mismatch'; END IF;",
            "IF NEW.completed_response_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_stageformresponse r WHERE r.id=NEW.completed_response_id AND r.assignment_id=NEW.id AND r.owner_member_id=NEW.owner_member_id) THEN RAISE EXCEPTION 'stage completed response mismatch'; END IF;",
        ],
        ['extension_reason', 'cancellation_reason', 'reassignment_reason'], False,
    ),
    (
        'events_stageformresponse',
        '(SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=NEW.event_id)',
        [
            "IF NEW.assignment_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_stageformassignment r WHERE r.id=NEW.assignment_id AND (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM tenant_id AND (SELECT s2.id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.event_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event r WHERE r.id=NEW.event_id AND r.makerspace_id IS NOT DISTINCT FROM tenant_id AND r.id IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.owner_member_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts_user WHERE id=NEW.owner_member_id AND account_kind='member') THEN RAISE EXCEPTION 'reimbursement requires member identity'; END IF;",
            "IF NEW.form_revision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventformrevision r WHERE r.id=NEW.form_revision_id AND (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM tenant_id AND (SELECT s2.id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.current_submitted_revision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_stageformresponserevision r WHERE r.id=NEW.current_submitted_revision_id AND (SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM events_stageformresponse s3 WHERE s3.id=r.response_id) IS NOT DISTINCT FROM tenant_id AND (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM events_stageformresponse s3 WHERE s3.id=r.response_id) IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.assignment_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_stageformassignment r WHERE r.id=NEW.assignment_id AND r.owner_member_id=NEW.owner_member_id) THEN RAISE EXCEPTION 'reimbursement owner mismatch'; END IF;",
            "IF NOT EXISTS (SELECT 1 FROM events_stageformassignment a WHERE a.id=NEW.assignment_id AND a.pinned_form_revision_id=NEW.form_revision_id) THEN RAISE EXCEPTION 'stage response revision mismatch'; END IF;",
            "IF NEW.current_submitted_revision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_stageformresponserevision r WHERE r.id=NEW.current_submitted_revision_id AND r.response_id=NEW.id AND r.form_revision_id=NEW.form_revision_id) THEN RAISE EXCEPTION 'stage submitted revision mismatch'; END IF;",
        ],
        ['answers_snapshot'], False,
    ),
    (
        'events_stageformresponserevision',
        '(SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM events_stageformresponse s3 WHERE s3.id=NEW.response_id)',
        [
            "IF NEW.response_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_stageformresponse r WHERE r.id=NEW.response_id AND (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM tenant_id AND (SELECT s2.id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM events_stageformresponse s3 WHERE s3.id=NEW.response_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.form_revision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventformrevision r WHERE r.id=NEW.form_revision_id AND (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM tenant_id AND (SELECT s2.id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM events_stageformresponse s3 WHERE s3.id=NEW.response_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF TG_OP='INSERT' AND NOT EXISTS (SELECT 1 FROM events_stageformresponse r WHERE r.id=NEW.response_id AND r.form_revision_id=NEW.form_revision_id) THEN RAISE EXCEPTION 'submitted response form mismatch'; END IF;",
        ],
        ['answers_snapshot'], True,
    ),
    (
        'events_stageformasset',
        '(SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=NEW.event_id)',
        [
            "IF NEW.event_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event r WHERE r.id=NEW.event_id AND r.makerspace_id IS NOT DISTINCT FROM tenant_id AND r.id IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.assignment_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_stageformassignment r WHERE r.id=NEW.assignment_id AND (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM tenant_id AND (SELECT s2.id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.owner_member_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts_user WHERE id=NEW.owner_member_id AND account_kind='member') THEN RAISE EXCEPTION 'reimbursement requires member identity'; END IF;",
            "IF NEW.response_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_stageformresponse r WHERE r.id=NEW.response_id AND (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM tenant_id AND (SELECT s2.id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.form_revision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventformrevision r WHERE r.id=NEW.form_revision_id AND (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM tenant_id AND (SELECT s2.id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NOT EXISTS (SELECT 1 FROM events_stageformassignment a WHERE a.id=NEW.assignment_id AND a.owner_member_id=NEW.owner_member_id AND a.pinned_form_revision_id=NEW.form_revision_id) THEN RAISE EXCEPTION 'stage asset assignment mismatch'; END IF;",
            "IF NEW.response_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_stageformresponse r WHERE r.id=NEW.response_id AND r.assignment_id=NEW.assignment_id AND r.owner_member_id=NEW.owner_member_id) THEN RAISE EXCEPTION 'stage asset response mismatch'; END IF;",
        ],
        ['original_filename'], False,
    ),
    (
        'events_eventattendancecorrection',
        '(SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=NEW.event_id)',
        [
            "IF NEW.registration_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventregistration r WHERE r.id=NEW.registration_id AND (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM tenant_id AND (SELECT s2.id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.event_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event r WHERE r.id=NEW.event_id AND r.makerspace_id IS NOT DISTINCT FROM tenant_id AND r.id IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
        ],
        [], True,
    ),
)

FORWARD, REVERSE = [], []
for table, host, checks, pii, immutable in RULES:
    function = table + "_rg_guard"
    history = ""
    if immutable:
        history = """
  IF TG_OP='DELETE' THEN
    IF current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
    RAISE EXCEPTION 'reimbursement history is immutable';
  END IF;
  IF TG_OP='UPDATE' THEN
    RAISE EXCEPTION 'reimbursement history is immutable';
  END IF;
"""
        if pii:
            exclusions = "ARRAY[" + ",".join("'" + p + "'" for p in pii) + "]::text[]"
            history = history.replace("  IF TG_OP='UPDATE' THEN", f"  IF TG_OP='UPDATE' AND NOT (to_jsonb(NEW)-{exclusions}=to_jsonb(OLD)-{exclusions} AND reimbursement_maintenance_allowed({host})) THEN")

    FORWARD.append(f"""
CREATE FUNCTION {function}() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE tenant_id bigint;
BEGIN
{history}
  tenant_id := {host};
  IF tenant_id IS NULL THEN RAISE EXCEPTION 'reimbursement host missing'; END IF;
  PERFORM pii_assert_mapped_write_allowed(tenant_id);
  {' '.join(checks)}
  RETURN NEW;
END; $$;
CREATE TRIGGER {table}_rg_guard BEFORE INSERT OR UPDATE{' OR DELETE' if immutable else ''}
ON {table} FOR EACH ROW EXECUTE FUNCTION {function}();
""")
    REVERSE.insert(0, f"DROP TRIGGER {table}_rg_guard ON {table}; DROP FUNCTION {function}();")


class Migration(migrations.Migration):
    dependencies = [('events', '0041_reimbursement_relations_1'), ('encryption', '0010_mandatory_finance_envelopes')]
    operations = [migrations.RunSQL('\n'.join(FORWARD), '\n'.join(REVERSE))]
