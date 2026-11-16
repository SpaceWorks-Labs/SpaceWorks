"""Safe derived disclosures. Aggregate service estimates never carry requester data."""


from apps.accounts import rbac
from apps.makerspaces.platform import module_enabled, feature_enabled
from .models import CertificationType


def training(machine):
    if "training" not in machine.public_fields:
        return None
    if not feature_enabled(machine.makerspace, "machines.certifications"):
        return False
    return rbac.scope_public_catalogue(CertificationType.objects.all(), machine.makerspace).filter(
        machine_type_id=machine.machine_type_id, is_active=True, is_required_for_service=True,
    ).exists()


def queue_eligible(machine):
    return "queue_eta" in machine.public_fields and module_enabled(machine.makerspace, "machine_service")


def queue_summaries(machines):
    """One snapshot per page: per-machine final free-at summaries for opted-in machines.

    The workload includes private jobs and non-public compatible machines, but the
    summary is aggregate-only: no job, member or machine identifiers are disclosed.
    """
    from .service_queue_eta import machine_queue_summaries_for
    eligible = [machine for machine in machines if queue_eligible(machine)]
    return machine_queue_summaries_for(eligible) if eligible else {}


def queue_estimate(machine, summaries=None):
    if not queue_eligible(machine):
        return None
    if summaries is None:
        summaries = queue_summaries([machine])
    return summaries.get(machine.pk)
