from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.events.models_event import Event
from apps.hardware_requests.exceptions import ErrorSerializer
from .models import EventMemberPresentation
from .policy import require_owner_event
from .selection_workflow import options, project_owner, select
from .serializers import PresentationSerializer, PresentationWriteSerializer, ProfileOptionsSerializer

ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404, 409, 423, 429, 503)}


def private(response):
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def owner_event(request, makerspace_id, pk):
    event = get_object_or_404(Event.objects.select_related("makerspace"), pk=pk, makerspace_id=makerspace_id)
    require_owner_event(event, request.user)
    return event


class ProfileOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Event presentation"], responses={200: ProfileOptionsSerializer, **ERRORS})
    def get(self, request, makerspace_id, pk):
        return private(Response(options(owner_event(request, makerspace_id, pk), request.user)))


class PresentationView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Event presentation"], responses={200: PresentationSerializer, **ERRORS})
    def get(self, request, makerspace_id, pk):
        event = owner_event(request, makerspace_id, pk)
        result = project_owner(EventMemberPresentation.objects.filter(event=event, member=request.user).first())
        result["selected_profile"] = result.pop("profile_id")
        result["selected_membership"] = result.pop("membership_id")
        return private(Response(result))

    @extend_schema(tags=["Event presentation"], request=PresentationWriteSerializer,
                   responses={200: PresentationSerializer, **ERRORS})
    def patch(self, request, makerspace_id, pk):
        event = owner_event(request, makerspace_id, pk)
        serializer = PresentationWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return private(Response(select(event.pk, actor=request.user, **serializer.validated_data)))
