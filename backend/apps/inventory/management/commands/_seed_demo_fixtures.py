"""Account and machine fixtures for the demo command."""
from decimal import Decimal
from django.core.management.base import CommandError
from django.db import transaction
from apps.accounts.models import User
from apps.accounts.staff_accounts import create_staff_account
from apps.machines.models import Machine, MachineConsumablePool, MachineServiceRequest, MachineType
from apps.machines.service_workflow import submit as submit_service_request


def seed_user(username, email, password, role, **flags):
    platform = role == User.Role.SUPERADMIN
    kind = "platform" if platform else "member"
    user, created = User.objects.get_or_create(username=username, defaults={
        "email": email, "account_kind": kind, "role": role,
        "is_superuser": platform, "is_staff": platform,
    })
    if user.account_kind != kind or user.is_walk_in:
        raise CommandError(f"Existing demo identity {username!r} requires a dev data rebuild.")
    user.email, user.role = email, role
    user.access_status, user.must_change_password = "active", False
    user.set_password(password)
    user.save()
    return user


@transaction.atomic
def seed_staff(makerspace, actor, username, password):
    user = User.objects.filter(username=username).first()
    if user is None:
        user = create_staff_account(makerspace, name=username, username=username,
            email=f"{username}@makerspace.local", roles=[makerspace.roles.get(slug="space_manager")],
            machine_type_ids=[], created_by=actor)
        # Keep the documented dev login. Usernames are global and mutable identifiers;
        # account kind and the captured tenant remain immutable.
        user.username = username
    if user.account_kind != "staff" or user.staff_makerspace_id != makerspace.pk:
        raise CommandError(f"Existing demo identity {username!r} requires a dev data rebuild.")
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
