"""Full-manager-only configuration; review permission never grants it."""
from django.utils.translation import gettext
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from apps.events import event_authority
from . import admission_config
from .admission_models import HackathonConfig
from .admission_ports import ports
from .api_base import AdminView, ProgrammeCommandThrottle
from .api_schema import ERRORS
from .api_schema_staff import ConfigSerializer
from .serializers_config import ConfigInput


class ConfigView(AdminView):
    permission = None
    throttle_classes = [ProgrammeCommandThrottle]

    @extend_schema(tags=["Event programme"], request=None, responses={200: ConfigSerializer, **ERRORS})
    def get(self, request, pk):
        event = event_authority.get_event(request.user, pk, None)
        from .admission_feature import admission_enabled
        from .admission_errors import fail
        if not admission_enabled(event.makerspace):
            fail("not_found", gettext("Not found."), status=404)
        config = HackathonConfig.objects.filter(event=event).first()
        if not config:
            return Response({"id": None, "event_id": event.pk, "version": 0, "state": "disabled", "enabled": False, "allowed_actions": ["edit"],
                                 "attendance_required": ports().default_attendance_required(event=event)})
        return Response(admission_config.project(config))

    @extend_schema(tags=["Event programme"], request=ConfigInput, responses={200: ConfigSerializer, **ERRORS})
    def patch(self, request, pk):
        event_authority.get_event(request.user, pk, None)
        row = admission_config.update(event_id=pk, actor=request.user, data=self.command_data(request, ConfigInput))
        return Response(admission_config.project(row))
