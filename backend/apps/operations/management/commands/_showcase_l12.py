"""Tinkerspace: machines and loans depth (lane L12) -- something to show on every new screen.

Switches on the L12 features, then writes through the same services the screens use: a
vendor and a take-and-go consumable, a laser job queue with one job in each review state
(submitted, needs changes, quote sent), a bookable laser-time resource, an open work order,
and a loan pickup policy. Nothing here moves money.
"""

from decimal import Decimal

from apps.audit import services as audit
from apps.machines import service_workflow_review as review
from apps.machines.models import Machine, MakerspaceMachineTypePricing, ServiceQueue
from apps.machines.service_workflow import submit

FEATURES = ("inventory.consumables", "inventory.vendors", "inventory.expected_back", "loans.reservations",
            "loans.pickup_windows", "loans.waitlist", "loans.withdrawals", "machines.batch_start",
            "machines.time_booking", "machines.maintenance")


def seed_l12(space, manager, inventory_manager, machine_manager, members):
    space.enabled_features = sorted(set(space.enabled_features or []) | set(FEATURES))
    space.save(update_fields=["enabled_features"])
    _inventory(space, inventory_manager)
    laser = Machine.objects.filter(makerspace=space, machine_type__slug="laser_cutter").first()
    if laser is not None:
        _laser_jobs(space, manager, machine_manager, laser, list(members.values()))
        _machine_time(space, manager, laser)
    cnc = Machine.objects.filter(makerspace=space, machine_type__slug="cnc_router").first()
    if cnc is not None:
        from apps.maintenance.work_orders import create_work_order
        create_work_order(machine_manager, space, subject_type="machine", subject=cnc,
                          title="Replace the spindle brushes", priority="high",
                          description="Spindle sparks under load; brushes are past their wear mark.")


def _inventory(space, inventory_manager):
    from apps.hardware_requests.models_loans import LoanReservationPolicy
    from apps.inventory.models import InventoryProduct
    from apps.procurement.services_vendors import create_vendor
    create_vendor(inventory_manager, space, {"name": "Bolt & Nut Supplies", "contact_name": "Sales desk",
                                             "email": "sales@boltnut.example", "phone": "+91 80 4000 1000",
                                             "website": "https://boltnut.example", "notes": "Next-day delivery."})
    InventoryProduct.objects.create(makerspace=space, name="M3 screws (box of 100)", total_quantity=12,
                                    available_quantity=12, is_consumable=True, reorder_point=3,
                                    reorder_quantity=20, supplier="Bolt & Nut Supplies")
    LoanReservationPolicy.objects.update_or_create(makerspace=space, defaults={
        "pickup_window_hours": 48, "reservation_max_days_ahead": 14, "waitlist_offer_hours": 24})


def _laser_jobs(space, manager, machine_manager, laser, members):
    MakerspaceMachineTypePricing.objects.get_or_create(
        makerspace=space, machine_type=laser.machine_type,
        defaults={"rate_per_unit": Decimal("4.00"), "flat_fee": Decimal("20.00"), "payment_enabled": True})
    queue = ServiceQueue.objects.create(makerspace=space, machine_type=laser.machine_type, name="Laser jobs",
                                        description="Send a vector file; staff cut it on the 60 W laser.")
    member_cycle = members or [manager]
    titles = ("Acrylic name plates", "Plywood box joints", "Engraved coasters")
    jobs = []
    for index, title in enumerate(titles):
        member = member_cycle[index % len(member_cycle)]
        jobs.append(submit(queue, member, member=member, actor=member, requester_name=member.display_name or "",
                           contact_email=member.email or "", contact_phone="", title=title,
                           description="3 mm sheet, cut and light engrave."))
    review.request_changes(jobs[1], machine_manager, code="wrong_format",
                           message="Please export the box as an SVG with cut lines in red.")
    try:
        review.send_quote(jobs[2], machine_manager, estimated_minutes=25)
    except Exception:  # a free type in a customised space simply stays submitted
        pass


def _machine_time(space, manager, laser):
    from apps.bookings.services_spaces import create_space
    create_space(makerspace=space, actor=manager, name="Laser cutter time", kind="machine",
                 description="Book the 60 W laser for your own job (certification needed).", capacity=1,
                 location=laser.location or "Laser room", is_public=True, audit_service=audit, machine=laser.pk)
