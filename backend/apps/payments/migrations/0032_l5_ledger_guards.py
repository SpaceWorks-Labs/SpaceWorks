"""Lane L5 database guards: late captures, held receipts, frozen tax, append-only finance rows.

* The charge guard (live body from 0015, reproduced) also admits `canceled -> paid_online`
  with the amount unchanged, only under the transaction-local
  `app.allow_late_capture_settlement` GUC: money that arrived for a cancelled charge is
  recorded and flagged, never refused (capture flags, G24).
* A second charge trigger keeps `tax_snapshot` immutable and lets `method_label` fill
  once, from blank (G20, G26).
* The document guard (live body from 0022) lets a receipt carry less or more than the
  charge only when a staff member released the held receipt "on the amount received".
* Ledger entries void once and never change otherwise; opening balances, event budgets
  and dispute history are insert-only; claims, confirmations and capture flags are decided
  once. `app.allow_immutable_delete` keeps the tenant purge path working.
"""

from importlib import import_module

from django.db import migrations

LATE_CLAUSE = """    IF current_setting('app.allow_late_capture_settlement', true) = 'on'
       AND OLD.status = 'canceled' AND NEW.status = 'paid_online' AND NEW.amount = OLD.amount THEN
      RETURN NEW;
    END IF;
    RAISE EXCEPTION 'terminal payment is immutable';"""
RECEIVED_CLAUSE = """(NEW.kind <> 'receipt' OR (NEW.amount <> charge.amount AND NOT EXISTS(
         SELECT 1 FROM payments_paymentcaptureflag flag WHERE flag.payment_id = NEW.payment_id
           AND flag.resolution = 'issue_received' AND flag.captured_amount = NEW.amount)) OR"""

CHARGE_L5_SQL = """
CREATE OR REPLACE FUNCTION payments_payment_l5_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.tax_snapshot IS DISTINCT FROM OLD.tax_snapshot THEN
    RAISE EXCEPTION 'a charge tax snapshot is immutable';
  END IF;
  IF OLD.method_label <> '' AND NEW.method_label IS DISTINCT FROM OLD.method_label THEN
    RAISE EXCEPTION 'a payment method label is set once';
  END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER payments_payment_l5_guard BEFORE UPDATE ON payments_payment
FOR EACH ROW EXECUTE FUNCTION payments_payment_l5_guard();
"""

