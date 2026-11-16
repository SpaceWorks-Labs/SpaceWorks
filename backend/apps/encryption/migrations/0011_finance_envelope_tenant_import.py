"""Mandatory finance envelopes may be loaded by a Lane D build before their keys exist.

A Lane D image carries tenant DEKs only in the sealed key envelope and installs them
at target activation, so its raw insertion runs without key rows. The envelope shape
is still required in every case; only the key-row lookup is waived, and only while
this tenant's write fence is closed for the exact ``tenant_import`` operation of the
session. The reverse restores the original guard.
"""
from django.db import migrations

_BODY = r"""
CREATE OR REPLACE FUNCTION finance_mandatory_envelope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE tenant_id bigint; payload text; field_name text; version_no integer;
BEGIN
  SELECT makerspace_id INTO tenant_id FROM payments_eventpayoutobligation WHERE id=NEW.obligation_id;
  IF tenant_id IS NULL THEN RAISE EXCEPTION 'mandatory finance host missing'; END IF;
  PERFORM pii_assert_mapped_write_allowed(tenant_id);
  FOREACH field_name IN ARRAY TG_ARGV LOOP
    payload := to_jsonb(NEW)->>field_name;
    IF field_name='cancellation_note' AND payload='' THEN CONTINUE; END IF;
    IF TG_TABLE_NAME='payments_eventpayeerevision' AND to_jsonb(NEW)->>'state'='purged' AND payload='' THEN CONTINUE; END IF;
    IF payload IS NULL OR payload !~ '^pii:gcm:v1:[1-9][0-9]*:[A-Za-z0-9_-]+:[A-Za-z0-9_-]+$'
      THEN RAISE EXCEPTION 'mandatory finance envelope required'; END IF;
    version_no:=split_part(payload,':',4)::integer;
    IF NOT EXISTS (SELECT 1 FROM encryption_makerspaceencryptionkey
      WHERE makerspace_id=tenant_id AND version=version_no AND status IN ('active','rotated'))%(exemption)s
      THEN RAISE EXCEPTION 'mandatory finance key unavailable'; END IF;
  END LOOP;
  RETURN NEW;
END; $$;
"""
_IMPORT = r"""
      AND NOT EXISTS (SELECT 1 FROM encryption_piimakerspacewritefence f
        WHERE f.makerspace_id=tenant_id AND f.state='closed' AND f.operation_kind='tenant_import'
          AND f.operation_id::text=COALESCE(current_setting('app.pii_fence_operation', true), ''))"""


class Migration(migrations.Migration):
    dependencies = [("encryption", "0010_mandatory_finance_envelopes")]
    operations = [migrations.RunSQL(_BODY % {"exemption": _IMPORT}, _BODY % {"exemption": ""})]
