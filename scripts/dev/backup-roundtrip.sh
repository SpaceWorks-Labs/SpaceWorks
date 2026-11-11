#!/usr/bin/env bash
# Live backup -> wipe -> restore round trip on the running dev stack (decision 245(a)).
#
#   ./scripts/dev/backup-roundtrip.sh            run everything, leave the scratch data for inspection
#   ./scripts/dev/backup-roundtrip.sh --clean    drop the scratch database and the test space afterwards
#
# It proves two layers with real sample data (a guest pass and day-pass product, a minor with an encrypted
# guardian consent, an incident, a volunteer credit):
#   A. In-app: one-space archive (age-encrypted, the real archive builder) -> simulated disaster (rows deleted
#      or edited, immutable rows removed under the restore scope) -> preview -> confirm -> apply, then the
#      row counts match, the encrypted fields read back, and the immutability triggers are intact.
#   B. Physical: pg_dump of the whole dev database -> fresh empty database -> pg_restore -> the same counts,
#      the encrypted fields decrypt with the same keys, every immutability trigger is present, and the
#      managed function catalog is complete (no application function missing from the catalogue).
# Needs: Docker, `./scripts/dev.sh up` already running, `age` and `age-keygen` in the backend image.
set -euo pipefail
export MSYS_NO_PATHCONV=1
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
DEV=./scripts/dev.sh
CLEAN=0; [[ "${1:-}" == --clean ]] && CLEAN=1
SCRATCH_DB=rt_restore
OWNER_URL="postgres://makerspace:makerspace@db:5432/$SCRATCH_DB"
step() { printf '\n==> %s\n' "$*"; }
fail() { printf 'ROUNDTRIP FAILED: %s\n' "$*" >&2; exit 1; }
backend() { $DEV exec -T "$@"; }

step "Preflight"
$DEV ps --status running --services | grep -qx backend || fail "the dev stack is not running (./scripts/dev.sh up --build)"
$DEV ps --status running --services | grep -qx db || fail "the db service is not running"
backend backend sh -c 'command -v age && command -v age-keygen' >/dev/null || fail "age/age-keygen missing in the backend image"
backend backend sh -c 'umask 077; mkdir -p /tmp/rt && cd /tmp/rt && [ -f server.key ] || { age-keygen -o server.key; age-keygen -o platform.key; }' >/dev/null 2>&1
SERVER_RECIPIENT="$(backend backend age-keygen -y /tmp/rt/server.key | tr -d '\r')"
PLATFORM_RECIPIENT="$(backend backend age-keygen -y /tmp/rt/platform.key | tr -d '\r')"
ENVS=(-e "BACKUP_AGE_RECIPIENT=$PLATFORM_RECIPIENT" -e "TENANT_MIGRATION_AGE_RECIPIENT=$SERVER_RECIPIENT"
      -e "TENANT_MIGRATION_AGE_IDENTITY_FILE=/tmp/rt/server.key" -e "BACKUP_PRESIGN_DRAIN_SECONDS=0"
      -e "TENANT_MIGRATION_PRESIGN_DRAIN_SECONDS=0")
shell() { $DEV exec -T "${ENVS[@]}" ${EXTRA_ENVS[@]+"${EXTRA_ENVS[@]}"} backend python manage.py shell; }
EXTRA_ENVS=()

step "1. Seed sample data and take the in-app one-space backup"
STATE="$(shell <<'PY' | tail -n 1
import json, time, uuid
from datetime import timedelta
from django.utils import timezone
from apps.accounts.models import User
from apps.backup.services import create_archive, run_archive
from apps.encryption.preparation import prepare_tenants
from apps.encryption.services import get_or_create_active_dek
from apps.maintenance.incidents.models import Incident
from apps.makerspaces.models import (DayPassProduct, GuardianConsent, GuardianConsentTerms, GuestPass, Makerspace,
                                     MinorProfile, VolunteerCredit)
from django.conf import settings

slug = f"roundtrip-{int(time.time())}"
space = Makerspace.objects.create(name=slug, slug=slug)
get_or_create_active_dek(space.pk)
def user(name):
    return User.objects.create_user(username=f"{slug}-{name}", email=f"{slug}-{name}@example.test",
                                    access_status=User.AccessStatus.ACTIVE)
root = User.objects.filter(is_superuser=True).first() or User.objects.create_superuser(
    f"{slug}-root", email=f"{slug}-root@example.test", password="x" * 20)
guest, kid, guardian, member = user("guest"), user("minor"), user("guardian"), user("member")
now = timezone.now()
product = DayPassProduct.objects.create(makerspace=space, name="Day pass", amount=5, currency="usd",
                                        entitlements={"presence": True, "borrow": "on_site", "machines": "none"})
