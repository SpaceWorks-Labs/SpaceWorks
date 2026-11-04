"""Account and machine fixtures for the demo command."""
from decimal import Decimal
from django.core.management.base import CommandError
from django.db import transaction
from apps.accounts.staff_identity import PERSON_KIND, PLATFORM_KIND, context_label, is_person
from apps.accounts.models import User
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.staff_role_grants import grant_staff_role
from apps.machines.models import Machine, MachineConsumablePool, MachineServiceRequest, MachineType
from apps.machines.service_workflow import submit as submit_service_request


def seed_user(username, email, password, role, **flags):
    platform = role == User.Role.SUPERADMIN
    kind = PLATFORM_KIND if platform else PERSON_KIND
    user, created = User.objects.get_or_create(username=username, defaults={
        "email": email, "account_kind": kind, "role": role,
        "is_superuser": platform, "is_staff": platform,
    })
    if context_label(user) != kind or user.is_walk_in:
        raise CommandError(f"Existing demo identity {username!r} requires a dev data rebuild.")
    user.email, user.role = email, role
    user.access_status, user.must_change_password = "active", False
    user.set_password(password)
    user.save()
    return user


@transaction.atomic
def seed_staff(makerspace, actor, username, password):
    """One account per person: the documented dev login is a person holding the Space
    Manager staff role in the demo space (granted by the superadmin, #110)."""
    user = User.objects.filter(username=username).first()
    if user is None:
        user = User.objects.create_user(username, email=f"{username}@makerspace.local",
                                        display_name=username, role=User.Role.SPACE_MANAGER)
    if not is_person(user) or user.is_walk_in:
        raise CommandError(f"Existing demo identity {username!r} requires a dev data rebuild.")
    if not MakerspaceMembership.staff_tracks.filter(makerspace=makerspace, user=user).exists():
        grant_staff_role(makerspace=makerspace, user=user, actor=actor,
                         roles=[makerspace.roles.get(slug="space_manager")])
    user.set_password(password)
    user.must_change_password = False
    user.save()
    return user


def seed_machine_service(makerspace, requester):
    printer_type = MachineType.objects.get(makerspace__isnull=True, slug="3d_printer")
    machine, _ = Machine.objects.update_or_create(
        makerspace=makerspace,
        name="Demo 3D Printer",
        defaults={
            "machine_type": printer_type,
            "location": "Fabrication Bench",
            "notes": "Seeded kernel machine-service printer.",
            "is_public": True,
            "type_payload": {"model": "Prusa MK4"},
            "created_by": requester,
        },
    )
    MachineConsumablePool.objects.get_or_create(
        makerspace=makerspace,
        machine=machine,
        material="PLA",
        color="Black",
        brand="Demo",
        lot_code="DEMO-PLA",
        defaults={
            "initial_grams": Decimal("1000.00"),
            "remaining_grams": Decimal("1000.00"),
            "low_threshold_grams": Decimal("200.00"),
            "created_by": requester,
        },
    )
    if MachineServiceRequest.objects.filter(
        makerspace=makerspace, title="Demo 3D print request"
    ).exists():
        return 0
    submit_service_request(
        machine,
        requester,
        actor=requester,
        requester_name=requester.username,
        contact_email=requester.email,
        contact_phone="",
        title="Demo 3D print request",
        description="Seeded machine-service sample.",
        capability_payload={
            "requested_material": "PLA",
            "requested_color": "Black",
            "quantity": 1,
            "estimated_grams": "25.00",
        },
    )
    return 1
