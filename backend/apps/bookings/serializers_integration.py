"""Explicit projections: private finance and editorial previews never enter reads."""

from django.http import Http404
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from apps.payments.money_fields import MoneyField

from .serializers_website import BookingPublicRulesSerializer


class IntegrationBookingPublicSectionSerializer(serializers.Serializer):
    kind = serializers.CharField()
    slug = serializers.CharField()
    title = serializers.CharField()
    body = serializers.CharField()
    url = serializers.CharField()
    position = serializers.IntegerField()
    image_url = serializers.CharField(allow_null=True)
    image_alt_text = serializers.CharField()


class IntegrationBookingPublicPageSerializer(serializers.Serializer):
    public_url = serializers.URLField()
    embed_path = serializers.CharField()
    payment_amount = MoneyField(max_digits=13, decimal_places=3)
    currency = serializers.CharField()
    rules = BookingPublicRulesSerializer()
    sections = IntegrationBookingPublicSectionSerializer(many=True)


class IntegrationBookingResourceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    kind = serializers.CharField()
    description = serializers.CharField()
    capacity = serializers.IntegerField()
    location = serializers.CharField()
    is_active = serializers.BooleanField()
    is_public = serializers.BooleanField()
    public_page = serializers.SerializerMethodField()

    @extend_schema_field(IntegrationBookingPublicPageSerializer(allow_null=True))
    def get_public_page(self, instance):
        from .website_projection import detail
        from .website_visibility import resolve

        # Signed resource authority includes private resources. The additional
        # publication projection must independently pass the live public gates.
        try:
            public = detail(resolve(instance.makerspace.slug, instance.public_token))
        except Http404:
            return None
        if public["website"] is None:
            return None
        return IntegrationBookingPublicPageSerializer({
            **public["website"], **{key: public[key] for key in ("payment_amount", "currency", "rules")},
        }).data


class IntegrationBookingSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    resource_id = serializers.IntegerField(source="space_id")
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    status = serializers.CharField()
    display_name = serializers.CharField(source="name")
    arrived_at = serializers.DateTimeField(allow_null=True, required=False)

    def __init__(self, *args, attendance=None, **kwargs):
        super().__init__(*args, **kwargs)
        if attendance is False:
            self.fields.pop("arrived_at")


class IntegrationBookingResourcePageSerializer(serializers.Serializer):
    next_cursor = serializers.CharField(allow_null=True)
    results = IntegrationBookingResourceSerializer(many=True)


class IntegrationBookingPageSerializer(serializers.Serializer):
    next_cursor = serializers.CharField(allow_null=True)
    results = IntegrationBookingSerializer(many=True)
