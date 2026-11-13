"""Adapter events through the notification catalogue (feature ``devices``): translated, preferences respected.

Fan-out goes through the shared ``operations.notifications_p2.fanout`` (durable outbox, per-recipient language, the
Phase-1a preference resolver) and is deferred to Celery by ``safe_notification``. The source row of each notice is an
immutable record: the ``AdapterEvent`` (needs attention, material runout, session ending) or the ``AdapterAccessLog``
(access denied, staff only, rate-limited per binding and reason). Job started/finished/failed come for free from the
machine-service workflow every adapter job reports through; offline/recovered are the device state edges
(``notifications_p2.py``); maintenance due is the maintenance schedule's own notice.
"""
import uuid

from django.core.cache import cache
from django.db import IntegrityError
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.integrations.notification_sources import NotificationSource, register_source
from apps.makerspaces.platform import module_enabled
from apps.operations.notifications_p2 import body, fanout, revision, safe_notification, scoped, staff_link
from .models import AdapterAccessLog, AdapterEvent, Device

EVENT_SOURCE = "devices.adapter_event"
ACCESS_SOURCE = "devices.adapter_access"
DENIED_WINDOW = 600
EVENTS = {"job.needs_attention": "adapter_attention", "consumable.runout": "adapter_runout",
          "detection.reported": "adapter_detection"}
DETECTION_WINDOW = 300


def _load(envelope):
    model = AdapterAccessLog if envelope.source_kind == ACCESS_SOURCE else AdapterEvent
    stamp = "created_at" if model is AdapterAccessLog else "received_at"
    row = scoped(model, envelope.makerspace_id).select_related("device", "makerspace").filter(
        pk=envelope.source_id).first()
    return row, stamp


def eligible(envelope):
    row, stamp = _load(envelope)
    return bool(row and row.device.status == Device.Status.ACTIVE and module_enabled(row.makerspace, "devices")
                and envelope.revision == revision(row.pk, getattr(row, stamp)))


def _name(binding, device):
    return binding.machine.name if binding is not None and binding.machine_id else device.name


def _subject(event):
    return {"adapter_attention": _("Machine needs attention"), "adapter_runout": _("Material has run out"), "adapter_detection": _("Detection at a machine"),
            "adapter_session_ending": _("Your machine session ends soon"),
            "adapter_access_denied": _("Access denied at a device"),
            "adapter_job_review": _("A job report is waiting for review")}[event]


def _send(row, event, kind, stamp, staff_text, owner=None, owner_text=None):
    space = row.makerspace
    link = staff_link(space, "devices")
    from apps.integrations.notification_links import local_link
    return fanout(
        row=row, space=space, feature="devices", stream="devices", event=event, source_kind=kind,
        revision=revision(row.pk, stamp), staff=staff_text is not None, rooms=staff_text is not None,
        staff_body=(lambda: body(_subject(event), staff_text, link)) if staff_text else None,
        owner=owner,
        owner_body=(lambda: body(_subject(event), owner_text, local_link(space, "member"))) if owner_text else None,
        context={"device_id": str(row.device_id)})


@safe_notification
def notify_event(row):
    event = EVENTS[row.event_type]
    name = _name(row.binding, row.device)
    if event == "adapter_detection":
        return _notify_detection(row, name)
    if event == "adapter_attention":
        text = _("%(name)s reported that it needs attention: %(reason)s.") % {
            "name": name, "reason": row.data.get("reason", "")}
    else:
        text = _("%(name)s ran out of a consumable and needs a refill.") % {"name": name}
    return _send(row, event, EVENT_SOURCE, row.received_at, text)


def _job_owner(binding):
    """The member whose in-progress request runs on this binding's machine, else None."""
    if binding is None or not binding.machine_id:
        return None
    from apps.machines.models import MachineServiceRequest
    request = MachineServiceRequest.objects.select_related("member", "requester").filter(
        assigned_machine_id=binding.machine_id, status=MachineServiceRequest.Status.IN_PROGRESS).first()
    return (request.member or request.requester) if request else None


