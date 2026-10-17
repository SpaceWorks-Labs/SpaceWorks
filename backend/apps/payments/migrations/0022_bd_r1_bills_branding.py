"""Bills share immutable document custody, with independent numbering."""

from importlib import import_module

from django.db import migrations, models


# The fill-only backup merge role has column-limited SELECT grants. The trigger
# needs owner reads for structural validation, never owner writes. Its search path
# explicitly places temporary schemas last; every mutation still passes the guard.
GUARD_SQL = r"""
CREATE OR REPLACE FUNCTION payments_document_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
  charge payments_payment%ROWTYPE;
  reconstruct boolean;
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF current_setting('app.allow_immutable_delete', true) = 'on' THEN RETURN OLD; END IF;
    RAISE EXCEPTION 'payment documents are append-only';
  END IF;
  IF TG_OP = 'UPDATE' THEN RAISE EXCEPTION 'payment documents are append-only'; END IF;
  reconstruct := COALESCE(NULLIF(current_setting('app.payment_document_import_ids', true), ''), '[]')::jsonb
                 @> jsonb_build_array(NEW.id);
  IF NEW.kind NOT IN ('receipt', 'credit_note', 'bill') OR
     num_nonnulls(NEW.settlement_id, NEW.refund_id, NEW.reverses_id) > 1 THEN
    RAISE EXCEPTION 'document must have only one financial source and a valid kind';
  END IF;
  IF jsonb_typeof(NEW.issuer) IS DISTINCT FROM 'object' OR
     jsonb_typeof(NEW.issuer->'name') IS DISTINCT FROM 'string' OR
     length(btrim(NEW.issuer->>'name')) = 0 THEN
    RAISE EXCEPTION 'invalid document issuer snapshot';
  END IF;
  IF (NEW.branding_logo_key = '') <> (NEW.branding_logo_sha256 = '') OR
     (NEW.branding_logo_sha256 <> '' AND NEW.branding_logo_sha256 !~ '^[0-9a-f]{64}$') THEN
    RAISE EXCEPTION 'invalid document logo identity';
  END IF;
  SELECT * INTO charge FROM payments_payment WHERE id = NEW.payment_id;
  IF NOT FOUND OR charge.makerspace_id <> NEW.makerspace_id OR charge.currency <> NEW.currency THEN
    RAISE EXCEPTION 'document must match its payment tenant and currency';
  END IF;
  IF NEW.kind = 'bill' THEN
    IF num_nonnulls(NEW.settlement_id, NEW.refund_id, NEW.reverses_id) <> 0 OR
       NEW.amount <> charge.amount OR (NOT reconstruct AND charge.status <> 'pending') THEN
      RAISE EXCEPTION 'bill must match a pending charge without a financial source';
    END IF;
  ELSE
    IF NOT reconstruct AND charge.status NOT IN ('paid_offline', 'paid_online') THEN
      RAISE EXCEPTION 'document must match a collected payment';
    END IF;
    IF NEW.settlement_id IS NOT NULL AND NOT EXISTS(
      SELECT 1 FROM payments_manualsettlement WHERE id = NEW.settlement_id AND payment_id = NEW.payment_id
        AND amount = NEW.amount AND currency = NEW.currency AND NEW.kind = 'receipt'
    ) THEN RAISE EXCEPTION 'document settlement belongs to another payment'; END IF;
    IF NEW.refund_id IS NOT NULL AND NOT EXISTS(
      SELECT 1 FROM payments_refund WHERE id = NEW.refund_id AND payment_id = NEW.payment_id
        AND (reconstruct OR status = 'succeeded')
        AND amount = NEW.amount AND currency = NEW.currency AND NEW.kind = 'credit_note'
    ) THEN RAISE EXCEPTION 'document refund is not succeeded on this payment'; END IF;
    IF NEW.reverses_id IS NOT NULL AND NOT EXISTS(
      SELECT 1 FROM payments_paymentdocument WHERE id = NEW.reverses_id AND payment_id = NEW.payment_id
        AND makerspace_id = NEW.makerspace_id AND currency = NEW.currency
        AND kind IN ('receipt', 'credit_note') AND kind <> NEW.kind AND amount = NEW.amount
    ) THEN RAISE EXCEPTION 'document reversal must offset the same payment'; END IF;
    IF NEW.refund_id IS NULL AND NEW.reverses_id IS NULL AND
       (NEW.kind <> 'receipt' OR NEW.amount <> charge.amount OR
         (NOT reconstruct AND charge.status = 'paid_offline' AND NEW.settlement_id IS NULL)) THEN
      RAISE EXCEPTION 'receipt must match the full settlement';
    END IF;
  END IF;
  IF jsonb_typeof(NEW.lines) IS DISTINCT FROM 'array' THEN
    RAISE EXCEPTION 'document lines must reconcile';
  END IF;
  IF jsonb_array_length(NEW.lines) NOT BETWEEN 1 AND 200 OR
     EXISTS(SELECT 1 FROM jsonb_array_elements(NEW.lines) line WHERE
       jsonb_typeof(line->'label') IS DISTINCT FROM 'string' OR length(btrim(line->>'label')) = 0 OR
       line->>'quantity' IS NULL OR line->>'unit_amount' IS NULL OR line->>'total' IS NULL OR
       (line->>'quantity')::numeric <= 0 OR (line->>'unit_amount')::numeric < 0 OR
       (line->>'quantity')::numeric IN ('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric) OR
       (line->>'unit_amount')::numeric IN ('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric) OR
       (line->>'total')::numeric IN ('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric) OR
       (line->>'quantity')::numeric * (line->>'unit_amount')::numeric <> (line->>'total')::numeric) OR
     (SELECT SUM((line->>'total')::numeric) FROM jsonb_array_elements(NEW.lines) line) <> NEW.amount THEN
    RAISE EXCEPTION 'document lines must reconcile';
  END IF;
  RETURN NEW;
END; $$;
"""


