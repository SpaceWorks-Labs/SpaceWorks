"""Decision 319: convert certification qualifications into machine access grants (idempotent).

Nobody loses access on upgrade:
* a machine type the space actually GATED (the certifications switch on and a required, active
  certification type) gives a type-wide grant to every active member who met the requirements of ANY
  purpose it was gated for (decision 335(a)): every service-required type, OR every booking-required
  type. Requirements were purpose-specific, so collapsing them into "hold every required type" would
  remove access a member had. The grant expires when the qualifying purpose's earliest certification
  expires (the later of the two purposes when both qualify). A purpose that was never gated (no type
  required for it) qualifies nobody: only purposes the machine was gated for count;
* every machine of a type that was NOT gated was open to every member, so it becomes "open to all
  members";
* every live guest certification becomes a type grant for that guest.
Certification rows are never touched. Re-running creates nothing twice.
"""
from django.db import migrations
from django.db.models import Q
from django.utils import timezone

NOTE = "Converted from a certification when machine access grants replaced certifications."


def _live(rows, now):
    return rows.filter(revoked_at__isnull=True).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))


def _ensure(Grant, space_id, user_id, machine_type_id, granted_at, expires_at):
    # Scoped to the space: a built-in (global) type gated in two spaces converts in each of them.
    if not Grant.objects.filter(makerspace_id=space_id, member_id=user_id, machine_type_id=machine_type_id,
                                machine__isnull=True, revoked_at__isnull=True).exists():
        Grant.objects.create(makerspace_id=space_id, member_id=user_id, machine_type_id=machine_type_id,
                             granted_at=granted_at, expires_at=expires_at, source="migration", note=NOTE)


def _held(CertGrant, membership_id, required, now):
    """The live certification for each required type, or None when one is missing."""
    held = []
    for row in required:
        best = _live(CertGrant.objects.filter(membership_id=membership_id, certification_type_id=row.pk),
                     now).order_by("-granted_at", "-pk").first()
        if best is None:
            return None
        held.append(best)
    return held


def _qualifying(CertGrant, membership_id, purposes, now):
    """``(granted_at, expires_at)`` from the best purpose the member met, or None when they met none."""
    best = None
    for required in purposes:
        held = _held(CertGrant, membership_id, required, now) if required else None
        if not held:
            continue
        expiries = [g.expires_at for g in held if g.expires_at is not None]
        option = (max(g.granted_at for g in held), min(expiries) if expiries else None)
        # Never expiring beats any expiry; otherwise the later expiry keeps the most access.
        if best is None or (best[1] is not None and (option[1] is None or option[1] > best[1])):
            best = option
    return best


def convert(apps, schema_editor):
    Space = apps.get_model("makerspaces", "Makerspace")
    Membership = apps.get_model("makerspaces", "MakerspaceMembership")
    Machine = apps.get_model("machines", "Machine")
    CertType = apps.get_model("machines", "CertificationType")
    CertGrant = apps.get_model("machines", "CertificationGrant")
    Guest = apps.get_model("machines", "GuestCertificationGrant")
    Grant = apps.get_model("machines", "MachineAccessGrant")
    now = timezone.now()
    for space in Space.objects.all().iterator():
        gated_types = set()
        if "machines.certifications" in (space.enabled_features or []):
            by_type = {}
            for row in CertType.objects.filter(makerspace_id=space.pk, is_active=True).filter(
                    Q(is_required_for_service=True) | Q(is_required_for_booking=True)):
                service, booking = by_type.setdefault(row.machine_type_id, ([], []))
                if row.is_required_for_service:
                    service.append(row)
                if row.is_required_for_booking:
                    booking.append(row)
            gated_types = set(by_type)
            for type_id, purposes in by_type.items():
                for membership in Membership.objects.filter(makerspace_id=space.pk, status="active"):
                    qualified = _qualifying(CertGrant, membership.pk, purposes, now)
                    if qualified is not None:
                        _ensure(Grant, space.pk, membership.user_id, type_id, *qualified)
        Machine.objects.filter(makerspace_id=space.pk).exclude(machine_type_id__in=gated_types).update(
            open_to_all_members=True)
        for row in _live(Guest.objects.filter(makerspace_id=space.pk, certification_type__is_active=True), now):
            _ensure(Grant, space.pk, row.user_id, row.certification_type.machine_type_id, row.granted_at, row.expires_at)


class Migration(migrations.Migration):
    dependencies = [("machines", "0039_machine_access_grants")]
    operations = [migrations.RunPython(convert, migrations.RunPython.noop)]
