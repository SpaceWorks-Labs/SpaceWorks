"""The live authority projection shared by event and recurring-series responses."""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from . import event_authority
from .event_permissions import PERMISSIONS
from .event_authority_page import authority_for_page


def event_list_context(request, rows):
    return {"request": request, "event_authority": authority_for_page(request.user, rows)}


class EventAuthorityFields(serializers.Serializer):
    staff_permissions = serializers.SerializerMethodField()
    can_manage_staff = serializers.SerializerMethodField()

    def _authority(self, obj):
        actor = getattr(self.context.get("request"), "user", None)
        key = (obj._meta.label, obj.pk)
        cache = self.context.setdefault("event_authority", {})
        if key not in cache:
            manager = bool(actor and event_authority.can_manage_grants(actor, obj))
            permissions = list(PERMISSIONS) if manager else event_authority.permissions_for(actor, obj)
            cache[key] = (manager, permissions)
        return cache[key]

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_staff_permissions(self, obj):
        return self._authority(obj)[1]

    @extend_schema_field(serializers.BooleanField())
    def get_can_manage_staff(self, obj):
        return self._authority(obj)[0]
