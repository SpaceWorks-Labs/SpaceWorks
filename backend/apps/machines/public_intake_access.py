"""Admission to public machine-job intake, independent of borrowing and staff work."""
from rest_framework.exceptions import NotFound

from apps.accounts.claim_sessions import claim_context
from apps.makerspaces.platform import feature_enabled, module_enabled
from django.utils.translation import gettext

from apps.machines.job_policy import JOB_REQUESTS


def require_job_requests(makerspace):
    """Every member intake (job, print, per-machine) sits behind `machines.job_requests` (dec 221e)."""
    if not feature_enabled(makerspace, JOB_REQUESTS):
        from apps.makerspaces.guards import feature_off
        raise feature_off(JOB_REQUESTS, gettext("Job requests are switched off here."))


def require_public_intake_available(makerspace):
    require_job_requests(makerspace)
    if not module_enabled(makerspace, "membership") or not module_enabled(makerspace, "presence"):
        raise NotFound({"detail": gettext("Public machine-job intake is unavailable. Please ask staff."),
                        "code": "machine_intake_unavailable"})


def require_public_machine_requester(user, makerspace):
    require_public_intake_available(makerspace)
    from apps.makerspaces.minors_guard import require_minor_clearance  # decision 223 (k)
    require_minor_clearance(user, makerspace, "machine")
    from apps.presence.guard import MemberPresenceRequired
    from apps.presence.guest_guard import require_member_or_guest
    if claim_context(user) is not None:
        raise MemberPresenceRequired()
    return require_member_or_guest(user, makerspace)  # decision 223: a live guest pass is admitted too


def require_guest_job(active, user, makerspace, machine_type):
    """A pass holder's job intake follows the machine mode (supervised use is never a job)."""
    if active.guest_pass is not None:
        from apps.machines.guest_access import require_guest_machine
        require_guest_machine(active.guest_pass, user, makerspace, machine_type=machine_type, surface="job")