GuestPass.objects.create(makerspace=space, holder=guest, kind="day", status="active", valid_from=now,
                         valid_until=now + timedelta(hours=8), pass_date=timezone.localdate(), product=product,
                         entitlements=product.entitlements, operation_id=f"{slug}-pass")
SECRET_GUARDIAN = "Gloria Guardian-Secret"
with prepare_tenants((space.pk,)):
    profile = MinorProfile.objects.create(makerspace=space, user=kid, date_of_birth="2014-03-02",
                                          guardian_name=SECRET_GUARDIAN, guardian_email="gg@example.test",
                                          guardian_phone="+15550001234", guardian_user=guardian, recorded_by=root)
    terms = GuardianConsentTerms.objects.create(makerspace=space, body="Guardian terms", version="v1", created_by=root)
    GuardianConsent.objects.create(profile=profile, makerspace=space, terms=terms, terms_version="v1",
                                   method="staff_recorded", signed_name=SECRET_GUARDIAN, recorded_by=root,
                                   signed_at=now, valid_until=now + timedelta(days=365), operation_id=f"{slug}-consent")
    Incident.objects.create(makerspace=space, reporter=member, involved_user=kid, involved_note="Cut finger on saw",
                            title="Saw nick", area="machines", severity="low")
VolunteerCredit.objects.create(makerspace=space, member=member, minutes_converted=60, kind="discount", amount=3,
                               currency="usd", created_by=root)
archive = run_archive(create_archive(root, scope="makerspace", makerspace=space).pk)
assert archive.status == "available", archive.failure_detail
assert archive.manifest["server_restorable"] is True
print("STATE:" + json.dumps({"slug": slug, "space": space.pk, "root": root.pk, "archive": str(archive.pk),
                             "secret": SECRET_GUARDIAN, "encryption": bool(settings.PII_ENCRYPTION_ENABLED)}))
