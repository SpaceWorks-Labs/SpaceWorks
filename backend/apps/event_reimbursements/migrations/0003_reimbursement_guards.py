"""Frozen scope, write-fence and append-only backstops for add-on rows."""
from django.db import migrations

# (table, tenant expression, relational checks, maintenance-only PII, immutable)
RULES = (
    (
        'event_reimbursements_grantaward',
        '(SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_grantrequest s3 WHERE s3.id=NEW.request_id)',
        [
            "IF NEW.request_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_grantrequest r WHERE r.id=NEW.request_id AND (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM tenant_id AND (SELECT s2.id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_grantrequest s3 WHERE s3.id=NEW.request_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.pool_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_reimbursementbudgetpool r WHERE r.id=NEW.pool_id AND (SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementprogramme s3 WHERE s3.id=r.programme_id) IS NOT DISTINCT FROM tenant_id AND (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementprogramme s3 WHERE s3.id=r.programme_id) IS NOT DISTINCT FROM (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_grantrequest s3 WHERE s3.id=NEW.request_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NOT EXISTS (SELECT 1 FROM event_reimbursements_grantrequest r JOIN event_reimbursements_reimbursementbudgetpool p ON p.programme_id=r.programme_id WHERE r.id=NEW.request_id AND p.id=NEW.pool_id AND p.currency=NEW.currency) THEN RAISE EXCEPTION 'award pool binding mismatch'; END IF;",
        ],
        ['note'], False,
    ),
    (
        'event_reimbursements_grantawardrevision',
        '(SELECT (SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_grantrequest s3 WHERE s3.id=s4.request_id) FROM event_reimbursements_grantaward s4 WHERE s4.id=NEW.award_id)',
        [
            "IF NEW.award_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_grantaward r WHERE r.id=NEW.award_id AND (SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_grantrequest s3 WHERE s3.id=r.request_id) IS NOT DISTINCT FROM tenant_id AND (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_grantrequest s3 WHERE s3.id=r.request_id) IS NOT DISTINCT FROM (SELECT (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_grantrequest s3 WHERE s3.id=s4.request_id) FROM event_reimbursements_grantaward s4 WHERE s4.id=NEW.award_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
        ],
        [], True,
    ),
    (
        'event_reimbursements_reimbursementbudgetpool',
        '(SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementprogramme s3 WHERE s3.id=NEW.programme_id)',
        [
            "IF NEW.programme_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_reimbursementprogramme r WHERE r.id=NEW.programme_id AND (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM tenant_id AND (SELECT s2.id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementprogramme s3 WHERE s3.id=NEW.programme_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
        ],
        [], False,
    ),
    (
        'event_reimbursements_budgetreservation',
        '(SELECT (SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementprogramme s3 WHERE s3.id=s4.programme_id) FROM event_reimbursements_reimbursementbudgetpool s4 WHERE s4.id=NEW.pool_id)',
        [
            "IF NEW.pool_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_reimbursementbudgetpool r WHERE r.id=NEW.pool_id AND (SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementprogramme s3 WHERE s3.id=r.programme_id) IS NOT DISTINCT FROM tenant_id AND (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementprogramme s3 WHERE s3.id=r.programme_id) IS NOT DISTINCT FROM (SELECT (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=s4.claim_id) FROM event_reimbursements_claimdecision s4 WHERE s4.id=NEW.decision_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.award_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_grantaward r WHERE r.id=NEW.award_id AND (SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_grantrequest s3 WHERE s3.id=r.request_id) IS NOT DISTINCT FROM tenant_id AND (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_grantrequest s3 WHERE s3.id=r.request_id) IS NOT DISTINCT FROM (SELECT (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=s4.claim_id) FROM event_reimbursements_claimdecision s4 WHERE s4.id=NEW.decision_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.decision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_claimdecision r WHERE r.id=NEW.decision_id AND (SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=r.claim_id) IS NOT DISTINCT FROM tenant_id AND (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=r.claim_id) IS NOT DISTINCT FROM (SELECT (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=s4.claim_id) FROM event_reimbursements_claimdecision s4 WHERE s4.id=NEW.decision_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NOT EXISTS (SELECT 1 FROM event_reimbursements_grantaward a WHERE a.id=NEW.award_id AND a.pool_id=NEW.pool_id) THEN RAISE EXCEPTION 'reservation pool binding mismatch'; END IF;",
        ],
        [], False,
    ),
    (
        'event_reimbursements_budgetentry',
        '(SELECT (SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementprogramme s3 WHERE s3.id=s4.programme_id) FROM event_reimbursements_reimbursementbudgetpool s4 WHERE s4.id=NEW.pool_id)',
        [
            "IF NEW.pool_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_reimbursementbudgetpool r WHERE r.id=NEW.pool_id AND (SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementprogramme s3 WHERE s3.id=r.programme_id) IS NOT DISTINCT FROM tenant_id AND (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementprogramme s3 WHERE s3.id=r.programme_id) IS NOT DISTINCT FROM (SELECT (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=s4.claim_id) FROM event_reimbursements_claimdecision s4 WHERE s4.id=NEW.decision_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.reservation_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_budgetreservation r WHERE r.id=NEW.reservation_id AND (SELECT (SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementprogramme s3 WHERE s3.id=s4.programme_id) FROM event_reimbursements_reimbursementbudgetpool s4 WHERE s4.id=r.pool_id) IS NOT DISTINCT FROM tenant_id AND (SELECT (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=s4.claim_id) FROM event_reimbursements_claimdecision s4 WHERE s4.id=r.decision_id) IS NOT DISTINCT FROM (SELECT (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=s4.claim_id) FROM event_reimbursements_claimdecision s4 WHERE s4.id=NEW.decision_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.decision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_claimdecision r WHERE r.id=NEW.decision_id AND (SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=r.claim_id) IS NOT DISTINCT FROM tenant_id AND (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=r.claim_id) IS NOT DISTINCT FROM (SELECT (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=s4.claim_id) FROM event_reimbursements_claimdecision s4 WHERE s4.id=NEW.decision_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
        ],
        [], True,
    ),
    (
        'event_reimbursements_claimdecision',
        '(SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=NEW.claim_id)',
        [
            "IF NEW.claim_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_reimbursementclaim r WHERE r.id=NEW.claim_id AND (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM tenant_id AND (SELECT s2.id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=NEW.claim_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.revision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_claimrevision r WHERE r.id=NEW.revision_id AND (SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=r.claim_id) IS NOT DISTINCT FROM tenant_id AND (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=r.claim_id) IS NOT DISTINCT FROM (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=NEW.claim_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NOT EXISTS (SELECT 1 FROM event_reimbursements_claimrevision r WHERE r.id=NEW.revision_id AND r.claim_id=NEW.claim_id) THEN RAISE EXCEPTION 'decision claim revision mismatch'; END IF;",
        ],
        ['reason'], True,
    ),
    (
        'event_reimbursements_claimlinedecision',
        '(SELECT (SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=s4.claim_id) FROM event_reimbursements_claimdecision s4 WHERE s4.id=NEW.decision_id)',
        [
            "IF NEW.decision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_claimdecision r WHERE r.id=NEW.decision_id AND (SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=r.claim_id) IS NOT DISTINCT FROM tenant_id AND (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=r.claim_id) IS NOT DISTINCT FROM (SELECT (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=s4.claim_id) FROM event_reimbursements_claimdecision s4 WHERE s4.id=NEW.decision_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.line_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_claimline r WHERE r.id=NEW.line_id AND (SELECT (SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=s4.claim_id) FROM event_reimbursements_claimrevision s4 WHERE s4.id=r.revision_id) IS NOT DISTINCT FROM tenant_id AND (SELECT (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=s4.claim_id) FROM event_reimbursements_claimrevision s4 WHERE s4.id=r.revision_id) IS NOT DISTINCT FROM (SELECT (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=s4.claim_id) FROM event_reimbursements_claimdecision s4 WHERE s4.id=NEW.decision_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NOT EXISTS (SELECT 1 FROM event_reimbursements_claimdecision d JOIN event_reimbursements_claimline l ON l.revision_id=d.revision_id WHERE d.id=NEW.decision_id AND l.id=NEW.line_id AND NEW.approved_minor<=l.converted_minor) THEN RAISE EXCEPTION 'claim line decision mismatch'; END IF;",
        ],
        ['reason'], True,
    ),
    (
        'event_reimbursements_claimappeal',
        '(SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=NEW.claim_id)',
        [
            "IF NEW.claim_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_reimbursementclaim r WHERE r.id=NEW.claim_id AND (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM tenant_id AND (SELECT s2.id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=NEW.claim_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.original_decision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_claimdecision r WHERE r.id=NEW.original_decision_id AND (SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=r.claim_id) IS NOT DISTINCT FROM tenant_id AND (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=r.claim_id) IS NOT DISTINCT FROM (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=NEW.claim_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.resolved_decision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_claimdecision r WHERE r.id=NEW.resolved_decision_id AND (SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=r.claim_id) IS NOT DISTINCT FROM tenant_id AND (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=r.claim_id) IS NOT DISTINCT FROM (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=NEW.claim_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NOT EXISTS (SELECT 1 FROM event_reimbursements_claimdecision d WHERE d.id=NEW.original_decision_id AND d.claim_id=NEW.claim_id) OR (NEW.resolved_decision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_claimdecision d WHERE d.id=NEW.resolved_decision_id AND d.claim_id=NEW.claim_id)) THEN RAISE EXCEPTION 'appeal decision binding mismatch'; END IF;",
        ],
        ['statement'], False,
    ),
    (
        'event_reimbursements_claimscreeningreview',
        '(SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=NEW.claim_id)',
        [
            "IF NEW.claim_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_reimbursementclaim r WHERE r.id=NEW.claim_id AND (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM tenant_id AND (SELECT s2.id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=NEW.claim_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.revision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_claimrevision r WHERE r.id=NEW.revision_id AND (SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=r.claim_id) IS NOT DISTINCT FROM tenant_id AND (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=r.claim_id) IS NOT DISTINCT FROM (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=NEW.claim_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NOT EXISTS (SELECT 1 FROM event_reimbursements_claimrevision r WHERE r.id=NEW.revision_id AND r.claim_id=NEW.claim_id) THEN RAISE EXCEPTION 'review claim revision mismatch'; END IF;",
        ],
        ['note'], True,
    ),
    (
        'event_reimbursements_claimattendanceattestation',
        '(SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=NEW.claim_id)',
        [
            "IF NEW.claim_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_reimbursementclaim r WHERE r.id=NEW.claim_id AND (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM tenant_id AND (SELECT s2.id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.registration_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventregistration r WHERE r.id=NEW.registration_id AND (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM tenant_id AND (SELECT s2.id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.event_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event r WHERE r.id=NEW.event_id AND r.makerspace_id IS NOT DISTINCT FROM tenant_id AND r.id IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.owner_member_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts_user WHERE id=NEW.owner_member_id AND account_kind='member') THEN RAISE EXCEPTION 'reimbursement requires member identity'; END IF;",
            "IF NOT EXISTS (SELECT 1 FROM event_reimbursements_reimbursementclaim c JOIN events_eventregistration r ON r.event_id=c.event_id AND r.member_id=c.member_id WHERE c.id=NEW.claim_id AND r.id=NEW.registration_id AND c.member_id=NEW.owner_member_id) THEN RAISE EXCEPTION 'attestation owner binding mismatch'; END IF;",
        ],
        ['note'], True,
    ),
    (
        'event_reimbursements_reimbursementclaim',
        '(SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=NEW.event_id)',
        [
            "IF NEW.award_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_grantaward r WHERE r.id=NEW.award_id AND (SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_grantrequest s3 WHERE s3.id=r.request_id) IS NOT DISTINCT FROM tenant_id AND (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_grantrequest s3 WHERE s3.id=r.request_id) IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.event_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event r WHERE r.id=NEW.event_id AND r.makerspace_id IS NOT DISTINCT FROM tenant_id AND r.id IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.member_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts_user WHERE id=NEW.member_id AND account_kind='member') THEN RAISE EXCEPTION 'reimbursement requires member identity'; END IF;",
            "IF NEW.current_revision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_claimrevision r WHERE r.id=NEW.current_revision_id AND (SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=r.claim_id) IS NOT DISTINCT FROM tenant_id AND (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=r.claim_id) IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.current_decision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_claimdecision r WHERE r.id=NEW.current_decision_id AND (SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=r.claim_id) IS NOT DISTINCT FROM tenant_id AND (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=r.claim_id) IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NOT EXISTS (SELECT 1 FROM event_reimbursements_grantaward a JOIN event_reimbursements_grantrequest r ON r.id=a.request_id WHERE a.id=NEW.award_id AND r.member_id=NEW.member_id AND r.event_id=NEW.event_id) THEN RAISE EXCEPTION 'claim owner binding mismatch'; END IF;",
        ],
        ['draft_payload', 'extension_reason'], False,
    ),
    (
        'event_reimbursements_reimbursementworkitem',
        '(SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=NEW.event_id)',
        [
            "IF NEW.event_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event r WHERE r.id=NEW.event_id AND r.makerspace_id IS NOT DISTINCT FROM tenant_id AND r.id IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.award_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_grantaward r WHERE r.id=NEW.award_id AND (SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_grantrequest s3 WHERE s3.id=r.request_id) IS NOT DISTINCT FROM tenant_id AND (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_grantrequest s3 WHERE s3.id=r.request_id) IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.claim_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_reimbursementclaim r WHERE r.id=NEW.claim_id AND (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM tenant_id AND (SELECT s2.id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
        ],
        [], False,
    ),
    (
        'event_reimbursements_claimrevision',
        '(SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=NEW.claim_id)',
        [
            "IF NEW.claim_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_reimbursementclaim r WHERE r.id=NEW.claim_id AND (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM tenant_id AND (SELECT s2.id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=NEW.claim_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
        ],
        [], True,
    ),
    (
        'event_reimbursements_claimline',
        '(SELECT (SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=s4.claim_id) FROM event_reimbursements_claimrevision s4 WHERE s4.id=NEW.revision_id)',
        [
            "IF NEW.revision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_claimrevision r WHERE r.id=NEW.revision_id AND (SELECT (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=r.claim_id) IS NOT DISTINCT FROM tenant_id AND (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=r.claim_id) IS NOT DISTINCT FROM (SELECT (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=s4.claim_id) FROM event_reimbursements_claimrevision s4 WHERE s4.id=NEW.revision_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.finance_asset_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM payments_financeattachment r WHERE r.id=NEW.finance_asset_id AND r.makerspace_id IS NOT DISTINCT FROM tenant_id AND (SELECT s2.id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM (SELECT (SELECT (SELECT s2.id FROM events_event s2 WHERE s2.id=s3.event_id) FROM event_reimbursements_reimbursementclaim s3 WHERE s3.id=s4.claim_id) FROM event_reimbursements_claimrevision s4 WHERE s4.id=NEW.revision_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
        ],
        ['vendor', 'description', 'traveller', 'source_note', 'route'], True,
    ),
    (
        'event_reimbursements_reimbursementprogramme',
        '(SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=NEW.event_id)',
        [
            "IF NEW.event_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event r WHERE r.id=NEW.event_id AND r.makerspace_id IS NOT DISTINCT FROM tenant_id AND r.id IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
        ],
        [], False,
    ),
    (
        'event_reimbursements_grantrequest',
        '(SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=NEW.event_id)',
        [
            "IF NEW.programme_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_reimbursementprogramme r WHERE r.id=NEW.programme_id AND (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM tenant_id AND (SELECT s2.id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.event_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event r WHERE r.id=NEW.event_id AND r.makerspace_id IS NOT DISTINCT FROM tenant_id AND r.id IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.member_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts_user WHERE id=NEW.member_id AND account_kind='member') THEN RAISE EXCEPTION 'reimbursement requires member identity'; END IF;",
            "IF NEW.registration_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventregistration r WHERE r.id=NEW.registration_id AND (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM tenant_id AND (SELECT s2.id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.application_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonapplication r WHERE r.id=NEW.application_id AND (SELECT s2.makerspace_id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM tenant_id AND (SELECT s2.id FROM events_event s2 WHERE s2.id=r.event_id) IS NOT DISTINCT FROM (SELECT s2.id FROM events_event s2 WHERE s2.id=NEW.event_id)) THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
            "IF NEW.registration_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventregistration r WHERE r.id=NEW.registration_id AND r.member_id=NEW.member_id) THEN RAISE EXCEPTION 'reimbursement owner mismatch'; END IF;",
            "IF NEW.application_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonapplication r WHERE r.id=NEW.application_id AND r.member_id=NEW.member_id) THEN RAISE EXCEPTION 'reimbursement owner mismatch'; END IF;",
        ],
        ['origin', 'destination', 'need_statement', 'itinerary', 'estimated_cost', 'reason', 'eligibility_snapshot'], False,
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
    dependencies = [('event_reimbursements', '0002_reimbursement_relations_1'), ('encryption', '0010_mandatory_finance_envelopes')]
    operations = [migrations.RunSQL('\n'.join(FORWARD), '\n'.join(REVERSE))]
