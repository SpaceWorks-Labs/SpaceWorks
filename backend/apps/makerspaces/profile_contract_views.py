"""Member-owned handle and timeline mutations; never accept a profile/user ID."""

from django.utils.translation import gettext
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from apps.hardware_requests.exceptions import ErrorSerializer
from drf_spectacular.utils import extend_schema
from apps.audit import services as audit
from .profile_views import MemberProfileBaseView, ERRORS
from .profile_services import profile_for
from .models_profiles import MemberProfile
from .public_profile_handles import claim_handle, release_handle
from .public_profile_validation import TimelineWriteSerializer


class HandleSerializer(serializers.Serializer):
    handle = serializers.CharField(max_length=30)


class HandleReadSerializer(serializers.Serializer):
    handle = serializers.CharField()
    claimed_at = serializers.DateTimeField()
    changed_at = serializers.DateTimeField()


class TimelinePageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = TimelineWriteSerializer(many=True)


class HandleView(MemberProfileBaseView):
    @extend_schema(tags=["Member profile"], request=HandleSerializer,
                   responses={200: HandleReadSerializer, 400: ErrorSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        membership = self.membership(request, makerspace_id)
        data = HandleSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        claim = claim_handle(membership, data.validated_data["handle"])
        return Response(HandleReadSerializer(claim).data)

    @extend_schema(tags=["Member profile"], request=None, responses={204: None, **ERRORS})
    def delete(self, request, makerspace_id):
        release_handle(self.membership(request, makerspace_id))
        return Response(status=204)


class TimelineListView(MemberProfileBaseView):
    @extend_schema(tags=["Member profile"], responses={200: TimelinePageSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        membership = self.membership(request, makerspace_id)
        profile = MemberProfile.objects.filter(membership=membership).first()
        paginator = PageNumberPagination()
        paginator.page_size = 24
        rows = paginator.paginate_queryset(profile.timeline.all() if profile else [], request, view=self)
        return paginator.get_paginated_response(TimelineWriteSerializer(rows, many=True).data)

    @extend_schema(tags=["Member profile"], request=TimelineWriteSerializer,
                   responses={201: TimelineWriteSerializer, 400: ErrorSerializer, **ERRORS})
    @transaction.atomic
    def post(self, request, makerspace_id):
        membership = self.membership(request, makerspace_id)
        from .models import MakerspaceMembership
        MakerspaceMembership.objects.select_for_update().get(pk=membership.pk)
        profile = profile_for(membership)
        profile = MemberProfile.objects.select_for_update().get(pk=profile.pk)
        if profile.timeline.count() >= 100:
            raise ValidationError({"timeline": gettext("At most 100 entries are allowed.")})
        data = TimelineWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        entry = data.save(profile=profile)
        audit.record(request.user, "member.profile_timeline_created", makerspace=membership.makerspace,
                     target=membership, meta={"fields": sorted(data.validated_data)})
        return Response(TimelineWriteSerializer(entry).data, status=201)


class TimelineDetailView(MemberProfileBaseView):
    def entry(self, request, makerspace_id, pk):
        membership = self.membership(request, makerspace_id)
        profile = get_object_or_404(MemberProfile.objects.select_for_update(), membership=membership)
        return membership, profile, get_object_or_404(profile.timeline, pk=pk)

    @extend_schema(tags=["Member profile"], responses={200: TimelineWriteSerializer, **ERRORS})
    @transaction.atomic
    def get(self, request, makerspace_id, pk):
        _, _, entry = self.entry(request, makerspace_id, pk)
        return Response(TimelineWriteSerializer(entry).data)

    @extend_schema(tags=["Member profile"], request=TimelineWriteSerializer,
                   responses={200: TimelineWriteSerializer, 400: ErrorSerializer, **ERRORS})
    @transaction.atomic
    def patch(self, request, makerspace_id, pk):
        membership, profile, entry = self.entry(request, makerspace_id, pk)
        data = TimelineWriteSerializer(entry, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        data.save()
        audit.record(request.user, "member.profile_timeline_updated", makerspace=membership.makerspace,
                     target=membership, meta={"fields": sorted(data.validated_data)})
        return Response(data.data)

    @extend_schema(tags=["Member profile"], request=None, responses={204: None, **ERRORS})
    @transaction.atomic
    def delete(self, request, makerspace_id, pk):
        membership, profile, entry = self.entry(request, makerspace_id, pk)
        entry.delete()
        audit.record(request.user, "member.profile_timeline_deleted", makerspace=membership.makerspace,
                     target=membership, meta={})
        return Response(status=204)
