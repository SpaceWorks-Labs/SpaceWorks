"""Frozen scope, write-fence and append-only backstops for add-on rows."""
from django.db import migrations

# (table, tenant expression, relational checks, maintenance-only PII, immutable)
RULES = (
    (
        'payments_financeattachment',
        'NEW.makerspace_id',
        [
            "IF NEW.event_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event r WHERE r.id=NEW.event_id AND r.makerspace_id IS NOT DISTINCT FROM tenant_id AND r.id IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.owner_member_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts_user WHERE id=NEW.owner_member_id AND account_kind='member') THEN RAISE EXCEPTION 'reimbursement requires member identity'; END IF;",
            "IF NEW.obligation_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM payments_eventpayoutobligation r WHERE r.id=NEW.obligation_id AND r.makerspace_id IS NOT DISTINCT FROM tenant_id AND (SELECT s2.id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.obligation_id IS NOT NULL AND NEW.owner_member_id IS NOT NULL AND EXISTS (SELECT 1 FROM payments_eventpayoutobligation o WHERE o.id=NEW.obligation_id AND o.owner_member_id IS NOT NULL AND o.owner_member_id<>NEW.owner_member_id) THEN RAISE EXCEPTION 'attachment owner mismatch'; END IF;",
        ],
        ['original_filename'], False,
    ),
    (
        'payments_payouteligibility',
        '(SELECT s2.makerspace_id FROM payments_eventpayoutobligation s2 WHERE s2.id=NEW.obligation_id)',
        [
            "IF NEW.obligation_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM payments_eventpayoutobligation r WHERE r.id=NEW.obligation_id AND r.makerspace_id IS NOT DISTINCT FROM tenant_id) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
        ],
        [], True,
    ),
    (
        'payments_payouthold',
        '(SELECT s2.makerspace_id FROM payments_eventpayoutobligation s2 WHERE s2.id=NEW.obligation_id)',
        [
            "IF NEW.obligation_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM payments_eventpayoutobligation r WHERE r.id=NEW.obligation_id AND r.makerspace_id IS NOT DISTINCT FROM tenant_id) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.releases_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM payments_payouthold r WHERE r.id=NEW.releases_id AND (SELECT s2.makerspace_id FROM payments_eventpayoutobligation s2 WHERE s2.id=r.obligation_id) IS NOT DISTINCT FROM tenant_id) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.releases_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM payments_payouthold h WHERE h.id=NEW.releases_id AND h.obligation_id=NEW.obligation_id AND h.action='hold' AND h.kind=NEW.kind) THEN RAISE EXCEPTION 'hold release binding mismatch'; END IF;",
        ],
        ['note'], True,
    ),
    (
        'payments_payoutexportbatch',
        'NEW.makerspace_id',
        [
        ],
        [], False,
    ),
    (
        'payments_payoutexportbatchitem',
        '(SELECT s2.makerspace_id FROM payments_payoutexportbatch s2 WHERE s2.id=NEW.batch_id)',
        [
            "IF NEW.batch_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM payments_payoutexportbatch r WHERE r.id=NEW.batch_id AND r.makerspace_id IS NOT DISTINCT FROM tenant_id) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.obligation_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM payments_eventpayoutobligation r WHERE r.id=NEW.obligation_id AND r.makerspace_id IS NOT DISTINCT FROM tenant_id) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.payee_revision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM payments_eventpayeerevision r WHERE r.id=NEW.payee_revision_id AND (SELECT s2.makerspace_id FROM payments_eventpayoutobligation s2 WHERE s2.id=r.obligation_id) IS NOT DISTINCT FROM tenant_id) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NOT EXISTS (SELECT 1 FROM payments_eventpayeerevision p WHERE p.id=NEW.payee_revision_id AND p.obligation_id=NEW.obligation_id) THEN RAISE EXCEPTION 'export payee binding mismatch'; END IF;",
        ],
        [], True,
    ),
    (
        'payments_eventpayoutobligation',
        'NEW.makerspace_id',
        [
            "IF NEW.owner_member_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts_user WHERE id=NEW.owner_member_id AND account_kind='member') THEN RAISE EXCEPTION 'reimbursement requires member identity'; END IF;",
            "IF NEW.event_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event r WHERE r.id=NEW.event_id AND r.makerspace_id IS NOT DISTINCT FROM tenant_id AND r.id IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.current_revision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM payments_eventpayoutobligationrevision r WHERE r.id=NEW.current_revision_id AND (SELECT s2.makerspace_id FROM payments_eventpayoutobligation s2 WHERE s2.id=r.obligation_id) IS NOT DISTINCT FROM tenant_id) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.current_revision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM payments_eventpayoutobligationrevision r WHERE r.id=NEW.current_revision_id AND r.obligation_id=NEW.id) THEN RAISE EXCEPTION 'obligation current revision mismatch'; END IF;",
        ],
        [], False,
    ),
    (
        'payments_eventpayoutobligationrevision',
        '(SELECT s2.makerspace_id FROM payments_eventpayoutobligation s2 WHERE s2.id=NEW.obligation_id)',
        [
            "IF NEW.obligation_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM payments_eventpayoutobligation r WHERE r.id=NEW.obligation_id AND r.makerspace_id IS NOT DISTINCT FROM tenant_id) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.previous_revision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM payments_eventpayoutobligationrevision r WHERE r.id=NEW.previous_revision_id AND (SELECT s2.makerspace_id FROM payments_eventpayoutobligation s2 WHERE s2.id=r.obligation_id) IS NOT DISTINCT FROM tenant_id) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NOT EXISTS (SELECT 1 FROM payments_eventpayoutobligation o WHERE o.id=NEW.obligation_id AND o.currency=NEW.currency) THEN RAISE EXCEPTION 'obligation revision currency mismatch'; END IF;",
            "IF NEW.previous_revision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM payments_eventpayoutobligationrevision p WHERE p.id=NEW.previous_revision_id AND p.obligation_id=NEW.obligation_id AND p.sequence+1=NEW.sequence AND p.currency=NEW.currency) THEN RAISE EXCEPTION 'obligation revision chain mismatch'; END IF;",
        ],
        ['cancellation_note', 'decision_summary'], True,
    ),
    (
        'payments_eventpayeerevision',
        '(SELECT s2.makerspace_id FROM payments_eventpayoutobligation s2 WHERE s2.id=NEW.obligation_id)',
        [
            "IF NEW.obligation_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM payments_eventpayoutobligation r WHERE r.id=NEW.obligation_id AND r.makerspace_id IS NOT DISTINCT FROM tenant_id) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.owner_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts_user WHERE id=NEW.owner_id AND account_kind='member') THEN RAISE EXCEPTION 'reimbursement requires member identity'; END IF;",
        ],
        ['details'], False,
    ),
    (
        'payments_eventpayeereview',
        '(SELECT s2.makerspace_id FROM payments_eventpayoutobligation s2 WHERE s2.id=NEW.obligation_id)',
        [
            "IF NEW.obligation_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM payments_eventpayoutobligation r WHERE r.id=NEW.obligation_id AND r.makerspace_id IS NOT DISTINCT FROM tenant_id) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.payee_revision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM payments_eventpayeerevision r WHERE r.id=NEW.payee_revision_id AND (SELECT s2.makerspace_id FROM payments_eventpayoutobligation s2 WHERE s2.id=r.obligation_id) IS NOT DISTINCT FROM tenant_id) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NOT EXISTS (SELECT 1 FROM payments_eventpayeerevision p WHERE p.id=NEW.payee_revision_id AND p.obligation_id=NEW.obligation_id) THEN RAISE EXCEPTION 'payee review obligation mismatch'; END IF;",
        ],
        ['note'], True,
    ),
    (
        'payments_eventpayoutentry',
        '(SELECT s2.makerspace_id FROM payments_eventpayoutobligation s2 WHERE s2.id=NEW.obligation_id)',
        [
            "IF NEW.obligation_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM payments_eventpayoutobligation r WHERE r.id=NEW.obligation_id AND r.makerspace_id IS NOT DISTINCT FROM tenant_id) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.payee_revision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM payments_eventpayeerevision r WHERE r.id=NEW.payee_revision_id AND (SELECT s2.makerspace_id FROM payments_eventpayoutobligation s2 WHERE s2.id=r.obligation_id) IS NOT DISTINCT FROM tenant_id) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.amends_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM payments_eventpayoutentry r WHERE r.id=NEW.amends_id AND (SELECT s2.makerspace_id FROM payments_eventpayoutobligation s2 WHERE s2.id=r.obligation_id) IS NOT DISTINCT FROM tenant_id) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NOT EXISTS (SELECT 1 FROM payments_eventpayoutobligation o WHERE o.id=NEW.obligation_id AND o.currency=NEW.currency) THEN RAISE EXCEPTION 'payout currency mismatch'; END IF;",
            "IF NEW.payee_revision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM payments_eventpayeerevision p WHERE p.id=NEW.payee_revision_id AND p.obligation_id=NEW.obligation_id) THEN RAISE EXCEPTION 'payout payee mismatch'; END IF;",
            "IF NEW.amends_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM payments_eventpayoutentry p WHERE p.id=NEW.amends_id AND p.obligation_id=NEW.obligation_id AND p.chain_uuid=NEW.chain_uuid AND p.currency=NEW.currency) THEN RAISE EXCEPTION 'payout amendment chain mismatch'; END IF;",
        ],
        [], True,
    ),
    (
        'payments_receiptuse',
        'NEW.makerspace_id',
        [
        ],
        [], False,
    ),
    (
        'payments_receiptallocationoverride',
        '(SELECT s2.makerspace_id FROM payments_receiptuse s2 WHERE s2.id=NEW.receipt_use_id)',
        [
            "IF NEW.receipt_use_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM payments_receiptuse r WHERE r.id=NEW.receipt_use_id AND r.makerspace_id IS NOT DISTINCT FROM tenant_id) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
        ],
        ['note'], True,
    ),
    (
        'payments_receiptallocation',
        '(SELECT s2.makerspace_id FROM payments_receiptuse s2 WHERE s2.id=NEW.receipt_use_id)',
        [
            "IF NEW.receipt_use_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM payments_receiptuse r WHERE r.id=NEW.receipt_use_id AND r.makerspace_id IS NOT DISTINCT FROM tenant_id) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.override_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM payments_receiptallocationoverride r WHERE r.id=NEW.override_id AND (SELECT s2.makerspace_id FROM payments_receiptuse s2 WHERE s2.id=r.receipt_use_id) IS NOT DISTINCT FROM tenant_id) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.override_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM payments_receiptallocationoverride o WHERE o.id=NEW.override_id AND o.receipt_use_id=NEW.receipt_use_id) THEN RAISE EXCEPTION 'receipt override binding mismatch'; END IF;",
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
    dependencies = [('payments', '0027_reimbursement_relations_1'), ('encryption', '0010_mandatory_finance_envelopes')]
    operations = [migrations.RunSQL('\n'.join(FORWARD), '\n'.join(REVERSE))]
