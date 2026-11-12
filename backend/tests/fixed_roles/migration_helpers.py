"""Historical fixtures shared by the real upgrade and pre-upgrade CLI tests."""
from datetime import timedelta

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.models import Q
from django.utils import timezone

from apps.makerspaces.role_migration_mapping import FROZEN_BY_SLUG, LEGACY_HANDOUT_ACTIONS

PRE_TARGETS = [
    ("makerspaces", "0090_website_embedding"),
    ("machines", "0026_public_detail_materials_intake"),
    ("accounts", "0031_platformloginmethods_provider_switches"),
    ("integrations", "0032_email_source_identity"),
    ("operations", "0013_stocktake_discipline"),
    ("audit", "0009_audit_verification_runs"),
]
DATA_TARGET = [("makerspaces", "0092_fixed_roles_data")]


_TEMPLATE_BUILT = set()  # template databases built (migrated forward) in this pytest process


@pytest.fixture
def old_database(transactional_db):
    """A pre-fixed-roles database, built FORWARD in a scratch database.

    The old fixture reversed the test database to ``PRE_TARGETS``. Since decision 63 the account
    unification (accounts 0050) is irreversible, so that rollback raised mid-way and the forward
    restore then spun. An upgrade is what these tests exercise, and a real upgrade starts from a
    database that was only ever migrated forward: migrate a template database to ``PRE_TARGETS``
    once per pytest process, clone it per test, point the default connection at the clone for
    the test, then drop the clone. The shared test database is never migrated backwards.
    """
    from django.contrib.contenttypes.models import ContentType

    main = connection.settings_dict["NAME"]
    template, scratch = f"{main}_prefr_tpl"[:63], f"{main}_prefr"[:63]

    def use(name):
        connection.close()
        connection.settings_dict["NAME"] = name

    def admin(statement):
        use(main)
        with connection.cursor() as cursor:
            cursor.execute(statement)

    if template not in _TEMPLATE_BUILT:
        admin(f'DROP DATABASE IF EXISTS "{template}" WITH (FORCE)')
        admin(f'CREATE DATABASE "{template}"')
        use(template)
        try:
            MigrationExecutor(connection).migrate(PRE_TARGETS)
        finally:
            use(main)
        _TEMPLATE_BUILT.add(template)
    admin(f'DROP DATABASE IF EXISTS "{scratch}" WITH (FORCE)')
    admin(f'CREATE DATABASE "{scratch}" TEMPLATE "{template}"')
    use(scratch)
    ContentType.objects.clear_cache()
    try:
        yield MigrationExecutor(connection).loader.project_state(PRE_TARGETS).apps
    finally:
        ContentType.objects.clear_cache()
        admin(f'DROP DATABASE IF EXISTS "{scratch}" WITH (FORCE)')


def upgrade():
    executor = MigrationExecutor(connection)
    executor.migrate(DATA_TARGET)
    return executor.loader.project_state(DATA_TARGET).apps


