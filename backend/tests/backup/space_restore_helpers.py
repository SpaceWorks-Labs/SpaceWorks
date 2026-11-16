"""Seed, archive and fingerprint helpers for the per-space restore tests (local only)."""

import json
from decimal import Decimal

from django.apps import apps
from django.conf import settings
from django.utils import timezone

from apps.backup import storage
from apps.backup.archive_objects import capture_objects
from apps.backup.archive_payload import _storage_modes, _tenant_payload
from apps.backup.slice_rows import SLICE_ROW_SPECS
from apps.backup.space_restore_plan import SpaceArchive, live_queryset
from apps.boxes.models import QrCode
from apps.encryption.services import get_or_create_active_dek
from apps.events.models import Event, EventRegistration
from apps.hardware_requests.models import HardwareRequest
from apps.makerspaces.models import MakerspaceMembership
from apps.payments.models import Payment
from tests.data_export.portable_helpers import make_space, make_user


def put_public(key, payload):
    storage.client().put_object(Bucket=settings.PUBLIC_IMAGE_BUCKET, Key=key, Body=payload)


def read_public(key):
    return storage.client().get_object(Bucket=settings.PUBLIC_IMAGE_BUCKET, Key=key)["Body"].read()


def seed_space(slug, user):
    from apps.encryption.preparation import prepare_tenants

    space = make_space(slug)
    get_or_create_active_dek(space.pk)
    MakerspaceMembership.objects.create(
        makerspace=space, user=user, role=MakerspaceMembership.Role.CUSTOM,
        assigned_role=space.roles.get(slug="member"),
    )
    request = HardwareRequest.objects.create(
        makerspace=space, requester=user, requester_username=user.username,
        requester_name="Archive Member", requester_contact_email="member@example.test",
        requester_contact_phone="+15550001111",
    )
    event = Event.objects.create(
        makerspace=space, title="Workshop", created_by=user,
        starts_at=timezone.now() + timezone.timedelta(days=1),
        ends_at=timezone.now() + timezone.timedelta(days=1, hours=2),
    )
    with prepare_tenants((space.pk,)):
        EventRegistration.objects.create(event=event, name="Archive Member", email="member@example.test",
                                         phone="+15550001111", member=user)
    QrCode.objects.create(makerspace=space, target_type=QrCode.TargetType.BOX, target_id=1)
    key = f"spike/{slug}/logo.png"
    put_public(key, f"logo-of-{slug}".encode())
    space.logo_key = key
    space.save(update_fields=["logo_key"])
    return space, request


def charge(space, user, label="Workshop fee"):
    """A pending charge for a fresh registration on the space's event (one subject per charge)."""
    from apps.encryption.preparation import prepare_tenants

    event = Event.objects.filter(makerspace=space).order_by("pk").first()
    serial = Payment.objects.filter(makerspace=space).count()
    with prepare_tenants((space.pk,)):
        registration = EventRegistration.objects.create(event=event, name="Payer", email=f"payer{serial}@example.test",
                                                        phone=f"+1555000222{serial}")
    return Payment.objects.create(
        makerspace=space, member=user, created_by=user, subject_type=Payment.SubjectType.EVENT_REGISTRATION,
        subject_id=registration.pk, amount=Decimal("5.00"), currency="usd", status=Payment.Status.PENDING, subject_label=label,
    )


def build_space_archive(space, root):
    """The raw slice + objects + manifest exactly as a per-space archive carries them."""
    root.mkdir(parents=True, exist_ok=True)
    object_keys = _tenant_payload(space.pk, root / "tenant")
    objects = capture_objects(root / "objects", object_keys, _storage_modes())
    manifest = {"scope": "makerspace", "makerspace_id": space.pk,
                "snapshot_at": timezone.now().isoformat(), "storage": {"objects": objects}}
    (root / "manifest.json").write_text(json.dumps(manifest, default=str), encoding="utf-8")
    return SpaceArchive(root)


def _plain(value):
    if isinstance(value, (bytes, memoryview)):
        return bytes(value).hex()
    return str(value)


def fingerprint(makerspace_id):
    """Every dataset row of one space, as raw column values keyed by (label, pk)."""
    rows = {}
    for label in sorted(SLICE_ROW_SPECS):
        model = apps.get_model(label)
        columns = [field.attname for field in model._meta.concrete_fields]
        for row in live_queryset(label, makerspace_id).values(*columns):
            rows[(label, str(row[model._meta.pk.attname]))] = json.dumps(row, sort_keys=True, default=_plain)
    return rows


__all__ = ("build_space_archive", "charge", "fingerprint", "make_user", "read_public", "seed_space", "put_public")