PY
)"
STATE="${STATE#STATE:}"
[[ "$STATE" == \{* ]] || fail "seeding did not return its state: $STATE"
echo "$STATE"
EXTRA_ENVS=(-e "RT_STATE=$STATE")

COUNTS='
from apps.maintenance.incidents.models import Incident
from apps.makerspaces.models import (DayPassProduct, GuardianConsent, GuardianConsentTerms, GuestPass,
                                     MinorProfile, VolunteerCredit)
def counts(space):
    return {m.__name__: (m.objects.filter(profile__makerspace_id=space) if m is GuardianConsent else m.objects.filter(makerspace_id=space)).count()
            for m in (GuestPass, DayPassProduct, MinorProfile, GuardianConsent, GuardianConsentTerms, Incident, VolunteerCredit)}
'
EXPECT='{"GuestPass": 1, "DayPassProduct": 1, "MinorProfile": 1, "GuardianConsent": 1, "GuardianConsentTerms": 1, "Incident": 1, "VolunteerCredit": 1}'

step "2. Take the physical dump (whole database, as the host backup does)"
$DEV exec -T db sh -c 'pg_dump --format=custom --no-owner --no-acl -U makerspace makerspace_manager > /tmp/rt.dump && test -s /tmp/rt.dump'
$DEV exec -T db sh -c 'ls -l /tmp/rt.dump'

step "3. A. Disaster in the live space: delete the immutable rows and edit the rest"
shell <<PY
import json, os
$COUNTS
from django.db import connection, transaction
from apps.maintenance.incidents.models import Incident
from apps.makerspaces.models import GuestPass, VolunteerCredit
state = json.loads(os.environ["RT_STATE"])
with transaction.atomic(), connection.cursor() as cursor:
    cursor.execute("SET LOCAL app.allow_immutable_delete = 'on'")  # the same scope a restore/purge uses
    cursor.execute("DELETE FROM makerspaces_guestpass WHERE makerspace_id = %s", [state["space"]])
Incident.objects.filter(makerspace_id=state["space"]).delete()
VolunteerCredit.objects.filter(makerspace_id=state["space"]).update(amount=99)
after = counts(state["space"])
assert after["GuestPass"] == 0 and after["Incident"] == 0, after
print("after disaster:", after)
PY

step "4. A. In-app restore: request -> preview -> confirm -> apply"
shell <<PY
import json, os
$COUNTS
from apps.accounts.models import User
from apps.backup import space_restore_runner as runner, space_restore_services as services
from apps.backup.models import BackupArchive, MakerspaceRestoreOperation
from apps.backup import tasks_space_restore
from apps.encryption.preparation import prepare_tenants
from apps.makerspaces.models import GuardianConsent, MinorProfile, Makerspace, VolunteerCredit
from django.db import connection
tasks_space_restore._dispatch = lambda task, op: None   # run the steps here, not on the worker
state = json.loads(os.environ["RT_STATE"])
root, space = User.objects.get(pk=state["root"]), Makerspace.objects.get(pk=state["space"])
op = services.request_restore(root, space, BackupArchive.objects.get(pk=state["archive"]))
assert runner.run_preview(op.pk).stage == "preview_ready"
op.refresh_from_db(); assert op.preview["blocked"] is False, op.preview
services.confirm_restore(root, op, space.slug)
done = runner.run_apply(op.pk)
assert done.stage == "completed", (done.error_code, done.error_detail)
got = counts(space.pk); print("after restore:", got)
assert got == json.loads('$EXPECT'), got
assert VolunteerCredit.objects.get(makerspace=space).amount == 3
with prepare_tenants((space.pk,)):
    assert MinorProfile.objects.get(makerspace=space).guardian_name == state["secret"]
    assert GuardianConsent.objects.get(profile__makerspace=space).signed_name == state["secret"]
with connection.cursor() as cursor:
    cursor.execute("SELECT count(*) FROM pg_trigger WHERE tgname = 'makerspaces_guest_pass_guard_trigger' AND NOT tgisinternal")
    assert cursor.fetchone()[0] == 1, "guest pass guard trigger missing after restore"
print("A. in-app restore OK")
PY

step "5. B. Fresh database: create $SCRATCH_DB and pg_restore the physical dump into it"
$DEV exec -T db sh -c "dropdb --if-exists -U makerspace $SCRATCH_DB && createdb -U makerspace $SCRATCH_DB && pg_restore --exit-on-error --no-owner --no-acl -U makerspace -d $SCRATCH_DB /tmp/rt.dump"

step "6. B. Verify the restored database with the application (owner login, same keys)"
EXTRA_ENVS=(-e "RT_STATE=$STATE" -e "DATABASE_URL=$OWNER_URL")
shell <<PY
import json, os
$COUNTS
from django.db import connection
from apps.backup.managed.function_catalog import APPLICATION_FUNCTIONS
from apps.encryption.preparation import prepare_tenants
from apps.makerspaces.models import GuardianConsent, MinorProfile
state = json.loads(os.environ["RT_STATE"])
assert connection.settings_dict["NAME"] == "$SCRATCH_DB", connection.settings_dict["NAME"]
got = counts(state["space"]); print("scratch counts:", got)
# The dump was taken BEFORE the disaster, so it holds the original sample rows.
assert got == json.loads('$EXPECT'), got
with prepare_tenants((state["space"],)):
    assert MinorProfile.objects.get(makerspace_id=state["space"]).guardian_name == state["secret"]
    assert GuardianConsent.objects.get(profile__makerspace_id=state["space"]).signed_name == state["secret"]
with connection.cursor() as cursor:
    if state["encryption"]:
        cursor.execute("SELECT guardian_name FROM makerspaces_minorprofile WHERE makerspace_id = %s", [state["space"]])
        assert state["secret"] not in cursor.fetchone()[0], "guardian name is stored in clear text"
    cursor.execute("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal")
    triggers = {row[0] for row in cursor.fetchall()}
    for name in ("makerspaces_guest_pass_guard_trigger", "event_booking_decision_immutable", "event_booking_decision_owner",
                 "equipment_receipt_immutable", "equipment_use_receipt_immutable"):
        assert name in triggers, f"trigger {name} missing after restore"
    cursor.execute("SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
                   "WHERE n.nspname = 'public' AND p.prokind = 'f' AND NOT EXISTS (SELECT 1 FROM pg_depend d "
                   "WHERE d.classid = 'pg_proc'::regclass AND d.objid = p.oid AND d.deptype = 'e')")
    uncatalogued = sorted(r[0] for r in cursor.fetchall() if r[0] not in APPLICATION_FUNCTIONS and not r[0].startswith(("tenant_rls", "rls_")))
    assert uncatalogued == [], f"functions missing from the managed catalogue: {uncatalogued}"
    # The immutability guard still bites in the restored database.
    try:
        cursor.execute("DELETE FROM makerspaces_guestpass WHERE makerspace_id = %s", [state["space"]])
    except Exception as exc:
        assert "cannot be deleted" in str(exc), exc
    else:
        raise AssertionError("guest pass delete was allowed without the restore scope")
print("B. physical restore OK")
PY

if (( CLEAN )); then
  step "Cleanup"
  $DEV exec -T db sh -c "dropdb --if-exists -U makerspace $SCRATCH_DB; rm -f /tmp/rt.dump"
  backend backend sh -c 'rm -rf /tmp/rt'
  echo "Dropped $SCRATCH_DB. The test space $(printf '%s' "$STATE" | sed -n 's/.*"slug": "\([^"]*\)".*/\1/p') stays in the dev database (delete it from the superadmin console)."
fi
printf '\nROUNDTRIP PASSED\n'
