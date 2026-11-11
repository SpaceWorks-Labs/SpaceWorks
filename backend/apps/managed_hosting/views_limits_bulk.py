"""Bulk-apply per-space limits (owner 2026-11-11): up to 50 spaces, all or nothing, superadmin + reauth."""
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.admin_api.permissions import IsActiveSuperAdmin
from apps.makerspaces.limits_core import KNOWN_LIMIT_KEYS

from apps.audit import services as audit
from apps.makerspaces.limits_validation import validate_resource_limit_overrides
from apps.makerspaces.models import Makerspace
from apps.openapi_errors import errors


TAGS = ["Managed hosting"]


class BulkLimitsSerializer(serializers.Serializer):
    makerspace_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=False,
                                           max_length=50)
    set = serializers.DictField(required=False, default=dict,
                                help_text="Keys to set on every listed space: a number, -1 or null (no limit), or "
                                          "the boolean `custom_domain`. Keys not listed are left alone.")
    clear = serializers.ListField(child=serializers.CharField(), required=False, default=list,
                                  help_text="Keys to reset to none (the stored override is removed).")

    def validate_makerspace_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Ids must be unique.")
        return value

    def validate(self, attrs):
        attrs["set"] = validate_resource_limit_overrides(attrs["set"])
        unknown = sorted(set(attrs["clear"]) - KNOWN_LIMIT_KEYS)
        if unknown:
            raise serializers.ValidationError({"clear": f"Unknown resource limit key: {unknown[0]}."})
        if not attrs["set"] and not attrs["clear"]:
            raise serializers.ValidationError("Send at least one key in `set` or `clear`.")
        return attrs


class BulkLimitsResultSerializer(serializers.Serializer):
    updated = serializers.IntegerField()
    makerspace_ids = serializers.ListField(child=serializers.IntegerField())


class BulkSpaceLimitsView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="Set or clear limit keys on many spaces (all or nothing)",
                   description="Superadmin only, recent re-authentication. Every space is audited as "
                               "`space_control.limits_changed`. 409 `bulk_failed` names the refused id.",
                   request=BulkLimitsSerializer,
                   responses={200: BulkLimitsResultSerializer, **errors(400, 401, 403, 404, 409)})
    def post(self, request):
        from apps.admin_api.bulk_decisions import BulkFailed
        body = BulkLimitsSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        ids, to_set, to_clear = (body.validated_data[k] for k in ("makerspace_ids", "set", "clear"))
        with transaction.atomic():
            spaces = {s.pk: s for s in Makerspace.objects.select_for_update().filter(pk__in=ids)}
            for pk in ids:
                space = spaces.get(pk)
                if space is None:
                    raise BulkFailed(pk, serializers.ValidationError({"makerspace_ids": "Unknown makerspace."}))
                old = dict(space.resource_limit_overrides or {})
                new = {k: v for k, v in old.items() if k not in to_clear}
                new.update(to_set)
                from apps.makerspaces.limits_storage_backfill import backfill_if_newly_limited
                backfill_if_newly_limited(space, old, new)  # #261
                space.resource_limit_overrides = new
                space.save(update_fields=["resource_limit_overrides"])
                changed = sorted(k for k in set(old) | set(new) if old.get(k, "unset") != new.get(k, "unset"))
                audit.record(request.user, "space_control.limits_changed", makerspace=space, target=space,
                             meta={"changed": changed, "overrides": new})
        return Response({"updated": len(ids), "makerspace_ids": ids})
