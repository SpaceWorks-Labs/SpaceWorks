from django.db import migrations


FORWARD = """
CREATE FUNCTION pii_fence_notification_contract() RETURNS trigger AS $$
BEGIN
  PERFORM pii_assert_mapped_write_allowed(NEW.makerspace_id);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER pii_fence_notification_envelope
BEFORE INSERT OR UPDATE OF message_body ON integrations_notificationenvelope
FOR EACH ROW EXECUTE FUNCTION pii_fence_notification_contract();
CREATE TRIGGER pii_fence_notification_endpoint
BEFORE INSERT OR UPDATE OF destination, provider_subject ON integrations_notificationendpoint
FOR EACH ROW EXECUTE FUNCTION pii_fence_notification_contract();
CREATE TRIGGER pii_fence_notification_challenge
BEFORE INSERT OR UPDATE OF candidate_destination ON integrations_notificationendpointchallenge
FOR EACH ROW EXECUTE FUNCTION pii_fence_notification_contract();

CREATE FUNCTION notification_contract_tenant_guard() RETURNS trigger AS $$
DECLARE config_space bigint; envelope_space bigint; endpoint_space bigint;
        owner_id bigint; endpoint_user bigint; endpoint_channel text;
BEGIN
  IF TG_TABLE_NAME IN ('integrations_notificationendpoint', 'integrations_notificationendpointchallenge') THEN
    SELECT makerspace_id INTO config_space FROM integrations_channelconfiguration WHERE id = NEW.configuration_id;
    IF config_space IS DISTINCT FROM NEW.makerspace_id THEN
      RAISE EXCEPTION 'notification integration tenant mismatch';
    END IF;
  ELSIF TG_TABLE_NAME = 'integrations_notificationdelivery' THEN
    SELECT makerspace_id, recipient_id INTO envelope_space, owner_id
    FROM integrations_notificationenvelope WHERE id = NEW.envelope_id;
    IF envelope_space IS DISTINCT FROM NEW.makerspace_id THEN
      RAISE EXCEPTION 'notification envelope tenant mismatch';
    END IF;
    IF NEW.endpoint_id IS NOT NULL THEN
      SELECT makerspace_id, user_id, channel INTO endpoint_space, endpoint_user, endpoint_channel
      FROM integrations_notificationendpoint WHERE id = NEW.endpoint_id;
      IF endpoint_space IS DISTINCT FROM NEW.makerspace_id OR endpoint_user IS DISTINCT FROM owner_id
         OR endpoint_channel IS DISTINCT FROM NEW.channel THEN
        RAISE EXCEPTION 'notification endpoint tenant mismatch';
      END IF;
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER notification_endpoint_tenant BEFORE INSERT OR UPDATE ON integrations_notificationendpoint
FOR EACH ROW EXECUTE FUNCTION notification_contract_tenant_guard();
CREATE TRIGGER notification_challenge_tenant BEFORE INSERT OR UPDATE ON integrations_notificationendpointchallenge
FOR EACH ROW EXECUTE FUNCTION notification_contract_tenant_guard();
CREATE TRIGGER notification_delivery_tenant BEFORE INSERT OR UPDATE ON integrations_notificationdelivery
FOR EACH ROW EXECUTE FUNCTION notification_contract_tenant_guard();

CREATE FUNCTION notification_contract_module_removed() RETURNS trigger AS $$
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
CREATE TRIGGER notification_contract_module_removed
AFTER UPDATE OF enabled_modules ON makerspaces_makerspace
FOR EACH ROW EXECUTE FUNCTION notification_contract_module_removed();
"""
REVERSE = """
DROP TRIGGER notification_contract_module_removed ON makerspaces_makerspace;
DROP FUNCTION notification_contract_module_removed();
DROP TRIGGER notification_delivery_tenant ON integrations_notificationdelivery;
DROP TRIGGER notification_challenge_tenant ON integrations_notificationendpointchallenge;
DROP TRIGGER notification_endpoint_tenant ON integrations_notificationendpoint;
DROP FUNCTION notification_contract_tenant_guard();
DROP TRIGGER pii_fence_notification_challenge ON integrations_notificationendpointchallenge;
DROP TRIGGER pii_fence_notification_endpoint ON integrations_notificationendpoint;
DROP TRIGGER pii_fence_notification_envelope ON integrations_notificationenvelope;
DROP FUNCTION pii_fence_notification_contract();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0035_whatsapp_channel"),
        ("encryption", "0007_tenant_import_fence_operation"),
    ]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
