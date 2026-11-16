"""Lane L15 database guards, and the pricing switches for spaces that already exist.

* `Payment.pricing_snapshot` is insert-only: the frozen quote a charge was raised from
  can never be rewritten (the model refuses too).
* `LoanFeeWaiver` rows are append-only: no UPDATE, no DELETE. A waiver is undone by a
  new revocation row, never by editing it.
* `PriceDiscount` rows are archived, never deleted.

`app.allow_immutable_delete` (and `session_replication_role = replica`) keep the
whole-tenant purge working, exactly as for the L5 ledger rows.

`enabled_features` is stored per makerspace, so the two default-ON switches
(`charges.pricing`, `loans.fee_waivers`) reach new spaces only; this backfills them onto
existing ones. Both change nothing on their own: with no rate card saved every new
component is free, and no waiver exists until staff write one. `charges.discounts`
stays off. Same shape as makerspaces `0072`: touches only rows lacking the keys, with a
working reverse.
"""

from django.db import migrations

GUARD_SQL = """
CREATE OR REPLACE FUNCTION payments_payment_l15_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.pricing_snapshot IS DISTINCT FROM OLD.pricing_snapshot THEN
    RAISE EXCEPTION 'a charge pricing snapshot is immutable';
  END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER payments_payment_l15_guard BEFORE UPDATE ON payments_payment
FOR EACH ROW EXECUTE FUNCTION payments_payment_l15_guard();

CREATE OR REPLACE FUNCTION payments_l15_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF current_setting('app.allow_immutable_delete', true) = 'on' THEN RETURN COALESCE(NEW, OLD); END IF;
  IF TG_TABLE_NAME = 'payments_pricediscount' AND TG_OP = 'UPDATE' THEN RETURN NEW; END IF;
  -- A discount's plan purged with the membership module is cleared by SET NULL.
  RAISE EXCEPTION '% rows are append-only', TG_TABLE_NAME;
END; $$;
CREATE TRIGGER payments_loanfeewaiver_l15_guard BEFORE UPDATE OR DELETE ON payments_loanfeewaiver
FOR EACH ROW EXECUTE FUNCTION payments_l15_append_only();
CREATE TRIGGER payments_pricediscount_l15_guard BEFORE UPDATE OR DELETE ON payments_pricediscount
FOR EACH ROW EXECUTE FUNCTION payments_l15_append_only();
"""

DROP_SQL = """
DROP TRIGGER IF EXISTS payments_pricediscount_l15_guard ON payments_pricediscount;
DROP TRIGGER IF EXISTS payments_loanfeewaiver_l15_guard ON payments_loanfeewaiver;
DROP FUNCTION IF EXISTS payments_l15_append_only();
DROP TRIGGER IF EXISTS payments_payment_l15_guard ON payments_payment;
DROP FUNCTION IF EXISTS payments_payment_l15_guard();
"""

FEATURE_KEYS = ("charges.pricing", "loans.fee_waivers")


def enable_switches(apps, schema_editor):
    Makerspace = apps.get_model("makerspaces", "Makerspace")
    for makerspace in Makerspace.objects.all().iterator():
        features = set(makerspace.enabled_features or [])
        if features.issuperset(FEATURE_KEYS):
            continue
        makerspace.enabled_features = sorted(features | set(FEATURE_KEYS))
        makerspace.save(update_fields=["enabled_features"])


def disable_switches(apps, schema_editor):
    Makerspace = apps.get_model("makerspaces", "Makerspace")
    for makerspace in Makerspace.objects.all().iterator():
        features = set(makerspace.enabled_features or [])
        if features.isdisjoint(FEATURE_KEYS + ("charges.discounts",)):
            continue
        makerspace.enabled_features = sorted(features - set(FEATURE_KEYS) - {"charges.discounts"})
        makerspace.save(update_fields=["enabled_features"])


class Migration(migrations.Migration):
    dependencies = [("payments", "0033_l15_pricing")]

    operations = [
        migrations.RunSQL(GUARD_SQL, DROP_SQL),
        migrations.RunPython(enable_switches, disable_switches),
    ]
