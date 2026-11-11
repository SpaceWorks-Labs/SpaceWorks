"""The ONE "Request a job" intake for every machine type (#140, #142 OQ-1/OQ-10/OQ-12).

The 3D-printer form and the generic machine-service form both end here, so every type
shares the same gate, queue, quote rule, files and timeline:

* members only: a member of THIS makerspace, checked in now, waiver signed when waivers
  are on (`require_public_machine_requester`, the existing presence gate);
* `machines.job_requests` on, and the machine type accepting jobs (per-type setting);
* at most `max_open_jobs` unfinished jobs per member and type when the space set one;
* files checked against the type's `maker_formats` groups before they attach.
"""

from django.utils.translation import gettext
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.machines import job_policy
from apps.machines.models import ServiceQueue

ACKNOWLEDGEMENTS = ("pickup_policy", "failure_policy", "own_content")


def require_member_job_gate(makerspace, user, machine_type):
    from apps.machines.public_intake_access import require_guest_job
    from apps.machines.views_public_service import require_public_machine_requester
    active = require_public_machine_requester(user, makerspace)  # `machines.job_requests` first (feature_off 404)
    require_guest_job(active, user, makerspace, machine_type)  # decision 223 (d)
    if not job_policy.accepts_jobs(makerspace, machine_type):
        raise ValidationError({"queue_id": gettext("This machine type is not taking job requests."), "code": "type_closed"})


def job_queues(makerspace):
    """Active queues whose type takes job requests, for the request form."""
    from apps.accounts import rbac
    rows = rbac.scope_verified_tenant(ServiceQueue.objects.all(), makerspace).filter(
        is_active=True).select_related("machine_type").order_by("name", "id")
    return [row for row in rows if job_policy.accepts_jobs(makerspace, row.machine_type)]


def resolve_queue(makerspace, queue_id):
    queue = next((row for row in job_queues(makerspace) if row.pk == queue_id), None)
    if queue is None:
        raise ValidationError({"queue_id": gettext("Choose a machine type that is taking job requests.")})
    return queue


def submit_job(makerspace, member, data):
    from apps.machines import service_workflow
    from apps.machines.job_files import attach_job_file
    from apps.machines.job_rules import require_open_job_limit
    from apps.makerspaces.models import Makerspace
    queue = resolve_queue(makerspace, data["queue_id"])
    require_member_job_gate(makerspace, member, queue.machine_type)
    acknowledged = data.get("acknowledgements") or {}
    if not all(acknowledged.get(key) is True for key in ACKNOWLEDGEMENTS):
        raise ValidationError({"acknowledgements": gettext("Confirm the pickup, failure and ownership terms.")})
    file_ids = list(dict.fromkeys(data.get("file_ids") or ()))
    if not file_ids:
        raise ValidationError({"file_ids": gettext("Add at least one file for this job.")})
    payload = _payload(queue, data)
    with transaction.atomic():
        # Same lock order as `submit`: the makerspace first, so the limit count is stable.
        makerspace = Makerspace.objects.select_for_update(no_key=True).get(pk=makerspace.pk)
        require_member_job_gate(makerspace, member, queue.machine_type)
        require_open_job_limit(makerspace, member, queue.machine_type)
        if payload is not None and "requested_material" in payload:
            from apps.makerspaces import limits
            limits.check_quota(makerspace, "print", adding=1)
        row = service_workflow.submit(
            queue, member, member=member, actor=member, requester_name=member.display_name or "",
            contact_email=member.email or "", contact_phone=member.phone or "", title=data["title"],
            description=data.get("description", ""), source_link=data.get("source_link", ""),
            capability_payload=payload,
            certification_override_reason="",
        )
        row.copies, row.needed_by = data.get("copies") or 1, data.get("needed_by")
        row.own_material, row.material_note = bool(data.get("own_material")), data.get("material_note", "")[:200]
        row.member_estimate_minutes = data.get("member_estimate_minutes")
        row.save(update_fields=["copies", "needed_by", "own_material", "material_note", "member_estimate_minutes",
                                "updated_at"])
        for file_id in file_ids:
            attach_job_file(row, file_id=file_id, actor=member)
        if not row.files.exclude(kind="screenshot").exists():
            raise ValidationError({"file_ids": gettext("Add at least one design file, not only screenshots.")})
        return row


def _payload(queue, data):
    """Printers build the printer pack's payload from the form's material fields, exactly as
    the 3D-printer route always has; every other type sends its typed intake as is."""
    from apps.machines.printer_capabilities import is_printer_type
    if not is_printer_type(queue.machine_type):
        return data.get("capability_payload")
    from apps.machines.public_printer_service import _kernel_payload
    return _kernel_payload(queue, {
        "material": data.get("material", ""), "color": data.get("color", ""), "quantity": data.get("copies") or 1,
        "project_brief": data.get("description", ""), "consumable_pool_id": data.get("consumable_pool_id"),
        "estimated_filament_grams": data.get("estimated_filament_grams"),
        "preferred_settings": data.get("preferred_settings"),
    })
