"""Privacy-safe people picker for the instructor of an open supervised session (0.12.0, UI lane U2).

Search is bounded to people currently checked in at the space (live presence) or registered for the
session's linked event, needs two characters and returns only `{id, display_name}`. It is never a
space-wide member directory: an empty pool or a one-letter query yields nothing.
"""
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from apps.accounts.models import User
from apps.openapi_errors import errors

from . import supervised
from .serializers_workshop import _name
from .views_supervised import TAGS, _Base, _session, supervisee_pool
from django.utils.translation import gettext

MIN_QUERY = 2
MAX_RESULTS = 20


class SupervisedPersonSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    display_name = serializers.CharField()


class SupervisedPersonListSerializer(serializers.Serializer):
    results = SupervisedPersonSerializer(many=True)


class SupervisedPeoplePickerView(_Base):
    throttle_scope = "member_card_resolve"

    @extend_schema(tags=TAGS, summary="Find a supervisee among people checked in or registered for the event",
                   request=None, parameters=[OpenApiParameter("q", str, required=True,
                                                              description="At least two characters.")],
                   responses={200: SupervisedPersonListSerializer, **errors(400, 401, 404, 429)})
    def get(self, request, pk):
        session = _session(request, pk)
        if session.instructor_id != request.user.pk or session.closed_at is not None:
            raise NotFound()
        query = (request.query_params.get("q") or "").strip()
        if len(query) < MIN_QUERY:
            raise ValidationError({"q": gettext("Type at least two characters.")})
        # One pool with the join check (`supervisee_pool`), so Events off adds no registrants (218).
        pool = supervisee_pool(session)
        match = (Q(display_name__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query))
        rows = (User.objects.filter(pool, match, is_active=True, access_status="active")
                .exclude(pk=session.instructor_id)
                .exclude(pk__in=session.participants.filter(removed_at__isnull=True).values("user_id"))
                .order_by("display_name", "pk")[:MAX_RESULTS])
        return Response({"results": [{"id": u.pk, "display_name": _name(u)} for u in rows]})