def restore_guard(apps, schema_editor):
    old = import_module("apps.payments.migrations.0021_payment_documents").GUARD_SQL
    schema_editor.execute(old.split("CREATE TRIGGER")[0].replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION"))


def avoid_legacy_prefix_collision(apps, schema_editor):
    Billing = apps.get_model("payments", "MakerspaceBillingSettings")
    Billing.objects.using(schema_editor.connection.alias).filter(number_prefix="BILL-").update(bill_prefix="BILL-BD-")


class Migration(migrations.Migration):
    dependencies = [("payments", "0021_payment_documents")]
    operations = [
        migrations.AddField("makerspacebillingsettings", "bill_prefix", models.CharField(max_length=32, default="BILL-")),
        migrations.AddField("makerspacebillingsettings", "payment_instructions", models.TextField(max_length=2000, blank=True, default="")),
        migrations.AddField("makerspacebillingsettings", "next_bill_number", models.PositiveBigIntegerField(default=1)),
        migrations.AddField("paymentdocument", "branding_logo_key", models.CharField(max_length=300, blank=True, default="")),
        migrations.AddField("paymentdocument", "branding_logo_sha256", models.CharField(max_length=64, blank=True, default="")),
        migrations.RunPython(avoid_legacy_prefix_collision, migrations.RunPython.noop),
        migrations.AlterField("paymentdocument", "kind", models.CharField(max_length=16, choices=[
            ("receipt", "Receipt"), ("credit_note", "Credit note"), ("bill", "Bill")])),
        migrations.AlterField("paymentdocument", "settlement_method", models.CharField(max_length=16, blank=True)),
        migrations.RemoveConstraint("paymentdocument", "document_space_sequence"),
        migrations.AddConstraint("paymentdocument", models.UniqueConstraint(fields=["makerspace", "sequence"],
            condition=models.Q(kind__in=["receipt", "credit_note"]), name="document_money_sequence")),
        migrations.AddConstraint("paymentdocument", models.UniqueConstraint(fields=["makerspace", "sequence"],
            condition=models.Q(kind="bill"), name="document_bill_sequence")),
        migrations.AddConstraint("paymentdocument", models.UniqueConstraint(fields=["payment"],
            condition=models.Q(kind="bill"), name="document_bill_once")),
        migrations.AddConstraint("makerspacebillingsettings", models.CheckConstraint(
            condition=models.Q(next_bill_number__gt=0), name="billing_bill_counter_positive")),
        migrations.RunPython(migrations.RunPython.noop, restore_guard),
        migrations.RunSQL(GUARD_SQL, migrations.RunSQL.noop),
    ]
