"""Inbox snooze and archive (X38, `notifications.inbox_snooze`). 404 while the switch is off.

Snoozed rows leave the list and the unread count until `snoozed_until`; archived rows
leave them until restored. Switching the feature off keeps both columns and simply
shows every row again (no data loss). Each change is audited without the message text.
"""

from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.audit import services as audit
from apps.makerspaces.platform import feature_enabled
from apps.tenant_migration.gate_runtime import tenant_write

from .serializers_inbox import InboxSerializer
from .views_inbox import WRITE_ERRORS, InboxBase

FEATURE = "notifications.inbox_snooze"
MAX_SNOOZE = timedelta(days=30)


class SnoozeSerializer(serializers.Serializer):
    until = serializers.DateTimeField(help_text="Show the message again at this time (at most 30 days ahead).")

    def validate_until(self, value):
        now = timezone.now()
        if not now < value <= now + MAX_SNOOZE:
            raise serializers.ValidationError("Choose a time in the next 30 days.")
        return value


def visible(rows, space, now=None):
    """The list/unread filter: hide snoozed and archived rows while the switch is on."""
    if not feature_enabled(space, FEATURE):
        return rows
    from django.db.models import Q
    now = now or timezone.now()
    return rows.filter(archived_at__isnull=True).filter(Q(snoozed_until__isnull=True) | Q(snoozed_until__lte=now))


class _InboxRowAction(InboxBase):
    action = ""

    def change(self, request, makerspace_id, pk, **values):
        space, rows = self.rows(request, makerspace_id)
        if not feature_enabled(space, FEATURE):
            raise NotFound()
        with tenant_write(space.pk):
            row = get_object_or_404(rows.select_for_update(), pk=pk)
            for field, value in values.items():
                setattr(row, field, value)
            row.save(update_fields=list(values))
            audit.record(request.user, f"notification.inbox_{self.action}", makerspace=space, target=space,
                         meta={"row_id": row.pk})
        return Response(InboxSerializer(row).data)


class InboxSnoozeView(_InboxRowAction):
    action = "snoozed"

    @extend_schema(tags=["Personal notifications"], request=SnoozeSerializer,
                   responses={200: InboxSerializer, **WRITE_ERRORS})
    def post(self, request, makerspace_id, pk):
        payload = SnoozeSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        return self.change(request, makerspace_id, pk, snoozed_until=payload.validated_data["until"])


class InboxArchiveView(_InboxRowAction):
    action = "archived"

    @extend_schema(tags=["Personal notifications"], request=None, responses={200: InboxSerializer, **WRITE_ERRORS})
    def post(self, request, makerspace_id, pk):
        return self.change(request, makerspace_id, pk, archived_at=timezone.now())


class InboxRestoreView(_InboxRowAction):
    action = "restored"

    @extend_schema(tags=["Personal notifications"], request=None, responses={200: InboxSerializer, **WRITE_ERRORS},
                   description="Bring an archived or snoozed message back to the list now.")
    def post(self, request, makerspace_id, pk):
        return self.change(request, makerspace_id, pk, archived_at=None, snoozed_until=None)
