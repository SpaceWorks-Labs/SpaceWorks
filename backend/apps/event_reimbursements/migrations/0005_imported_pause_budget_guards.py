"""Imported programmes stay paused; budget guards resolve scope through the pool.

0003 derived the comparison event for reservations and budget entries through the
nullable decision, so the first fund/reserve rows (decision NULL) were refused. The
replacement bodies anchor scope on pool -> programme -> event, check the award/pool
binding unconditionally, and check a decision only when one is present. Tenant
resolution, the write fence and the immutable-entry history block are unchanged.
"""
import importlib

from django.db import migrations, models

_G = importlib.import_module("apps.event_reimbursements.migrations.0003_reimbursement_guards")
_RULES = {rule[0]: rule for rule in _G.RULES}
_TABLES = [rule[0] for rule in _G.RULES]

NEW_CHECKS = {
    "event_reimbursements_budgetreservation": [
        "IF NOT EXISTS (SELECT 1 FROM event_reimbursements_grantaward a"
        " JOIN event_reimbursements_grantrequest q ON q.id=a.request_id"
        " JOIN event_reimbursements_reimbursementbudgetpool p ON p.id=NEW.pool_id"
        " WHERE a.id=NEW.award_id AND a.pool_id=NEW.pool_id AND q.programme_id=p.programme_id)"
        " THEN RAISE EXCEPTION 'reservation pool binding mismatch'; END IF;",
        "IF NEW.decision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_claimdecision d"
        " JOIN event_reimbursements_reimbursementclaim c ON c.id=d.claim_id"
        " WHERE d.id=NEW.decision_id AND c.award_id=NEW.award_id)"
        " THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
    ],
    "event_reimbursements_budgetentry": [
        "IF NEW.reservation_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_budgetreservation r"
        " WHERE r.id=NEW.reservation_id AND r.pool_id=NEW.pool_id)"
        " THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
        "IF NEW.decision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM event_reimbursements_claimdecision d"
        " JOIN event_reimbursements_reimbursementclaim c ON c.id=d.claim_id"
        " JOIN event_reimbursements_budgetreservation r ON r.award_id=c.award_id"
        " JOIN event_reimbursements_reimbursementbudgetpool p ON p.id=r.pool_id"
        " WHERE d.id=NEW.decision_id AND r.id=NEW.reservation_id AND d.currency=p.currency)"
        " THEN RAISE EXCEPTION 'reimbursement scope mismatch'; END IF;",
    ],
}


def _function_body(table):
    text = _G.FORWARD[_TABLES.index(table)]
    body = text[:text.index("CREATE TRIGGER")]
    return body.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)


def _replaced(table):
    old = " ".join(_RULES[table][2])
    body = _function_body(table)
    if body.count(old) != 1:
        raise RuntimeError(f"0003 guard for {table} no longer matches its frozen checks")
    return body.replace(old, " ".join(NEW_CHECKS[table]))


FORWARD = "\n".join(_replaced(table) for table in NEW_CHECKS)
REVERSE = "\n".join(_function_body(table) for table in NEW_CHECKS)


class Migration(migrations.Migration):

    dependencies = [
        ("event_reimbursements", "0004_award_appeal_guards"),
    ]

    operations = [
        migrations.AddField(
            model_name="reimbursementprogramme",
            name="imported_paused",
            field=models.BooleanField(default=False),
        ),
        migrations.RunSQL(FORWARD, REVERSE),
    ]
