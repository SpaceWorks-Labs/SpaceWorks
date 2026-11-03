"""Per-space, per-machine-type job settings with their built-in defaults (#140-#142).

One read path for every caller: the intake gate, the quote rule, the failure charge, the
ETA calendar and the accepted file formats. A missing policy row means every default.
"""

from decimal import Decimal

from apps.makerspaces.platform import feature_enabled

from .models_policy import MakerspaceMachineTypePolicy as Policy

JOB_REQUESTS = "machines.job_requests"
JOB_QUOTES = "machines.job_quotes"
BATCH_START = "machines.batch_start"
PAY_BEFORE_PICKUP = "machines.pay_before_pickup"
QUOTE_VALID_DAYS = 7
QUOTE_REMINDER_DAY = 5
KEEP_PLACE_DAYS = 3
PICKUP_REMINDER_DAYS = (3, 10)
UNCOLLECTED_AFTER_DAYS = 14
NO_SHOW_LIMIT, NO_SHOW_WINDOW_DAYS = 3, 180
MAX_AUTO_REQUEUES = 2

# #142 OQ-12: maker_formats groups by built-in type slug; images always ride along.
DEFAULT_FILE_GROUPS = {
    "3d_printer": ("fab-3dprint", "hardware-cad"),
    "resin_printer": ("fab-3dprint", "hardware-cad"),
    "laser_cutter": ("fab-2d",),
    "vinyl_cutter": ("fab-2d",),
    "cnc_router": ("fab-cnc", "fab-2d", "hardware-cad"),
    "pcb_mill": ("hardware-pcb",),
    "embroidery": ("embroidery",),
}
FALLBACK_FILE_GROUPS = ("fab-2d", "fab-3dprint", "hardware-cad")
UNATTENDED_SLUGS = frozenset({"3d_printer", "resin_printer"})


def policy_for(makerspace, machine_type):
    space_id = getattr(makerspace, "pk", makerspace)
    row = Policy.objects.filter(makerspace_id=space_id, machine_type=machine_type).first()
    return row or Policy(makerspace_id=space_id, machine_type=machine_type)


def accepts_jobs(makerspace, machine_type):
    return feature_enabled(makerspace, JOB_REQUESTS) and policy_for(makerspace, machine_type).accepts_job_requests


def file_groups(makerspace, machine_type):
    groups = tuple(policy_for(makerspace, machine_type).file_groups or ())
    return groups or DEFAULT_FILE_GROUPS.get(machine_type.slug, FALLBACK_FILE_GROUPS)


def runs_unattended(makerspace, machine_type, policy=None):
    value = (policy or policy_for(makerspace, machine_type)).runs_unattended
    return machine_type.slug in UNATTENDED_SLUGS if value is None else bool(value)


def quote_required(makerspace, machine_type, total):
    """#142 OQ-2: off / above an amount / always; default always when priced, off when free."""
    if not feature_enabled(makerspace, JOB_QUOTES):
        return False
    policy = policy_for(makerspace, machine_type)
    total = Decimal(total or 0)
    if policy.quote_mode == Policy.QuoteMode.OFF:
        return False
    if policy.quote_mode == Policy.QuoteMode.ALWAYS:
        return True
    if policy.quote_mode == Policy.QuoteMode.ABOVE:
        return total > (policy.quote_above_amount or Decimal("0"))
    return total > 0


def prepay(makerspace, machine_type):
    return policy_for(makerspace, machine_type).payment_timing == Policy.PaymentTiming.PREPAY


def member_fault_charge(makerspace, machine_type):
    return policy_for(makerspace, machine_type).member_fault_charge