APPEND_ONLY_SQL = """
CREATE OR REPLACE FUNCTION payments_l5_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  -- The tenant purge path (and the SET NULL cascades it causes) runs under this GUC.
  IF current_setting('app.allow_immutable_delete', true) = 'on' THEN RETURN COALESCE(NEW, OLD); END IF;
  IF TG_OP = 'DELETE' THEN RAISE EXCEPTION '% rows are append-only', TG_TABLE_NAME; END IF;
  IF TG_TABLE_NAME = 'payments_ledgerentry' THEN
    -- Void once; or an event / machine type removed elsewhere clears its link (SET NULL).
    IF OLD.voided_at IS NULL AND NEW.voided_at IS NOT NULL AND
       (to_jsonb(NEW) - 'voided_at' - 'voided_by_id' - 'void_reason') =
       (to_jsonb(OLD) - 'voided_at' - 'voided_by_id' - 'void_reason') THEN
      RETURN NEW;
    END IF;
    IF (to_jsonb(NEW) - 'event_id' - 'machine_type_id') = (to_jsonb(OLD) - 'event_id' - 'machine_type_id') THEN
      IF (NEW.event_id IS NULL OR NEW.event_id = OLD.event_id) AND
         (NEW.machine_type_id IS NULL OR NEW.machine_type_id = OLD.machine_type_id) THEN
        RETURN NEW;
      END IF;
    END IF;
  ELSIF TG_TABLE_NAME = 'payments_eventfinancebudget' THEN
    IF NEW.event_id IS NULL AND (to_jsonb(NEW) - 'event_id') = (to_jsonb(OLD) - 'event_id') THEN RETURN NEW; END IF;
  ELSIF TG_TABLE_NAME = 'payments_paymentclaim' THEN
    IF OLD.status IN ('submitted', 'awaiting_confirmation') THEN RETURN NEW; END IF;
    IF NEW.pay_link_id IS NULL AND (to_jsonb(NEW) - 'pay_link_id') = (to_jsonb(OLD) - 'pay_link_id') THEN
      RETURN NEW;
    END IF;
  ELSIF TG_TABLE_NAME = 'payments_settlementconfirmation' THEN
    IF OLD.status = 'awaiting_confirmation' THEN RETURN NEW; END IF;
  ELSIF TG_TABLE_NAME = 'payments_paymentcaptureflag' THEN
    IF OLD.resolution = '' THEN RETURN NEW; END IF;
  ELSIF TG_TABLE_NAME = 'payments_paymentdispute' THEN
    IF NEW.payment_id = OLD.payment_id AND NEW.provider = OLD.provider
       AND NEW.provider_dispute_id = OLD.provider_dispute_id THEN RETURN NEW; END IF;
  ELSIF TG_TABLE_NAME = 'payments_paymentpaylink' THEN
    IF NEW.token_digest = OLD.token_digest AND NEW.payment_id = OLD.payment_id
       AND (OLD.revoked_at IS NULL OR NEW.revoked_at = OLD.revoked_at) THEN RETURN NEW; END IF;
  END IF;
  RAISE EXCEPTION '% rows are append-only', TG_TABLE_NAME;
END; $$;
""" + "".join(f"""
CREATE TRIGGER {table}_l5_guard BEFORE UPDATE OR DELETE ON {table}
FOR EACH ROW EXECUTE FUNCTION payments_l5_append_only();
""" for table in (
    "payments_ledgerentry", "payments_openingbalance", "payments_eventfinancebudget",
    "payments_paymentdisputeevent", "payments_paymentdispute", "payments_paymentclaim",
    "payments_settlementconfirmation", "payments_paymentcaptureflag", "payments_paymentpaylink",
))

DROP_SQL = """
DROP TRIGGER IF EXISTS payments_payment_l5_guard ON payments_payment;
DROP FUNCTION IF EXISTS payments_payment_l5_guard();
""" + "".join(f"DROP TRIGGER IF EXISTS {table}_l5_guard ON {table};\n" for table in (
    "payments_ledgerentry", "payments_openingbalance", "payments_eventfinancebudget",
    "payments_paymentdisputeevent", "payments_paymentdispute", "payments_paymentclaim",
    "payments_settlementconfirmation", "payments_paymentcaptureflag", "payments_paymentpaylink",
)) + "DROP FUNCTION IF EXISTS payments_l5_append_only();\n"


def _charge_guard(late):
    body = import_module("apps.payments.migrations.0015_payment_unclaimed_provider").FORWARD_SQL
    old = "    RAISE EXCEPTION 'terminal payment is immutable';"
    assert body.count(old) == 1
    return body.replace(old, LATE_CLAUSE) if late else body


def _document_guard(received):
    body = import_module("apps.payments.migrations.0022_bd_r1_bills_branding").GUARD_SQL
    old = "(NEW.kind <> 'receipt' OR NEW.amount <> charge.amount OR"
    assert body.count(old) == 1
    return body.replace(old, RECEIVED_CLAUSE) if received else body


def forward(apps, schema_editor):
    schema_editor.execute(_charge_guard(True), params=None)
    schema_editor.execute(_document_guard(True), params=None)
    schema_editor.execute(CHARGE_L5_SQL, params=None)
    schema_editor.execute(APPEND_ONLY_SQL, params=None)


def reverse(apps, schema_editor):
    schema_editor.execute(DROP_SQL, params=None)
    schema_editor.execute(_document_guard(False), params=None)
    schema_editor.execute(_charge_guard(False), params=None)


class Migration(migrations.Migration):
    dependencies = [("payments", "0031_l5_finance_ledger_tax")]

    operations = [migrations.RunPython(forward, reverse)]
