"""Machines of every built-in type, a live print queue, consumables and maintenance.

Machine rows mirror the staff create view (module lock, quota, audit) and publicity
mirrors the publicity view, because neither has a service function. Every status
change after that goes through the machines services: the service workflow moves jobs
pending -> accepted -> in_progress -> completed -> collected, `set_status` flags the
maintenance machine, and the maintenance services write schedules and logs.
"""
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.machines import role_scope
from apps.machines.models import Machine, MachineType, ServiceQueue
from apps.machines.service_consumable_pools import create_pool
from apps.machines.service_workflow import accept, collect, complete, start, submit
from apps.machines.services import set_status
from apps.maintenance import services as maintenance
from apps.makerspaces import limits
from apps.makerspaces.guards import require_module_locked

PUBLIC = ["queue_eta", "training"]
# (name, built-in type slug, location, type payload)
MACHINES = (
    ("Print Bay 1", "3d_printer", "Print farm", {"model": "FDM 250 mm"}),
    ("Print Bay 2", "3d_printer", "Print farm", {"model": "FDM 250 mm"}),
    ("Print Bay 3", "3d_printer", "Print farm", {"model": "FDM 350 mm"}),
    ("Resin Station", "resin_printer", "Print farm", {}),
    ("Laser Cutter 60 W", "laser_cutter", "Laser room", {}),
    ("CNC Router 1.2 m", "cnc_router", "Woodshop", {}),
    ("Benchtop CNC Mill", "cnc_mill", "Metal corner", {}),
    ("PCB Mill", "pcb_mill", "Electronics bay", {}),
    ("Vinyl Cutter", "vinyl_cutter", "Craft table", {}),
    ("Embroidery Machine", "other", "Textile studio", {}),
)


def seed_machines(makerspace, manager, machine_manager, members):
    machines = {}
    for name, slug, location, payload in MACHINES:
        machine_type = MachineType.objects.get(makerspace__isnull=True, slug=slug)
        machines[name] = _machine(makerspace, manager, machine_type, name, location, payload)
    printer_type = machines["Print Bay 1"].machine_type
    queue = ServiceQueue.objects.create(
        makerspace=makerspace, machine_type=printer_type, name="FDM print queue",
        description="Send us a model; staff slice and print it on the next free bay.",
    )
    pools = {
        "black": create_pool(makerspace, machine_manager, machine_type=printer_type, material="PLA",
                             color="Black", color_hex="#1f1f1f", initial_grams="2000",
                             low_threshold_grams="300", brand="Patchwork stock"),
        "white": create_pool(makerspace, machine_manager, machine_type=printer_type, material="PLA",
                             color="White", color_hex="#f5f5f5", initial_grams="1000",
                             low_threshold_grams="200", brand="Patchwork stock"),
        "petg": create_pool(makerspace, machine_manager, machine_type=printer_type, material="PETG",
                            color="Blue", color_hex="#2f6fde", initial_grams="300",
                            low_threshold_grams="250", brand="Patchwork stock"),
    }
    create_pool(makerspace, machine_manager, machine=machines["Resin Station"],
                material="Standard resin", color="Grey", quantity="1000", unit="milliliters",
                low_threshold_grams="200")
    _print_jobs(machine_manager, queue, machines, pools, members)
    _other_jobs(machine_manager, machines, members)
    _maintenance(manager, machine_manager, machines)
    return machines


def _machine(makerspace, actor, machine_type, name, location, payload):
    with transaction.atomic():
        require_module_locked(makerspace, "machines")
        limits.check_quota(makerspace, "machines", adding=1)
        machine = Machine.objects.create(
            makerspace=makerspace, machine_type=machine_type, created_by=actor, name=name,
            location=location, notes=f"{name} in the {location.lower()}.",
            public_fields=PUBLIC, type_payload=payload,
        )
        audit.record(actor, "machine.created", makerspace=makerspace, target=machine,
                     target_type="machine")
        machine = Machine.objects.select_for_update().get(pk=machine.pk)
        machine.is_public = True
        machine.save(update_fields=["is_public", "updated_at"])
        audit.record(actor, "machine.publicity_changed", makerspace=makerspace, target=machine,
                     meta={"from": False, "to": True})
    return machine


def _job(target, member, title, material="PLA", colour="Black", grams="40", actor=None):
    payload = None
    if isinstance(target, ServiceQueue):
        payload = {"requested_material": material, "requested_color": colour,
                   "quantity": 1, "estimated_grams": grams}
    return submit(target, member, actor=actor or member, requester_name=member.display_name,
                  contact_email=member.email, contact_phone="", title=title,
                  description=f"{title}. Files shared at the desk.", capability_payload=payload)


def _print_jobs(staff, queue, machines, pools, members):
    bay1, bay2 = machines["Print Bay 1"].pk, machines["Print Bay 2"].pk

    def run(username, title, bay, pool, colour, minutes, grams, material="PLA"):
        job = _job(queue, members[username], title, material, colour, grams)
        accept(job, staff, estimated_minutes=minutes)
        return start(job, staff, role_scope.EXEMPT, machine_id=bay, estimated_minutes=minutes,
                     consumable_pool_id=pool.pk, planned_grams=grams)

    done = run("aiko_tanaka", "Planter drip tray", bay1, pools["black"], "Black", 90, "40")
    complete(done, staff, actual_minutes=85, consumptions=[], actual_grams="38")
    collect(done, staff)
    ready = run("noor_rahman", "Cable clips, set of 20", bay2, pools["white"], "White", 60, "25")
    complete(ready, staff, actual_minutes=58, consumptions=[], actual_grams="24")
    run("asha_menon", "Sensor enclosure", bay1, pools["white"], "White", 180, "75")
    run("diego_ramos", "Van shelf brackets", bay2, pools["petg"], "Blue", 120, "60", "PETG")
    for username, title, minutes in (("ravi_kumar", "Garden hose adapter", 60),
                                     ("lena_ortiz", "Multimeter probe holder", 45)):
        accept(_job(queue, members[username], title), staff, estimated_minutes=minutes)
    _job(queue, members["kofi_mensah"], "Amplifier knob set")
    _job(queue, members["priya_nair"], "Robot chassis plate", grams="120")


def _other_jobs(staff, machines, members):
    _job(machines["Laser Cutter 60 W"], members["jonas_weber"], "Acrylic shop sign")
    accept(_job(machines["Vinyl Cutter"], members["sara_haddad"], "Club sticker sheet"), staff)


def _maintenance(manager, staff, machines):
    today = timezone.localdate()
    laser = machines["Laser Cutter 60 W"]
    maintenance.create_schedule(laser, actor=manager, description="Clean optics and check alignment",
                                interval_days=30, next_due=today - timedelta(days=4))
    for name in ("Print Bay 1", "Print Bay 2", "Print Bay 3"):
        schedule = maintenance.create_schedule(machines[name], actor=manager,
                                               description="Lubricate rails and check belts",
                                               interval_days=60, next_due=today - timedelta(days=1))
        maintenance.complete_due(schedule, actor=staff, summary="Rails lubricated, belts tensioned",
                                 cost=Decimal("4.50"), parts_note="PTFE grease")
    router = machines["CNC Router 1.2 m"]
    set_status(router, manager, Machine.Status.MAINTENANCE)
    maintenance.log_maintenance(router, actor=manager, summary="Spindle bearing noise; waiting on part",
                                parts_note="Spindle bearing ordered")
