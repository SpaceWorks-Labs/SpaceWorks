"""Removing the optional `notifications` (inbox) module no longer rotates SMS/WhatsApp.

Owner decision D1/V12 (2026-10-18 reconciliation): addressed SMS and WhatsApp are
independent of the optional member inbox. The 0036 trigger bumped EVERY channel
configuration's generation (and revoked its endpoints) when `notifications` was
removed, which silently voided all SMS consent and WhatsApp endpoint proofs bound to
that generation. Removing a channel's OWN module still rotates and revokes it.
"""
from django.db import migrations

FORWARD = """
CREATE OR REPLACE FUNCTION notification_contract_module_removed() RETURNS trigger AS $$
BEGIN
  IF OLD.enabled_modules IS NOT DISTINCT FROM NEW.enabled_modules THEN RETURN NEW; END IF;
  UPDATE integrations_channelconfiguration config SET generation = generation + 1
    WHERE config.makerspace_id = NEW.id AND (
      (config.channel NOT IN ('sms', 'whatsapp')
        AND OLD.enabled_modules ? 'notifications' AND NOT (NEW.enabled_modules ? 'notifications')) OR
      (OLD.enabled_modules ? config.channel AND NOT (NEW.enabled_modules ? config.channel))
    );
  UPDATE integrations_notificationendpoint endpoint
    SET revoked_at = statement_timestamp(), verification_state = 'revoked'
    FROM integrations_channelconfiguration config
    WHERE endpoint.configuration_id = config.id AND config.makerspace_id = NEW.id
      AND endpoint.revoked_at IS NULL AND (
        (config.channel NOT IN ('sms', 'whatsapp')
          AND OLD.enabled_modules ? 'notifications' AND NOT (NEW.enabled_modules ? 'notifications')) OR
        (OLD.enabled_modules ? config.channel AND NOT (NEW.enabled_modules ? config.channel))
      );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

REVERSE = """
CREATE OR REPLACE FUNCTION notification_contract_module_removed() RETURNS trigger AS $$
BEGIN
  IF OLD.enabled_modules IS NOT DISTINCT FROM NEW.enabled_modules THEN RETURN NEW; END IF;
  UPDATE integrations_channelconfiguration config SET generation = generation + 1
    WHERE config.makerspace_id = NEW.id AND (
      (OLD.enabled_modules ? 'notifications' AND NOT (NEW.enabled_modules ? 'notifications')) OR
      (OLD.enabled_modules ? config.channel AND NOT (NEW.enabled_modules ? config.channel))
    );
  UPDATE integrations_notificationendpoint endpoint
    SET revoked_at = statement_timestamp(), verification_state = 'revoked'
    FROM integrations_channelconfiguration config
    WHERE endpoint.configuration_id = config.id AND config.makerspace_id = NEW.id
      AND endpoint.revoked_at IS NULL AND (
        (OLD.enabled_modules ? 'notifications' AND NOT (NEW.enabled_modules ? 'notifications')) OR
        (OLD.enabled_modules ? config.channel AND NOT (NEW.enabled_modules ? config.channel))
      );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


class Migration(migrations.Migration):

    dependencies = [("integrations", "0044_restore_receipt_received_at")]

    operations = [migrations.RunSQL(FORWARD, REVERSE)]
