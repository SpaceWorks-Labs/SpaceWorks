"""Platform IP rules and automatic blocks in the web superadmin console (#190, parity with /control/).

The same rules and the same records as ``admin_ip_access``: superadmin only, every write
behind the re-authentication step-up, the same lock-out guard, and the same audit rows
(``platform.ip_rule_saved`` / ``_deleted`` with ``via=console``; ``auth.ip_unblocked``).
Lifting a block deletes it, exactly like the /control/ action; blocks are never added here.
"""

from django.utils.translation import gettext
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import ip_rules
from apps.accounts.ip_rule_edits import LOCKOUT_MESSAGE, unblock, would_lock_out
from apps.accounts.models import IPAccessRule, IPAutoBlock
from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.admin_api.permissions import IsActiveSuperAdmin
from apps.audit import services as audit
from apps.openapi_errors import errors

TAGS = ["Platform security"]
EDITABLE = ("cidr", "action", "note", "expires_at")


class IPAccessRuleSerializer(serializers.ModelSerializer):
    created_by = serializers.SerializerMethodField()
    active = serializers.SerializerMethodField()

    class Meta:
        model = IPAccessRule
        fields = ("id", "cidr", "action", "note", "expires_at", "active", "created_by", "created_at")
        read_only_fields = ("id", "active", "created_by", "created_at")
        extra_kwargs = {
            "cidr": {"help_text": "One address (203.0.113.7) or a network (203.0.113.0/24, 2001:db8::/48)."},
            "action": {"help_text": "allow beats every deny rule and every automatic block; deny always applies."},
            "expires_at": {"help_text": "Empty keeps the rule until it is deleted."},
        }

    def get_created_by(self, obj) -> str | None:
        return (obj.created_by.display_name or obj.created_by.username) if obj.created_by_id else None

    def get_active(self, obj) -> bool:
        return obj.expires_at is None or obj.expires_at > timezone.now()

    def validate_cidr(self, value):
        try:
            return ip_rules.canonical_cidr(value)
        except ValueError:
            raise serializers.ValidationError(gettext("Enter an IP address or a network in CIDR form.")) from None

    def validate(self, attrs):
        cidr = attrs.get("cidr", getattr(self.instance, "cidr", None))
        action = attrs.get("action", getattr(self.instance, "action", None))
        if would_lock_out(self.context.get("editor_address"), cidr, action,
                          replacing_cidr=getattr(self.instance, "cidr", None)):
            raise serializers.ValidationError({"cidr": LOCKOUT_MESSAGE})
        return attrs


class IPAutoBlockSerializer(serializers.ModelSerializer):
    active = serializers.SerializerMethodField()

    class Meta:
        model = IPAutoBlock
        fields = ("id", "network", "blocked_until", "created_at", "active")
        read_only_fields = fields

    def get_active(self, obj) -> bool:
        return obj.blocked_until > timezone.now()


class UnblockResultSerializer(serializers.Serializer):
    unblocked = serializers.IntegerField(min_value=0)


def _editor_address(request):
    from config.client_ip import get_throttle_client_ip

    return ip_rules.parse_address(get_throttle_client_ip(request))


def _changed(instance, data):
    return sorted(field for field in EDITABLE if field in data and getattr(instance, field) != data[field])


class IPAccessRuleListCreateView(RecentReauthenticationMixin, GenericAPIView):
    permission_classes = [IsActiveSuperAdmin]
    serializer_class = IPAccessRuleSerializer

    @extend_schema(tags=TAGS, summary="List the platform IP allow and deny rules",
                   responses={200: IPAccessRuleSerializer(many=True), **errors(401, 403)})
    def get(self, request):
        page = self.paginate_queryset(IPAccessRule.objects.select_related("created_by").order_by("-created_at", "-pk"))
        return self.get_paginated_response(IPAccessRuleSerializer(page, many=True).data)

    @extend_schema(tags=TAGS, summary="Add a platform IP rule (refused if it would lock you out)",
                   request=IPAccessRuleSerializer, responses={201: IPAccessRuleSerializer, **errors(400, 401, 403)})
    def post(self, request):
        body = IPAccessRuleSerializer(data=request.data, context={"editor_address": _editor_address(request)})
        body.is_valid(raise_exception=True)
        rule = body.save(created_by=request.user)
        audit.record(request.user, "platform.ip_rule_saved", target=rule, meta={
            "via": "console", "created": True, "action": rule.action,
            "changed_fields": sorted(field for field in EDITABLE if field in body.validated_data)})
        return Response(IPAccessRuleSerializer(rule).data, status=status.HTTP_201_CREATED)


class IPAccessRuleDetailView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="Change a platform IP rule", request=IPAccessRuleSerializer,
                   responses={200: IPAccessRuleSerializer, **errors(400, 401, 403, 404)})
    def patch(self, request, pk):
        rule = get_object_or_404(IPAccessRule, pk=pk)
        body = IPAccessRuleSerializer(rule, data=request.data, partial=True,
                                      context={"editor_address": _editor_address(request)})
        body.is_valid(raise_exception=True)
        changed = _changed(rule, body.validated_data)
        rule = body.save()
        audit.record(request.user, "platform.ip_rule_saved", target=rule, meta={
            "via": "console", "created": False, "action": rule.action, "changed_fields": changed})
        return Response(IPAccessRuleSerializer(rule).data)

    @extend_schema(tags=TAGS, summary="Delete a platform IP rule", responses={204: None, **errors(401, 403, 404)})
    def delete(self, request, pk):
        rule = get_object_or_404(IPAccessRule, pk=pk)
        audit.record(request.user, "platform.ip_rule_deleted", target=rule,
                     meta={"via": "console", "action": rule.action})
        rule.delete()  # post_delete clears the cached rule set
        return Response(status=status.HTTP_204_NO_CONTENT)


class IPAutoBlockListView(GenericAPIView):
    permission_classes = [IsActiveSuperAdmin]
    serializer_class = IPAutoBlockSerializer

    @extend_schema(tags=TAGS, summary="List automatic network blocks (blocking now first)",
                   responses={200: IPAutoBlockSerializer(many=True), **errors(401, 403)})
    def get(self, request):
        page = self.paginate_queryset(IPAutoBlock.objects.order_by("-blocked_until", "-pk"))
        return self.get_paginated_response(IPAutoBlockSerializer(page, many=True).data)


class IPAutoBlockUnblockView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="Lift an automatic block now", request=None,
                   responses={200: UnblockResultSerializer, **errors(401, 403, 404)})
    def post(self, request, pk):
        row = get_object_or_404(IPAutoBlock, pk=pk)
        return Response({"unblocked": unblock(request.user, [row])})
