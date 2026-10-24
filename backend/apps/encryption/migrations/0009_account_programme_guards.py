"""Raw-SQL backstops for immutable account ownership and always-encrypted values."""
from django.db import migrations

SQL = r"""
CREATE FUNCTION pii_assert_account_write_allowed(owner_id bigint) RETURNS void LANGUAGE plpgsql AS $$
DECLARE fence_state text;
BEGIN
  PERFORM pii_assert_mapped_write_allowed(NULL);
  PERFORM pg_advisory_xact_lock_shared(734203, owner_id::integer);
  SELECT state INTO fence_state FROM encryption_piiaccountwritefence WHERE user_id=owner_id;
  IF fence_state IS NOT NULL AND fence_state<>'open' THEN RAISE EXCEPTION 'account write fence closed'; END IF;
END; $$;

CREATE FUNCTION account_programme_owner_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='UPDATE' AND NEW.user_id IS DISTINCT FROM OLD.user_id THEN RAISE EXCEPTION 'account owner is immutable'; END IF;
  IF NOT EXISTS (SELECT 1 FROM accounts_user WHERE id=NEW.user_id AND account_kind='member')
    THEN RAISE EXCEPTION 'saved details require member identity'; END IF;
  PERFORM pii_assert_account_write_allowed(NEW.user_id);
  RETURN NEW;
END; $$;

CREATE FUNCTION account_programme_envelope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE payload text; version_no integer; expected_epoch bigint;
BEGIN
  IF TG_TABLE_NAME='accounts_membersaveddetail' THEN
    IF TG_OP='UPDATE' AND NEW.field_key IS DISTINCT FROM OLD.field_key THEN RAISE EXCEPTION 'saved field binding is immutable'; END IF;
    payload:=NEW.value_envelope;
    IF payload='' AND NEW.deleted_at IS NOT NULL THEN RETURN NEW; END IF;
  ELSE
    IF TG_OP='UPDATE' AND (NEW.operation_uuid,NEW.event_id,NEW.subject_kind,NEW.subject_id,NEW.base_versions,NEW.chosen_fields,NEW.key_version,NEW.key_epoch)
      IS DISTINCT FROM (OLD.operation_uuid,OLD.event_id,OLD.subject_kind,OLD.subject_id,OLD.base_versions,OLD.chosen_fields,OLD.key_version,OLD.key_epoch)
      THEN RAISE EXCEPTION 'saved intent binding is immutable'; END IF;
    payload:=NEW.encrypted_payload;
    IF payload='' AND NEW.state IN ('applied','conflict','failed') THEN RETURN NEW; END IF;
    SELECT epoch INTO expected_epoch FROM encryption_piiaccountwritefence WHERE user_id=NEW.user_id AND state='open';
    IF expected_epoch IS DISTINCT FROM NEW.key_epoch THEN RAISE EXCEPTION 'saved intent account epoch changed'; END IF;
  END IF;
  IF payload !~ '^pii:account:gcm:v1:[1-9][0-9]*:[A-Za-z0-9_-]+:[A-Za-z0-9_-]+$'
    THEN RAISE EXCEPTION 'account values require encrypted envelopes'; END IF;
  version_no:=split_part(payload,':',5)::integer;
  IF NOT EXISTS (SELECT 1 FROM encryption_accountpiikey WHERE user_id=NEW.user_id AND version=version_no AND status IN ('active','rotated'))
    THEN RAISE EXCEPTION 'account encryption key unavailable'; END IF;
  IF TG_TABLE_NAME='accounts_saveddetailupdateintent' THEN
    IF version_no<>NEW.key_version THEN RAISE EXCEPTION 'intent key mismatch'; END IF;
  END IF;
  RETURN NEW;
END; $$;

CREATE FUNCTION account_programme_fence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='UPDATE' AND (NEW.user_id IS DISTINCT FROM OLD.user_id OR NEW.epoch<OLD.epoch
    OR (OLD.state='erased' AND NEW.state<>'erased')) THEN RAISE EXCEPTION 'account fence cannot revive'; END IF;
  IF NOT EXISTS (SELECT 1 FROM accounts_user WHERE id=NEW.user_id AND account_kind='member')
    THEN RAISE EXCEPTION 'account fence requires member identity'; END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER account_fence_identity BEFORE INSERT OR UPDATE ON encryption_piiaccountwritefence
  FOR EACH ROW EXECUTE FUNCTION account_programme_fence_guard();
CREATE TRIGGER saved_detail_envelope BEFORE INSERT OR UPDATE ON accounts_membersaveddetail
  FOR EACH ROW EXECUTE FUNCTION account_programme_envelope_guard();
CREATE TRIGGER saved_intent_envelope BEFORE INSERT OR UPDATE ON accounts_saveddetailupdateintent
  FOR EACH ROW EXECUTE FUNCTION account_programme_envelope_guard();
"""

OWNED_TABLES = (
    "encryption_accountpiikey",
    "accounts_membersaveddetail", "accounts_membersavedasset", "accounts_saveddetailupdateintent",
    "accounts_saveddetailcommandreceipt", "accounts_accountsaveddetailsexportjob",
)
FORWARD = SQL + "\n".join(
    f"CREATE TRIGGER {table}_owner BEFORE INSERT OR UPDATE ON {table} "
    "FOR EACH ROW EXECUTE FUNCTION account_programme_owner_guard();" for table in OWNED_TABLES
)
REVERSE = "\n".join(f"DROP TRIGGER {table}_owner ON {table};" for table in OWNED_TABLES) + """
DROP TRIGGER saved_detail_envelope ON accounts_membersaveddetail;
DROP TRIGGER saved_intent_envelope ON accounts_saveddetailupdateintent;
DROP TRIGGER account_fence_identity ON encryption_piiaccountwritefence;
DROP FUNCTION account_programme_fence_guard();
DROP FUNCTION account_programme_envelope_guard();
DROP FUNCTION account_programme_owner_guard();
DROP FUNCTION pii_assert_account_write_allowed(bigint);
"""


class Migration(migrations.Migration):
    dependencies = [("encryption", "0008_events_programme_schema"), ("accounts", "0043_events_programme_schema")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
