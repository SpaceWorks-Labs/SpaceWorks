"""Live guest-pass holders for the staff check-in search (0.12.0, UI lane U1).

Same authority as starting a presence session (`staff_space`), minimal fields, and bounded to
people holding a live pass at this space: it is not a roster and never lists members.
"""
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.staff_identity import person_q
from apps.makerspaces.guest_pass_queries import active_pass_for
from apps.makerspaces.models import GuestPass

from .schema import ERRORS
from .views_staff import StaffPresenceView, staff_space

MAX_RESULTS = 20


class CheckInGuestSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    display_name = serializers.CharField()
    pass_valid_until = serializers.DateTimeField()
    waiver_on_file = serializers.BooleanField()


class CheckInGuestListSerializer(serializers.Serializer):
    results = CheckInGuestSerializer(many=True)


class StaffCheckInGuestSearchView(StaffPresenceView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "member_card_resolve"  # m17: people lookups share the card-resolve budget
    @extend_schema(tags=["Presence staff"], summary="Search live guest-pass holders to check in",
                   description="Requires the same authority as starting a presence session.",
                   parameters=[OpenApiParameter("q", str, required=True, description="At least two characters.")],
                   responses={200: CheckInGuestListSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        space = staff_space(request, makerspace_id)
        query = (request.query_params.get("q") or "").strip()
        if len(query) < 2:
            raise ValidationError({"q": "Type at least two characters."})
        now = timezone.now()
        rows = (GuestPass.objects.filter(
            Q(holder__display_name__icontains=query) | Q(holder__first_name__icontains=query)
            | Q(holder__last_name__icontains=query),
            person_q("holder__"), makerspace=space, status__in=GuestPass.LIVE_STATUSES,
            valid_from__lte=now, valid_until__gt=now).select_related("holder", "product")
            .order_by("holder__display_name", "holder_id"))
        seen, results = set(), []
        for row in rows:
            if row.holder_id in seen:
                continue
            live = active_pass_for(row.holder, space, now)
            if live is None:
                continue
            seen.add(row.holder_id)
            user = row.holder
            results.append({"id": user.pk, "display_name": user.display_name or user.get_full_name() or user.username,
                            "pass_valid_until": live.valid_until, "waiver_on_file": live.accepted_waiver_id is not None})
            if len(results) >= MAX_RESULTS:
                break
        return Response({"results": results})