def historical_world(apps):
    model = lambda label: apps.get_model(label)
    space = model("makerspaces.Makerspace").objects.create(name="Historical lab", slug="historical-fixed")
    other = model("makerspaces.Makerspace").objects.create(name="Other lab", slug="historical-other")
    # Historical creates skip the post_save signal that seeds each makerspace's PII write
    # fence, and the flushed test database may lack the global singleton; the PII triggers
    # on membership requests refuse every write without both. The fence tables are
    # unchanged across these migrations, so the live models are safe to use here.
    from apps.encryption.models import PiiGlobalWriteFence, PiiMakerspaceWriteFence
    PiiGlobalWriteFence.objects.get_or_create(pk=1)
    for owner in (space, other):
        PiiMakerspaceWriteFence.objects.get_or_create(makerspace_id=owner.pk)
    roles = {}

    def role(slug, grants, *, name=None, default=False, protected=False, owner=space, legacy=None):
        row = model("makerspaces.MakerspaceRole").objects.create(
            makerspace=owner, name=name or slug, slug=slug, granted_actions=sorted(grants),
            is_default=default, is_protected=protected, legacy_role=legacy,
        )
        if owner.pk == space.pk:
            roles[slug] = row
        return row

    # Swap the old default labels; canonicalization must clear BOTH names first.
    role("space_manager", {"manage_makerspace"}, name="Inventory Manager",
         default=True, protected=True, legacy="space_manager")
    role("inventory_manager", FROZEN_BY_SLUG["inventory_manager"][3] | {"manage_bookings"},
         name="Space Manager", default=True, protected=True, legacy="inventory_manager")
    role("machine_manager", {"manage_machines"}, name="Old machine manager",
         default=True, protected=True, legacy="machine_manager")
    role("member", (), name="Member", default=True, protected=True)
    role("event_manager", {"manage_events"}, name="Event Manager")
    role("handover", LEGACY_HANDOUT_ACTIONS, name="Handover")
    role("print_manager", {"manage_printing"}, name="Print Manager",
         default=True, protected=True, legacy="print_manager")
    role("inventory-events", FROZEN_BY_SLUG["inventory_manager"][3] | {"manage_events"})
    role("typed", {"manage_machines"})
    role("machine-only", {"manage_machines"})
    role("empty", {"manage_machines"})
    role("exempt", {"manage_makerspace", "manage_machines"})
    foreign_role = role("foreign", {"manage_events"}, owner=other)
    kind = model("machines.MachineType").objects.create(makerspace=space, name="Laser", slug="historical-laser")
    global_kind = model("machines.MachineType").objects.create(name="Global kiln", slug="historical-global", is_builtin=True)
    foreign_kind = model("machines.MachineType").objects.create(makerspace=other, name="Other laser", slug="historical-foreign")
    machine = model("machines.Machine").objects.create(makerspace=space, machine_type=kind, name="Laser one")
    model("machines.RoleMachineTypeScope").objects.create(role=roles["typed"], machine_type=kind)
    for slug in ("typed", "machine-only"):
        model("machines.RoleMachineScope").objects.create(role=roles[slug], machine=machine)
    memberships = {}
    for index, slug in enumerate([*roles, "legacy", "foreign"]):
        user = model("accounts.User").objects.create(username=f"historical-holder-{index}",
                email=f"holder-{index}@example.test", password="!", access_status="active")
        assigned = None if slug == "legacy" else foreign_role if slug == "foreign" else roles[slug]
        memberships[slug] = model("makerspaces.MakerspaceMembership").objects.create(
            makerspace=space, user=user, assigned_role=assigned,
            role="machine_manager" if slug == "legacy" else (assigned.legacy_role or "custom"),
        )
    user = model("accounts.User").objects.create(username="historical-typed-peer", password="!")
    memberships["typed-peer"] = model("makerspaces.MakerspaceMembership").objects.create(
        makerspace=space, user=user, assigned_role=roles["typed"], role="custom",
    )
    model("makerspaces.MakerspaceMembership").objects.filter(pk=memberships["inventory-events"].pk).update(status="revoked")
    actor = memberships["space_manager"].user
    requests = {}
    for state in ("requested", "invited", "awaiting_vouches", "awaiting_payment", "active", "revoked"):
        requests[state] = model("makerspaces.MembershipRequest").objects.create(
            makerspace=space, kind="request", state=state, assigned_role=roles["event_manager"],
        )
    requests["closed-default"] = model("makerspaces.MembershipRequest").objects.create(
        makerspace=space, kind="request", state="active", assigned_role=roles["inventory_manager"],
    )
    requests["null"] = model("makerspaces.MembershipRequest").objects.create(
        makerspace=space, kind="request", state="active", assigned_role=None,
    )
    invitations = {}
    for label, slug, snapshot in [
        ("valid", "inventory-events", roles["inventory-events"].granted_actions),
        ("stale", "event_manager", ["manage_bookings"]),
        ("e2", "handover", roles["handover"].granted_actions),
        ("closed", "event_manager", roles["event_manager"].granted_actions),
    ]:
        invitations[label] = model("accounts.StaffInvitation").objects.create(
            makerspace=space, role=roles[slug], granted_actions=snapshot, created_by=actor,
            token_digest=label.ljust(64, "0"), email_ciphertext="", expires_at=timezone.now() + timedelta(days=1),
            failed_attempts=2,
            accepted_at=timezone.now() if label == "closed" else None,
        )
    schedules = {}
    for label, recipients, emails in [("empty", ["inventory-events"], []),
                                     ("mixed", ["inventory-events", "space_manager"], []),
                                     ("email", ["inventory-events"], ["external@example.test"])]:
        schedules[label] = model("operations.ReportSchedule").objects.create(
            makerspace=space, report_key="most-lent", next_run_at=timezone.now(),
            recipient_roles=recipients, recipient_emails=emails,
        )
    return dict(space=space, other=other, roles=roles, memberships=memberships,
                kind=kind, global_kind=global_kind, foreign_kind=foreign_kind, machine=machine,
                requests=requests, invitations=invitations, schedules=schedules,
                all_type_ids=set(model("machines.MachineType").objects.filter(
                    Q(makerspace=space)
                    | Q(makerspace=None)
                ).values_list("pk", flat=True)))
