"""Phase 2 bookings: decision reasons, typed departures + issues, place photo gallery."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


# Departure history is append-only like arrival history. The single permitted UPDATE is
# the scoped-PII maintenance rewrite of `remark` (encrypt/decrypt transition), which runs
# under an explicit write-fence operation and leaves every other column untouched.
DEPARTURE_SQL = """
CREATE FUNCTION bookings_reject_departure_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' AND current_setting('app.allow_immutable_delete', true) = 'on' THEN
        RETURN OLD;
    END IF;
    IF TG_OP = 'UPDATE'
       AND NEW.id = OLD.id AND NEW.makerspace_id = OLD.makerspace_id AND NEW.booking_id = OLD.booking_id
       AND NEW.actor_id = OLD.actor_id AND NEW.outcome = OLD.outcome AND NEW.source = OLD.source
       AND NEW.recorded_at = OLD.recorded_at
       AND (
         -- encrypt backfill: plaintext -> authenticated envelope (AAD binds it to this row)
         (OLD.remark NOT LIKE 'pii:gcm:v1:%' AND NEW.remark LIKE 'pii:gcm:v1:%')
         -- decrypt rollback runs under an explicit closed-fence operation
         OR COALESCE(current_setting('app.pii_fence_operation', true), '') <> ''
       ) THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'append-only/immutable booking departure: % not allowed', TG_OP;
END;
$$;
CREATE TRIGGER bookings_departure_immutable BEFORE UPDATE OR DELETE ON bookings_bookingdepartureevent
FOR EACH ROW EXECUTE FUNCTION bookings_reject_departure_mutation();

CREATE FUNCTION pii_fence_booking_departure() RETURNS trigger AS $$
BEGIN PERFORM pii_assert_mapped_write_allowed(NEW.makerspace_id); RETURN NEW; END; $$ LANGUAGE plpgsql;
CREATE TRIGGER pii_fence_booking_departure_trigger BEFORE INSERT OR UPDATE OF remark
ON bookings_bookingdepartureevent FOR EACH ROW EXECUTE FUNCTION pii_fence_booking_departure();

CREATE FUNCTION bookings_departure_tenant_guard() RETURNS trigger AS $$
DECLARE owner_space bigint;
BEGIN
    SELECT space.makerspace_id INTO owner_space FROM bookings_booking booking
      JOIN bookings_bookablespace space ON space.id = booking.space_id WHERE booking.id = NEW.booking_id;
    IF owner_space IS DISTINCT FROM NEW.makerspace_id THEN
        RAISE EXCEPTION 'booking departure tenant mismatch';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER bookings_departure_tenant BEFORE INSERT ON bookings_bookingdepartureevent
FOR EACH ROW EXECUTE FUNCTION bookings_departure_tenant_guard();
CREATE TRIGGER bookings_issue_tenant BEFORE INSERT OR UPDATE OF booking_id, makerspace_id ON bookings_bookingissue
FOR EACH ROW EXECUTE FUNCTION bookings_departure_tenant_guard();
"""

DEPARTURE_REVERSE = """
DROP TRIGGER bookings_issue_tenant ON bookings_bookingissue;
DROP TRIGGER bookings_departure_tenant ON bookings_bookingdepartureevent;
DROP FUNCTION bookings_departure_tenant_guard();
DROP TRIGGER pii_fence_booking_departure_trigger ON bookings_bookingdepartureevent;
DROP FUNCTION pii_fence_booking_departure();
DROP TRIGGER bookings_departure_immutable ON bookings_bookingdepartureevent;
DROP FUNCTION bookings_reject_departure_mutation();
"""

OUTCOMES = [("all_good", "All good"), ("issue", "Something was wrong"),
            ("damaged", "Something was damaged"), ("left_early", "Left early")]


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0019_alter_bookingspacestaffgrant_user"),
        ("makerspaces", "0094_public_profile_contract"),
        ("encryption", "0007_tenant_import_fence_operation"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(model_name="booking", name="decision_reason",
                            field=models.TextField(blank=True, default="")),
        migrations.AddField(model_name="booking", name="departed_at",
                            field=models.DateTimeField(blank=True, editable=False, null=True)),
        migrations.CreateModel(
            name="BookableSpacePhoto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("object_key", models.CharField(max_length=500, unique=True)),
                ("size_bytes", models.PositiveIntegerField()),
                ("caption", models.CharField(blank=True, default="", max_length=200)),
                ("position", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("space", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                            related_name="photos", to="bookings.bookablespace")),
                ("uploaded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                  related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("position", "id"), "indexes": [
                models.Index(fields=["space", "position"], name="bookspace_photo_order_idx")]},
        ),
        migrations.CreateModel(
            name="BookingDepartureEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("outcome", models.CharField(choices=OUTCOMES, max_length=16)),
                ("remark", models.TextField(blank=True, default="")),
                ("source", models.CharField(choices=[("staff", "Staff"), ("member", "Member")], max_length=8)),
                ("recorded_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                            related_name="+", to=settings.AUTH_USER_MODEL)),
                ("booking", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                              related_name="departure_events", to="bookings.booking")),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                                 related_name="+", to="makerspaces.makerspace")),
            ],
            options={"ordering": ["recorded_at", "pk"], "constraints": [
                models.CheckConstraint(condition=Q(outcome__in=["all_good", "issue", "damaged", "left_early"]),
                                       name="booking_departure_outcome"),
                models.CheckConstraint(condition=Q(source__in=["staff", "member"]),
                                       name="booking_departure_source"),
                models.CheckConstraint(condition=Q(outcome="all_good") | ~Q(remark=""),
                                       name="booking_departure_remark_required"),
            ]},
        ),
        migrations.CreateModel(
            name="BookingIssue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("outcome", models.CharField(choices=OUTCOMES, max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("resolution_note", models.CharField(blank=True, default="", max_length=500)),
                ("booking", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                              related_name="issues", to="bookings.booking")),
                ("departure", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,
                                                   related_name="issue", to="bookings.bookingdepartureevent")),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                                 related_name="booking_issues", to="makerspaces.makerspace")),
                ("resolved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                  related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "-pk"],
                     "indexes": [models.Index(fields=["makerspace", "resolved_at"], name="booking_issue_open_idx")],
                     "constraints": [models.CheckConstraint(condition=~Q(outcome="all_good"),
                                                            name="booking_issue_not_all_good")]},
        ),
        migrations.RunSQL(DEPARTURE_SQL, DEPARTURE_REVERSE),
    ]
