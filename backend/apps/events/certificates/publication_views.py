from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from apps.admin_api.permissions import IsActiveStaff
from apps.events.credentials.views import CredentialCommandSerializer, CommandResultSerializer, ERRORS
from apps.events.profile_photos.views import private
from .publication import set_policy
from apps.events import event_authority
from .models import EventCertificatePublicationPolicy


class PublicationSerializer(CredentialCommandSerializer):
    enabled = serializers.BooleanField()
    certificate_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=200, default=list)


class PublicationStatusSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    event_version = serializers.IntegerField()


class PublicationResultSerializer(CommandResultSerializer):
    enabled = serializers.BooleanField()
    event_version = serializers.IntegerField()
    certificate_count = serializers.IntegerField()


class CertificatePublicationView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Event certificates"], responses={200: PublicationStatusSerializer, **ERRORS})
    def get(self, request, pk):
        event = event_authority.get_event(request.user, pk, None)
        enabled = EventCertificatePublicationPolicy.objects.filter(event=event, enabled=True).exists()
        return private(Response({"enabled": enabled, "event_version": event.version}))

    @extend_schema(tags=["Event certificates"], request=PublicationSerializer,
                   responses={200: PublicationResultSerializer, **ERRORS})
    def post(self, request, pk):
        serializer = PublicationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return private(Response(set_policy(pk, actor=request.user, **serializer.validated_data)))
