"""Unified accounts M+1: a membership belongs to the community or the staff TRACK.

Existing memberships of staff accounts become staff rows; every other row is community.
The unique key becomes (makerspace, user, track) so one person can hold both. Deferred
constraint triggers pin each membership FK to the track it may reference, and the track
itself is immutable once written.
"""

from django.db import migrations, models

# (table, membership column, required track). Machine scopes and additional roles hang
# off staff rows; everything community-owned (claims, OIDC walk-in binding, calendar
# feeds, event presentations, certifications, import adoption, terms, cards, profiles,
# presence) hangs off community rows.
TRACK_FKS = (
    ("machines_membershipmachinetypescope", "membership_id", "staff"),
    ("makerspaces_membershipadditionalrole", "membership_id", "staff"),
    ("accounts_memberclaimcode", "membership_id", "community"),
    ("accounts_oidcbrowserattempt", "intended_membership_id", "community"),
    ("events_membercalendarfeed", "membership_id", "community"),
    ("events_eventmemberpresentation", "selected_membership_id", "community"),
    ("machines_certificationgrant", "membership_id", "community"),
    ("makerspaces_pendingimportedmembership", "adopted_membership_id", "community"),
    ("makerspaces_membershipterm", "membership_id", "community"),
    ("makerspaces_membercard", "membership_id", "community"),
    ("makerspaces_memberprofile", "membership_id", "community"),
    ("presence_presencesession", "membership_id", "community"),
)

BACKFILL = """
UPDATE makerspaces_makerspacemembership m SET track = 'staff'
FROM accounts_user u WHERE u.id = m.user_id AND u.account_kind = 'staff';
SET CONSTRAINTS ALL IMMEDIATE;
"""

FUNCTION = r"""
CREATE FUNCTION makerspaces_membership_track_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    referenced bigint;
    actual text;
BEGIN
    IF TG_TABLE_NAME = 'makerspaces_makerspacemembership' THEN
        IF NEW.track IS DISTINCT FROM OLD.track THEN
            RAISE EXCEPTION 'Membership track is immutable' USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END IF;
    referenced := (to_jsonb(NEW) ->> TG_ARGV[0])::bigint;
    IF referenced IS NULL THEN RETURN NULL; END IF;
    SELECT track INTO actual FROM makerspaces_makerspacemembership WHERE id = referenced;
    IF actual IS NOT NULL AND actual <> TG_ARGV[1] THEN
        RAISE EXCEPTION '%.% must reference a % membership', TG_TABLE_NAME, TG_ARGV[0], TG_ARGV[1]
            USING ERRCODE = '23514';
    END IF;
    RETURN NULL;
END $$;
CREATE TRIGGER makerspaces_membership_track_immutable
    BEFORE UPDATE OF track ON makerspaces_makerspacemembership
    FOR EACH ROW EXECUTE FUNCTION makerspaces_membership_track_guard();
""" + "\n".join(
    f"CREATE CONSTRAINT TRIGGER {table}_membership_track AFTER INSERT OR UPDATE OF {column} "
    f"ON {table} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
    f"EXECUTE FUNCTION makerspaces_membership_track_guard('{column}', '{track}');"
    for table, column, track in TRACK_FKS
)

REVERSE = "\n".join(
    f"DROP TRIGGER {table}_membership_track ON {table};" for table, _column, _track in TRACK_FKS
) + """
DROP TRIGGER makerspaces_membership_track_immutable ON makerspaces_makerspacemembership;
DROP FUNCTION makerspaces_membership_track_guard();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("makerspaces", "0113_remove_superadmin_access_enabled"),
        ("accounts", "0048_remove_b1_guard_branch"),
        ("events", "0062_l2_communications"),
        ("machines", "0030_service_notice_markers"),
        ("presence", "0003_presence_programme"),
    ]

    operations = [
        migrations.AddField(
            model_name="makerspacemembership",
            name="track",
            field=models.CharField(
                choices=[("community", "Community"), ("staff", "Staff")],
                default="community", max_length=16,
            ),
        ),
        migrations.RemoveConstraint(model_name="makerspacemembership", name="uniq_makerspace_user"),
        migrations.AddConstraint(
            model_name="makerspacemembership",
            constraint=models.UniqueConstraint(
                fields=("makerspace", "user", "track"), name="uniq_makerspace_user_track",
            ),
        ),
        migrations.RunSQL(BACKFILL, migrations.RunSQL.noop),
        migrations.RunSQL(FUNCTION, REVERSE),
    ]
