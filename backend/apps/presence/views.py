from drf_spectacular.utils import extend_schema
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.apiclients.throttling import MemberPrincipalRateThrottle
from apps.makerspaces.lookup import get_public_makerspace
from apps.makerspaces.models import MemberProject
from . import services
from .models import PresencePreference
from .policy import presets, require_account, require_enabled
from .privacy import update_preference
from .serializers import (
    PresenceCurrentSerializer, PresencePreferenceSerializer, PresenceProjectPageSerializer,
    PresenceProjectSerializer, PresenceRenewSerializer, PresenceSessionSerializer, PresenceStartSerializer,
)

from .schema import ERRORS


def public_space(request, slug):
    from .views_public import check_origin
    space = get_public_makerspace(slug)
    require_enabled(space)
    check_origin(request, space)
    return space


class MemberPresenceView(APIView):
    permission_classes = [IsAuthenticated]


class PresenceStartView(MemberPresenceView):
    throttle_classes = [MemberPrincipalRateThrottle]
    throttle_scope = "presence_start"
    @extend_schema(tags=["Presence"], request=PresenceStartSerializer, responses={201: PresenceSessionSerializer, **ERRORS})
    def post(self, request, makerspace_slug):
        space = public_space(request, makerspace_slug)
        serializer = PresenceStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = services.start_session(request.user, space, **serializer.validated_data)
        return Response(PresenceSessionSerializer(session).data, status=201)


class PresenceCurrentView(MemberPresenceView):
    @extend_schema(tags=["Presence"], request=None, responses={200: PresenceCurrentSerializer, **ERRORS})
    def get(self, request, makerspace_slug):
        space = public_space(request, makerspace_slug)
        session = services.current_session(request.user, space)
        return Response(PresenceCurrentSerializer({"active": bool(session), "session": session, "presets": presets(space)}).data)


class PresenceEndView(MemberPresenceView):
    @extend_schema(tags=["Presence"], request=None, responses={200: PresenceCurrentSerializer, **ERRORS})
    def post(self, request, makerspace_slug):
        space = public_space(request, makerspace_slug)
        services.end_session(request.user, space)
        return Response({"active": False, "session": None})


class PresenceRenewView(MemberPresenceView):
    throttle_classes = [MemberPrincipalRateThrottle]
    throttle_scope = "presence_start"
    @extend_schema(tags=["Presence"], request=PresenceRenewSerializer, responses={200: PresenceSessionSerializer, **ERRORS})
    def post(self, request, makerspace_slug):
        space = public_space(request, makerspace_slug)
        serializer = PresenceRenewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = services.renew_session(request.user, space, **serializer.validated_data)
        return Response(PresenceSessionSerializer(row).data)


class PresenceProjectsView(MemberPresenceView):
    @extend_schema(tags=["Presence"], request=None, responses={200: PresenceProjectPageSerializer, **ERRORS})
    def get(self, request, makerspace_slug):
        space = public_space(request, makerspace_slug)
        require_account(request.user, space)
        rows = MemberProject.objects.filter(profile__membership__user=request.user,
                                            profile__membership__makerspace=space).order_by("position", "pk")
        page = PageNumberPagination()
        return page.get_paginated_response(PresenceProjectSerializer(page.paginate_queryset(rows, request), many=True).data)


class PresencePreferenceView(MemberPresenceView):
    @extend_schema(tags=["Presence"], responses={200: PresencePreferenceSerializer, **ERRORS})
    def get(self, request, makerspace_slug):
        space = public_space(request, makerspace_slug)
        require_account(request.user, space)
        row = PresencePreference.objects.filter(makerspace=space, account=request.user).first()
        return Response({"hide_on_display": bool(row and row.hide_on_display)})

    @extend_schema(tags=["Presence"], request=PresencePreferenceSerializer, responses={200: PresencePreferenceSerializer, **ERRORS})
    def patch(self, request, makerspace_slug):
        space = public_space(request, makerspace_slug)
        serializer = PresencePreferenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = update_preference(request.user, space, **serializer.validated_data)
        return Response(PresencePreferenceSerializer(row).data)


# Preserve the existing import used by presence.urls_admin.
from .views_staff import PresenceRosterView  # noqa: E402,F401
