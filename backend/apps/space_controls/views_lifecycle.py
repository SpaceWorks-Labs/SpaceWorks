"""Archive now / unarchive / purge from the web console (#190: /control/ is a fallback).

Each calls the existing single lifecycle source (``apps.makerspaces.lifecycle``), so the
archival-money impact audit, the two-key request auto-approval, the migrated-out handoff
refusal and the purge graph are exactly the /control/ ones. Purge additionally needs the
space's slug typed back, as the /control/ purge confirmation does.
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.makerspaces.models import Makerspace

from . import serializers as s
from .errors import SpaceControlConflict
from .models import SpaceControlState
from .services_schedule import is_archived
from .views_controls import CONTROL_ERRORS, TAGS, _ControlView
from .write_policy import control_context


def _conflict(exc):
    return SpaceControlConflict("lifecycle_refused", " ".join(exc.messages))


class ArchiveNowView(_ControlView):
    def run(self, actor, pk, data):
        from apps.makerspaces import lifecycle

        space = Makerspace.objects.get(pk=pk)
        try:
            with control_context():
                lifecycle.archive(space, actor)
        except DjangoValidationError as exc:
            raise SpaceControlConflict("space_not_active", " ".join(exc.messages)) from exc

    @extend_schema(tags=TAGS, summary="Archive a space now", request=s.EmptySerializer,
                   responses={200: s.HealthCardSerializer, **CONTROL_ERRORS})
    def post(self, request, makerspace_id):
        return self.control(request, makerspace_id)


class UnarchiveView(_ControlView):
    def run(self, actor, pk, data):
        from apps.makerspaces import lifecycle

        space = Makerspace.objects.get(pk=pk)
        if not is_archived(space):
            raise SpaceControlConflict("space_not_archived", "This space is not archived.")
        with transaction.atomic(), control_context():
            try:
                lifecycle.unarchive(space, actor)
            except DjangoValidationError as exc:
                raise _conflict(exc) from exc
            # A purge scheduled for the archived space no longer applies.
            SpaceControlState.objects.filter(makerspace=space).update(
                purge_due_at=None, archive_on=None, scheduled_at=None, scheduled_by=None,
                schedule_note="", reminders_sent=[])

    @extend_schema(tags=TAGS, summary="Unarchive a space", request=s.EmptySerializer,
                   responses={200: s.HealthCardSerializer, **CONTROL_ERRORS})
    def post(self, request, makerspace_id):
        return self.control(request, makerspace_id)


class PurgeView(_ControlView):
    request_serializer = s.PurgeRequestSerializer

    def run(self, actor, pk, data):
        from apps.makerspaces import lifecycle

        space = Makerspace.objects.get(pk=pk)
        if data["confirm_slug"] != space.slug:
            raise ValidationError({"confirm_slug": "Type the space's slug exactly to confirm.", "code": "slug_mismatch"})
        if not is_archived(space):
            raise SpaceControlConflict("space_not_archived", "Only an archived space can be purged.")
        try:
            with control_context():
                lifecycle.purge(space, actor)
        except DjangoValidationError as exc:
            raise _conflict(exc) from exc

    @extend_schema(tags=TAGS, summary="Permanently delete (purge) an archived space", request=s.PurgeRequestSerializer,
                   responses={204: OpenApiResponse(description="Purged."), **CONTROL_ERRORS})
    def post(self, request, makerspace_id):
        get_object_or_404(Makerspace, pk=makerspace_id)
        body = s.PurgeRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            self.run(request.user, makerspace_id, body.validated_data)
        except DjangoValidationError as exc:
            raise _conflict(exc) from exc
        return Response(status=status.HTTP_204_NO_CONTENT)

