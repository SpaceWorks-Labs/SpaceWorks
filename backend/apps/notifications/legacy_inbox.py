"""Snapshot legacy-only staff alerts without changing the shared feed contract."""

from uuid import NAMESPACE_URL, uuid4, uuid5

from apps.accounts import rbac
from apps.accounts.models import User
from apps.makerspaces.models import MakerspaceMembership
from apps.notifications.inbox import safe_link, _hint
from apps.notifications.models_inbox import NotificationInboxRow
from apps.notifications.preferences import personal_enabled
from apps.tenant_migration.gate_runtime import tenant_write
from django.db import transaction


def mirror_legacy_staff(makerspace, payload, *, source_intent=""):
    event = payload["event"]
    from apps.integrations.notification_catalog import is_notification_enabled
    from apps.notifications.views import _makerspace_for_manager
    from rest_framework.exceptions import PermissionDenied

    family = ("printing" if event.startswith("machine_service.") else "stock" if event.startswith("stocktake.")
              else "api_access" if event == "email.failed" else "hardware_requests")
    matrix_enabled = is_notification_enabled(makerspace, family, "in_app")
    # Direct hardware/printing alerts predate the opt-in matrix channel. Mirror them
    # unless the matrix already owns this edge, preventing both loss and duplication.
    if matrix_enabled and (event == "request.submitted" or event.startswith("machine_service.")):
        return
    if family not in {"hardware_requests", "printing"} and not matrix_enabled:
        return
    memberships = rbac.scope_for_scheduled_work(MakerspaceMembership.objects.filter(
        makerspace=makerspace, status="active", receives_notifications=True, user__is_active=True,
        user__access_status=User.AccessStatus.ACTIVE, user__is_tenant_dump_stub=False,
    )).select_related("user")
    event_key = uuid4()
    with tenant_write(makerspace.pk):
        for membership in memberships:
            user = membership.user
            try:
                # Preserve exactly the old visibility floor, including machine-only denial.
                _makerspace_for_manager(user, makerspace.pk)
            except PermissionDenied:
                continue
            if not personal_enabled(makerspace, user.pk, family, "in_app", event=event):
                continue
            key = (uuid5(NAMESPACE_URL, f"p2:{source_intent}:u:{user.pk}")
                   if source_intent and (event.startswith("stocktake.") or event == "email.failed") else event_key)
            _, created = NotificationInboxRow.objects.get_or_create(makerspace=makerspace, user=user, event_key=key,
                defaults={"feature": family, "event": event[:64], "title": payload["title"],
                          "summary": payload["body"][:12000], "link": safe_link(payload["url_path"])})
            if created:
                transaction.on_commit(lambda uid=user.pk: _hint(makerspace.pk, uid), robust=True)
