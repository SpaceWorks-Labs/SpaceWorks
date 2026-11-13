"""Timeline, self-reported achievements and own-submission import of the global profile.

Same rules for each: the profile is always the caller's own (never an id in the body), every write
is locked, capped and audited, and audit metadata names the fields touched, never their content.
"""

from datetime import date
from urllib.parse import urlsplit

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apps.audit import services as audit
from apps.hardware_requests.exceptions import ErrorSerializer

from .account_profile import account_profile_for
from .account_profile_serializers import TimelineSerializer
from .account_profile_views import ERRORS, AccountOwnerView
from .models_account_profile import AccountProfile, ProfileAchievement

MAX_TIMELINE = 100
MAX_ACHIEVEMENTS = 30


def locked_profile(user):
    """The caller's profile row under a lock, created on demand (writes only)."""
    return AccountProfile.objects.select_for_update().get(pk=account_profile_for(user).pk)


def existing_profile(user, *, lock=False):
    """The caller's profile if it exists, else 404. Reads and by-id writes must never create a row."""
    rows = AccountProfile.objects.select_for_update() if lock else AccountProfile.objects
    return get_object_or_404(rows, user=user)


class TimelinePageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = TimelineSerializer(many=True)


class TimelineListView(AccountOwnerView):
    @extend_schema(tags=["Member profile"], responses={200: TimelinePageSerializer, **ERRORS})
    def get(self, request, **kwargs):
        user = self.actor(request, **kwargs)
        paginator = PageNumberPagination()
        paginator.page_size = 24
        profile = AccountProfile.objects.filter(user=user).first()
        rows = paginator.paginate_queryset(profile.timeline.all() if profile else [], request, view=self)
        return paginator.get_paginated_response(TimelineSerializer(rows, many=True).data)

    @extend_schema(tags=["Member profile"], request=TimelineSerializer,
                   responses={201: TimelineSerializer, 400: ErrorSerializer, **ERRORS})
    @transaction.atomic
    def post(self, request, **kwargs):
        user = self.actor(request, **kwargs)
        profile = locked_profile(user)
        if profile.timeline.count() >= MAX_TIMELINE:
            raise ValidationError({"timeline": gettext("At most 100 entries are allowed.")})
        data = TimelineSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        entry = data.save(profile=profile)
        audit.record(user, "member.profile_timeline_created", makerspace=self.audit_space, target=user,
                     meta={"fields": sorted(data.validated_data)})
        return Response(TimelineSerializer(entry).data, status=201)


class TimelineDetailView(AccountOwnerView):
    def entry(self, request, pk, **kwargs):
        user = self.actor(request, **kwargs)
        return user, get_object_or_404(existing_profile(user, lock=True).timeline, pk=pk)

    @extend_schema(tags=["Member profile"], responses={200: TimelineSerializer, **ERRORS})
    @transaction.atomic
    def get(self, request, pk, **kwargs):
        return Response(TimelineSerializer(self.entry(request, pk, **kwargs)[1]).data)

    @extend_schema(tags=["Member profile"], request=TimelineSerializer,
                   responses={200: TimelineSerializer, 400: ErrorSerializer, **ERRORS})
    @transaction.atomic
    def patch(self, request, pk, **kwargs):
        user, entry = self.entry(request, pk, **kwargs)
        data = TimelineSerializer(entry, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        data.save()
        audit.record(user, "member.profile_timeline_updated", makerspace=self.audit_space, target=user,
                     meta={"fields": sorted(data.validated_data)})
        return Response(data.data)

    @extend_schema(tags=["Member profile"], request=None, responses={204: None, **ERRORS})
    @transaction.atomic
    def delete(self, request, pk, **kwargs):
        user, entry = self.entry(request, pk, **kwargs)
        entry.delete()
        audit.record(user, "member.profile_timeline_deleted", makerspace=self.audit_space, target=user, meta={})
        return Response(status=204)


class AchievementSerializer(serializers.ModelSerializer):
    title = serializers.CharField(max_length=160, trim_whitespace=True)
    issuer = serializers.CharField(max_length=160, required=False, allow_blank=True)
    description = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    url = serializers.URLField(max_length=500, required=False, allow_blank=True)

    class Meta:
        model = ProfileAchievement
        fields = ("id", "title", "issuer", "achieved_on", "url", "description", "order")
        read_only_fields = ("id",)

    def validate_url(self, value):
        # Renders as an href on a page others read: https only, no credentials (stored XSS).
        if value:
            parsed = urlsplit(value)
            if parsed.scheme != "https" or parsed.username or parsed.password:
                raise serializers.ValidationError(gettext("Use an HTTPS link without credentials."))
        return value

    def validate_achieved_on(self, value):
        if value and value > date.today():
            raise serializers.ValidationError(gettext("The date cannot be in the future."))
        return value


class AchievementListView(AccountOwnerView):
    @extend_schema(tags=["Member profile"], summary="List the caller's self-reported achievements",
                   responses={200: AchievementSerializer(many=True), **ERRORS})
    def get(self, request, **kwargs):
        user = self.actor(request, **kwargs)
        profile = AccountProfile.objects.filter(user=user).first()
        return Response(AchievementSerializer(profile.achievements.all() if profile else [], many=True).data)

    @extend_schema(tags=["Member profile"], summary="Add a self-reported achievement",
                   request=AchievementSerializer,
                   responses={201: AchievementSerializer, 400: ErrorSerializer, **ERRORS})
    @transaction.atomic
    def post(self, request, **kwargs):
        user = self.actor(request, **kwargs)
        profile = locked_profile(user)
        if profile.achievements.count() >= MAX_ACHIEVEMENTS:
            raise ValidationError({"achievements": gettext("At most 30 achievements are allowed.")})
        data = AchievementSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        row = data.save(profile=profile)
        audit.record(user, "member.profile_achievement_created", makerspace=self.audit_space, target=user,
                     meta={"fields": sorted(data.validated_data)})
        return Response(AchievementSerializer(row).data, status=201)


class AchievementDetailView(AccountOwnerView):
    def row(self, request, pk, **kwargs):
        user = self.actor(request, **kwargs)
        return user, get_object_or_404(existing_profile(user, lock=True).achievements, pk=pk)

    @extend_schema(tags=["Member profile"], summary="Edit a self-reported achievement",
                   request=AchievementSerializer,
                   responses={200: AchievementSerializer, 400: ErrorSerializer, **ERRORS})
    @transaction.atomic
    def patch(self, request, pk, **kwargs):
        user, row = self.row(request, pk, **kwargs)
        data = AchievementSerializer(row, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        data.save()
        audit.record(user, "member.profile_achievement_updated", makerspace=self.audit_space, target=user,
                     meta={"fields": sorted(data.validated_data)})
        return Response(data.data)

    @extend_schema(tags=["Member profile"], summary="Delete a self-reported achievement",
                   request=None, responses={204: None, **ERRORS})
    @transaction.atomic
    def delete(self, request, pk, **kwargs):
        user, row = self.row(request, pk, **kwargs)
        row.delete()
        audit.record(user, "member.profile_achievement_deleted", makerspace=self.audit_space, target=user,
                     meta={})
        return Response(status=204)
