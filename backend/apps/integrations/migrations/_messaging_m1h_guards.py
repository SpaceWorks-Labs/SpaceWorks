"""Frozen SQL for the messaging consent history and mapped phone write fence."""


def seed_otp_sender(apps, schema_editor):
    row = apps.get_model("integrations", "PlatformSmsSettings").objects.filter(pk=1).first()
    if row and row.account_sid and row.from_number:
        identity = apps.get_model("integrations", "MessagingSenderIdentity").objects.create(
            sender_key=f"twilio:{row.account_sid}:{row.from_number}", channel="sms", owner="platform_otp",
        )
        # Both columns use the same deployment encryption; never decrypt in a migration.
        apps.get_model("integrations", "MessagingSenderCredential").objects.create(
            identity=identity, version=1, webhook_secret=row.auth_token,
        )


FORWARD = """
CREATE FUNCTION messaging_consent_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF current_setting('app.allow_immutable_delete', true) = 'on' THEN RETURN OLD; END IF;
  ELSIF (to_jsonb(NEW) - 'phone_e164') = (to_jsonb(OLD) - 'phone_e164') AND EXISTS (
    SELECT 1 FROM encryption_piiglobalwritefence
      WHERE state = 'closed'
        AND operation_id::text = current_setting('app.pii_fence_operation', true)
        AND operation_kind IN ('enable_transition', 'decrypt_rollback')
    UNION ALL
    SELECT 1 FROM encryption_piimakerspacewritefence
      WHERE makerspace_id = OLD.makerspace_id AND state = 'closed'
        AND operation_id::text = current_setting('app.pii_fence_operation', true)
        AND operation_kind IN ('enable_transition', 'decrypt_rollback')
  ) THEN
    PERFORM pii_assert_mapped_write_allowed(NEW.makerspace_id);
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'Messaging consent is append-only';
END; $$;
CREATE TRIGGER messaging_consent_immutable BEFORE UPDATE OR DELETE
  ON integrations_messagingconsent FOR EACH ROW EXECUTE FUNCTION messaging_consent_immutable();
CREATE FUNCTION messaging_consent_phone_fence() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  PERFORM pii_assert_mapped_write_allowed(NEW.makerspace_id); RETURN NEW;
END; $$;
CREATE TRIGGER messaging_consent_phone_fence BEFORE INSERT OR UPDATE OF phone_e164
  ON integrations_messagingconsent FOR EACH ROW EXECUTE FUNCTION messaging_consent_phone_fence();
"""
REVERSE = """
DROP TRIGGER IF EXISTS messaging_consent_phone_fence ON integrations_messagingconsent;
DROP FUNCTION IF EXISTS messaging_consent_phone_fence();
DROP TRIGGER IF EXISTS messaging_consent_immutable ON integrations_messagingconsent;
DROP FUNCTION IF EXISTS messaging_consent_immutable();
"""
