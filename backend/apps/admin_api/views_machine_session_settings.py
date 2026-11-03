"""Per-machine-type session settings (lane L23, #158.5): the maximum session length.

Written through the settings-authority layer (`machines` / `sessions.max_minutes`), like
the other per-type machine settings. 404 while `machines.sessions` is off.
"""

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.views_machine_sessions import ERRORS, _space
from apps.machines.job_policy import policy_for
from apps.machines.models import MachineType
from apps.machines.serializers_sessions import SessionSettingsSerializer

SETTING_KEY = "sessions.max_minutes"


class MachineTypeSessionSettingsView(APIView):
    permission_classes = [IsActiveStaff]

    def resolve(self, request, makerspace_id, type_id):
        space = _space(request.user, makerspace_id)
        machine_type = get_object_or_404(
            MachineType.objects.filter(Q(makerspace__isnull=True) | Q(makerspace=space)), pk=type_id)
        return space, machine_type, policy_for(space, machine_type)

    @extend_schema(tags=["Admin machine sessions"], summary="Session settings for one machine type",
                   responses={200: SessionSettingsSerializer, **ERRORS})
    def get(self, request, makerspace_id, type_id):
        _space_row, _type, policy = self.resolve(request, makerspace_id, type_id)
        return Response(SessionSettingsSerializer({"session_max_minutes": policy.session_max_minutes}).data)

    @extend_schema(tags=["Admin machine sessions"], summary="Change the maximum session length for one machine type",
                   description="Sessions still live stop at the new maximum on the next sweep.",
                   request=SessionSettingsSerializer, responses={200: SessionSettingsSerializer, **ERRORS})
    @transaction.atomic
    def put(self, request, makerspace_id, type_id):
        from apps.audit import services as audit
        from apps.makerspaces.settings_authority import assert_setting_write, record_change
        space, machine_type, policy = self.resolve(request, makerspace_id, type_id)
        payload = SessionSettingsSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        value, before = payload.validated_data["session_max_minutes"], policy.session_max_minutes
        if value != before:
            decision = assert_setting_write(request.user, space, "machines", SETTING_KEY)
            policy.session_max_minutes = value
            if policy.pk:
                policy.save(update_fields=["session_max_minutes"])
            else:
                policy.save()
            record_change(request.user, space, "machines", SETTING_KEY, before, value, decision)
            audit.record(request.user, "machine_type.session_settings_updated", makerspace=space, target=policy,
                         meta={"machine_type_id": machine_type.pk, "session_max_minutes": value})
        return Response(SessionSettingsSerializer({"session_max_minutes": value}).data)