def _notify_detection(row, name):
    """Staff and the job owner learn of a detection once per binding and kind per five minutes. Never acts."""
    kind = row.data.get("kind", "other")
    if not cache.add(f"adapter-detect-notify:{row.binding_id}:{kind}", 1, DETECTION_WINDOW):
        return None
    pct = int(round(float(row.data.get("confidence", 0)) * 100))
    staff_text = _("%(name)s: %(kind)s detected (%(pct)s%% confidence).") % {"name": name, "kind": kind, "pct": pct}
    owner = _job_owner(row.binding)
    return _send(row, "adapter_detection", EVENT_SOURCE, row.received_at, staff_text, owner=owner,
                 owner_text=staff_text if owner else None)


@safe_notification
def notify_access_denied(row):
    text = _("Access was denied at %(name)s (%(reason)s).") % {
        "name": _name(row.binding, row.device), "reason": row.reason}
    return _send(row, "adapter_access_denied", ACCESS_SOURCE, row.created_at, text)


@safe_notification
def _send_owner(row, session, text):
    return _send(row, "adapter_session_ending", EVENT_SOURCE, row.received_at, None,
                 owner=session.member, owner_text=text)


def on_event(row):
    if row.event_type in EVENTS:
        notify_event(row)


def on_access(row):
    """Staff learn of a denial once per binding and reason per ten minutes (never a flood from a held-down tag)."""
    if row.allowed or row.reason in ("unknown_credential", "credential_locked", "pin_required"):
        return
    if cache.add(f"adapter-denied:{row.binding_id}:{row.reason}", 1, DENIED_WINDOW):
        notify_access_denied(row)


def notify_session_ending(binding, session, minutes):
    """One notice per session (the event row's operation id is derived from the session, so a repeat is a no-op)."""
    now = timezone.now()
    try:
        row = AdapterEvent.objects.create(
            makerspace_id=binding.makerspace_id, device=binding.device, binding=binding,
            operation_id=uuid.uuid5(uuid.NAMESPACE_URL, f"adapter-session-ending:{session.pk}"),
            event_type="session.ending_soon", capability="safety", observed_at=now, received_at=now,
            data={"session_id": session.pk, "minutes": minutes})
    except IntegrityError:
        return False
    if session.member_id is None:
        return False
    _send_owner(row, session, _("Your session on %(name)s ends in about %(minutes)s minutes.") % {
        "name": session.machine.name, "minutes": minutes})
    return True


JOB_REVIEW = "job.review_needed"  # a server-side row, like `session.ending_soon`; adapters cannot send this type


@safe_notification
def _send_review(row, text):
    return _send(row, "adapter_job_review", EVENT_SOURCE, row.received_at, text)


def notify_job_review(job, outcome):
    """NCA audit 0.12.0 (decision 312c): a terminal job report an adapter sent is held for staff review (auto-apply
    off, or any failed report). Staff are told once per job; the member hears the outcome when staff apply it."""
    from django.db import transaction
    from .models import AdapterBinding
    if AdapterEvent.objects.filter(device_id=job.device_id, event_type=JOB_REVIEW, data__job_id=str(job.pk)).exists():
        return False
    now = timezone.now()
    binding = AdapterBinding.objects.filter(device_id=job.device_id, machine_id=job.machine_id).first()         if job.machine_id else None
    try:
        with transaction.atomic():
            row = AdapterEvent.objects.create(
                makerspace_id=job.makerspace_id, device_id=job.device_id, binding=binding, operation_id=uuid.uuid4(),
                event_type=JOB_REVIEW, capability="job.dispatch", observed_at=now, received_at=now,
                data={"job_id": str(job.pk), "outcome": outcome})
    except IntegrityError:
        return False
    name = job.machine_name or _name(binding, row.device)
    text = (_("%(name)s reported a failed job. Review the report in Devices before the member is told.")
            if outcome == "failed" else
            _("%(name)s reported a finished job. Review the report in Devices before the member is told."))
    _send_review(row, text % {"name": name})
    return True


def register():
    register_source(EVENT_SOURCE, NotificationSource(eligible))
    register_source(ACCESS_SOURCE, NotificationSource(eligible))
