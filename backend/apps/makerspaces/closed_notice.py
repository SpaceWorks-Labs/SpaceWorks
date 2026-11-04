"""The Space Manager's "closed for now" banner on the public page (#77, platform Q10).

No new lifecycle state: the space stays fully servable and every page works; the public
page only shows a short notice and an optional reopening date. Behind the parentless
`public_site.closed_notice` switch (off by default; off hides the banner and the API and
keeps the text). Only the Space Manager (or the superadmin, #115) edits it, through the
settings-authority layer, which never delegates a key outside a managed module. Audited as
`makerspace.closed_notice_updated`.
"""

from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.audit import services as audit
from apps.hardware_requests.exceptions import ErrorSerializer

from .capability_eligibility import configuration_feature_enabled
from .models import Makerspace
from .servability import servable_queryset

FEATURE = "public_site.closed_notice"
FIELDS = ("public_closed_notice", "public_reopens_on")


def public_notice(makerspace):
    """`{"text", "reopens_on"}` for the public page, or None (switch off or no text)."""
    text = (makerspace.public_closed_notice or "").strip()
    if not text or not configuration_feature_enabled(makerspace, FEATURE):
        return None
    reopens = makerspace.public_reopens_on
    from .local_time import local_now
    if reopens is not None and reopens < local_now(makerspace).date():
        reopens = None  # A past date says nothing useful; the text still stands.
    return {"text": text, "reopens_on": reopens.isoformat() if reopens else None}


class ClosedNoticeSerializer(serializers.Serializer):
    public_closed_notice = serializers.CharField(max_length=280, allow_blank=True, trim_whitespace=True,
                                                 help_text="Shown on the public page; blank hides the banner.")
    public_reopens_on = serializers.DateField(allow_null=True, required=False,
                                              help_text="Optional reopening date in the space's own calendar.")


def save_notice(actor, makerspace, values):
    from apps.tenant_migration.gate_runtime import tenant_write
    from .folded_capabilities import require_capability
    from .settings_authority import assert_setting_write

    require_capability(makerspace, FEATURE)
    assert_setting_write(actor, makerspace, "public_site", "public_closed_notice")
    with tenant_write(makerspace.pk), transaction.atomic():
        locked = Makerspace.objects.select_for_update().get(pk=makerspace.pk)
        values = {"public_closed_notice": values["public_closed_notice"],
                  "public_reopens_on": values.get("public_reopens_on")}
        moved = sorted(field for field in FIELDS if getattr(locked, field) != values[field])
        if not moved:
            return locked
        for field in moved:
            setattr(locked, field, values[field])
        locked.save(update_fields=[*moved, "updated_at"])
        audit.record(actor, "makerspace.closed_notice_updated", makerspace=locked, target=locked, meta={
            "notice_set": bool(locked.public_closed_notice),
            "reopens_on": locked.public_reopens_on.isoformat() if locked.public_reopens_on else None,
            "changed_fields": moved,
        })
        return locked


class PublicClosedNoticeView(APIView):
    permission_classes = [IsActiveStaff]

    def space(self, request, makerspace_id):
        rows = rbac.scope_by_action(request.user, rbac.Action.MANAGE_MAKERSPACE,
                                    servable_queryset(Makerspace.objects.all()), field="pk")
        return get_object_or_404(rows, pk=makerspace_id)

    @extend_schema(tags=["Admin makerspaces"], summary="Read the closed-for-now banner", request=None,
                   description="Space Manager only; 404 while `public_site.closed_notice` is off.",
                   responses={200: ClosedNoticeSerializer, **{code: ErrorSerializer for code in (401, 403, 404)}})
    def get(self, request, makerspace_id):
        from .folded_capabilities import require_capability
        space = require_capability(self.space(request, makerspace_id), FEATURE)
        return Response(ClosedNoticeSerializer(space).data, headers={"Cache-Control": "private, no-store"})

    @extend_schema(tags=["Admin makerspaces"], summary="Set or clear the closed-for-now banner",
                   description="No lifecycle change: the space keeps working. Audited as "
                               "`makerspace.closed_notice_updated`.",
                   request=ClosedNoticeSerializer,
                   responses={200: ClosedNoticeSerializer, **{code: ErrorSerializer for code in (400, 401, 403, 404, 423)}})
    def put(self, request, makerspace_id):
        space = self.space(request, makerspace_id)
        data = ClosedNoticeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        saved = save_notice(request.user, space, data.validated_data)
        return Response(ClosedNoticeSerializer(saved).data, headers={"Cache-Control": "private, no-store"})

