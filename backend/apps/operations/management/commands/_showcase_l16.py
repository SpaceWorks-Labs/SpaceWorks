"""Tinkerspace: technicians, issue reports and repairs (lane L16) -- something on every new screen.

Switches on the per-parent repairs, reporting and item/room maintenance keys, then writes through
the same services the screens use: an in-house Technician covering the laser type, an outside
contractor, a staff-opened machine repair assigned to the Technician, a room repair with a quote
waiting for approval, and an item maintenance schedule. Nothing is sent and no money moves.
"""

from datetime import timedelta

from django.utils import timezone

FEATURES = ("machines.maintenance", "machines.repairs", "machines.issue_reporting", "inventory.maintenance",
            "inventory.repairs", "inventory.issue_reporting", "bookings.room_maintenance", "bookings.room_repairs",
            "bookings.issue_reporting")


def seed_l16(space, root, manager, password):
    from apps.machines.models import Machine
    from apps.maintenance.models import TechnicianContact, TechnicianCoverage
    from apps.maintenance.repairs import maintenance_subjects, services_issues as issues, services_work as work
    from apps.makerspaces.staff_role_grants import grant_staff_role

    from ._showcase_people import member_account
    space.enabled_features = sorted(set(space.enabled_features or []) | set(FEATURES))
    space.save(update_fields=["enabled_features"])
    tech = member_account("tinker_tech", "Tara Technician", password)
    grant_staff_role(makerspace=space, user=tech, actor=root, roles=[space.roles.get(slug="technician")],
                     machine_type_ids=[])
    laser = Machine.objects.filter(makerspace=space, machine_type__slug="laser_cutter").first()
    in_house = TechnicianContact.objects.create(makerspace=space, kind="in_house", person=tech, name="Tara Technician",
                                                email=tech.email)
    if laser is not None:
        TechnicianCoverage.objects.create(contact=in_house, kind="machine_type", machine_type=laser.machine_type)
        job = issues.open_issue(manager, space, subject_type="machine", subject=laser, title="Laser loses focus",
                                description="Cuts are fuzzy on the right half of the bed.", priority="high")
        issues.assign(manager, job, contact=in_house)
    contractor = TechnicianContact.objects.create(
        makerspace=space, kind="external", name="Ravi Electricals", email="ravi@example.org", phone="+91 98000 00000",
        notes="Fixes room lighting and extraction fans.")
    TechnicianCoverage.objects.create(contact=contractor, kind="inventory")
    room = space.bookable_spaces.filter(machine__isnull=True).first()
    if room is not None:
        TechnicianCoverage.objects.create(contact=contractor, kind="room", room=room)
        repair = issues.open_issue(manager, space, subject_type="bookable_space", subject=room,
                                   title="Extraction fan rattles", description="Loud rattle above 50% speed.")
        issues.assign(manager, repair, contact=contractor)
        work.quote(manager, repair, amount="1800.00", currency="inr", contact_id=contractor.pk,
                   note="New bearing and a service visit.")
    product = space.products.filter(is_archived=False).first()
    if product is not None:
        maintenance_subjects.create_schedule(manager, space, subject_type="inventory_product", subject=product,
                                             description="Check cables and clean contacts", interval_days=30,
                                             next_due=timezone.localdate() + timedelta(days=3))
