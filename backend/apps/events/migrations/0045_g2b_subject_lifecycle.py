"""Atomic presentation source deletion and a non-removable erased-account fence."""
from django.db import migrations

FORWARD = r"""
CREATE FUNCTION events_clear_deleted_presentation_source() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF to_regclass('events_eventmemberpresentation') IS NULL THEN RETURN OLD; END IF;
  UPDATE events_eventmemberpresentation SET
    selected_profile_id=NULL, selected_membership_id=NULL, source_revision='',
    print_photo_consent=false, public_card_consent=false, public_card_scopes='[]'::jsonb,
    consented_at=NULL, revoked_at=clock_timestamp(),
    version=version+1, consent_revision=consent_revision+1
  WHERE (TG_TABLE_NAME='makerspaces_memberprofile' AND selected_profile_id=OLD.id)
     OR (TG_TABLE_NAME='makerspaces_makerspacemembership' AND selected_membership_id=OLD.id);
  RETURN OLD;
END; $$;
CREATE TRIGGER events_profile_selection_delete BEFORE DELETE ON makerspaces_memberprofile
  FOR EACH ROW EXECUTE FUNCTION events_clear_deleted_presentation_source();
CREATE TRIGGER events_membership_selection_delete BEFORE DELETE ON makerspaces_makerspacemembership
  FOR EACH ROW EXECUTE FUNCTION events_clear_deleted_presentation_source();

CREATE FUNCTION events_retain_erased_account_fence() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.state='erased' AND EXISTS (SELECT 1 FROM accounts_user WHERE id=OLD.user_id) THEN
    -- Django's collector deletes CASCADE children before their User. Retain this
    -- fence until the User DELETE itself, rather than permitting a revival gap.
    RETURN NULL;
  END IF;
  RETURN OLD;
END; $$;
CREATE TRIGGER events_retain_erased_fence BEFORE DELETE ON encryption_piiaccountwritefence
  FOR EACH ROW EXECUTE FUNCTION events_retain_erased_account_fence();
CREATE FUNCTION events_remove_deleted_user_fence() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  DELETE FROM encryption_piiaccountwritefence WHERE user_id=OLD.id;
  RETURN OLD;
END; $$;
CREATE TRIGGER events_deleted_user_fence AFTER DELETE ON accounts_user
  FOR EACH ROW EXECUTE FUNCTION events_remove_deleted_user_fence();
"""

REVERSE = r"""
DROP TRIGGER events_deleted_user_fence ON accounts_user;
DROP FUNCTION events_remove_deleted_user_fence();
DROP TRIGGER events_retain_erased_fence ON encryption_piiaccountwritefence;
DROP FUNCTION events_retain_erased_account_fence();
DROP TRIGGER events_membership_selection_delete ON makerspaces_makerspacemembership;
DROP TRIGGER events_profile_selection_delete ON makerspaces_memberprofile;
DROP FUNCTION events_clear_deleted_presentation_source();
"""


class Migration(migrations.Migration):
    dependencies = [("events", "0044_events_programme_guards"),
                    ("encryption", "0009_account_programme_guards")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
