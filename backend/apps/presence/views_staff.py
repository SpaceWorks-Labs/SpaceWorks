from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.makerspaces.servability import servable_queryset
from .display import present_rows
from .policy import require_staff
from .privacy import settings_for, update_settings
from .serializers import (
    PresenceCurrentSerializer, PresencePrivacySerializer, PresenceRosterPageSerializer, PresenceRosterSerializer,
    PresenceSessionSerializer, StaffPresenceEndSerializer, StaffPresenceStartSerializer,
)
from .services import end_session, staff_check_in
from .schema import ERRORS


def staff_space(request, makerspace_id, *, settings=False):
    action = rbac.Action.MANAGE_MAKERSPACE if settings else rbac.Action.MANAGE_MEMBERS
    space = get_object_or_404(rbac.scope_by_action(request.user, action, servable_queryset(), field="id"), pk=makerspace_id)
    require_staff(request.user, space, settings=settings)
    return space


def scoped_account(space, account_id, *, present=False):
    """Resolve only accounts this makerspace already knows, never any deployment account.

    Check-in needs a roster row here (member or this space's walk-in); check-out also
    accepts an account-only guest with presence here. Anything else is the same 404,
    so a numeric id cannot probe or project another tenant's people.
    """
    known = Q(makerspace_memberships__makerspace=space)
    if present:
        known |= Q(presence_sessions__makerspace=space)
    return get_object_or_404(get_user_model().objects.filter(known).distinct(), pk=account_id)


class StaffPresenceView(APIView):
    permission_classes = [IsActiveStaff]


class PresenceRosterView(StaffPresenceView):
    @extend_schema(tags=["Presence staff"], description="Requires manage_members in this makerspace.",
                   responses={200: PresenceRosterPageSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        space = staff_space(request, makerspace_id)
        rows = rbac.scope_by_action(request.user, rbac.Action.MANAGE_MEMBERS, present_rows(space))
        page = PageNumberPagination()
        return page.get_paginated_response(PresenceRosterSerializer(page.paginate_queryset(rows, request), many=True).data)


class StaffPresenceStartView(StaffPresenceView):
    @extend_schema(tags=["Presence staff"], request=StaffPresenceStartSerializer, responses={201: PresenceSessionSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        space = staff_space(request, makerspace_id)
        serializer = StaffPresenceStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        account = scoped_account(space, values.pop("account_id"))
        row = staff_check_in(request.user, account, space, **values)
        return Response(PresenceSessionSerializer(row).data, status=201)


class StaffPresenceEndView(StaffPresenceView):
    @extend_schema(tags=["Presence staff"], request=StaffPresenceEndSerializer, responses={200: PresenceCurrentSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        space = staff_space(request, makerspace_id)
        serializer = StaffPresenceEndSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = scoped_account(space, serializer.validated_data["account_id"], present=True)
        end_session(account, space, actor=request.user)
        return Response({"active": False, "session": None})


class PresencePrivacyView(StaffPresenceView):
    @extend_schema(tags=["Presence staff"], responses={200: PresencePrivacySerializer, **ERRORS})
    def get(self, request, makerspace_id):
        return Response(PresencePrivacySerializer(settings_for(staff_space(request, makerspace_id, settings=True))).data)

    @extend_schema(tags=["Presence staff"], request=PresencePrivacySerializer, responses={200: PresencePrivacySerializer, **ERRORS})
    def patch(self, request, makerspace_id):
        space = staff_space(request, makerspace_id, settings=True)
        serializer = PresencePrivacySerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(PresencePrivacySerializer(update_settings(request.user, space, serializer.validated_data)).data)
