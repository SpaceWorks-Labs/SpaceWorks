"""Superadmin PII windows on one makerspace: status, open, close (owner decision #111 Q12).

Opening needs a reason and recent re-authentication. The status read is also open to the
space's own Space Manager, who sees every window on the space -- the same facts the audit
log carries -- so a platform PII view is never invisible to the people it concerns.
"""

from django.utils.translation import gettext
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import pii_access
from apps.accounts.models_pii_access import PlatformPiiAccessGrant
from apps.accounts.pii_presentation import pii_visible
from apps.accounts.platform_authority import is_platform_superadmin
from apps.accounts.reauthentication import require_recent_reauth
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.serializers_security_settings import PiiAccessOpenSerializer, PiiAccessStatusSerializer
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces import security_settings
from apps.makerspaces.models import Makerspace

ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404)}


def _grant_row(grant, viewer):
    actor = grant.actor
    return {"id": grant.id, "scope": "space" if grant.makerspace_id else "person", "reason": grant.reason,
            "opened_by": actor.display_name or actor.username, "opened_at": grant.opened_at,
            "expires_at": grant.expires_at, "closed_at": grant.closed_at, "close_reason": grant.close_reason,
            "is_own": grant.actor_id == getattr(viewer, "pk", None)}


def _status(request, space):
    viewer = request.user
    pii_access.sweep_expired(makerspace_id=space.pk)
    now = timezone.now()
    rows = PlatformPiiAccessGrant.objects.filter(makerspace=space).select_related("actor")
    open_rows = [row for row in rows.filter(closed_at__isnull=True, expires_at__gt=now)]
    own = next((row for row in open_rows if row.actor_id == viewer.pk), None)
    response = Response(PiiAccessStatusSerializer({
        "makerspace_id": space.pk, "viewer_is_superadmin": is_platform_superadmin(viewer),
        "pii_visible": pii_visible(viewer, space.pk),
        "active": _grant_row(own, viewer) if own else None,
        "space_grants": [_grant_row(row, viewer) for row in open_rows],
        "recent": [_grant_row(row, viewer) for row in rows[:10]],
    }).data)
    response["Cache-Control"] = "private, no-store"
    return response


def _space(request, makerspace_id, *, superadmin_only):
    space = get_object_or_404(Makerspace, pk=makerspace_id)
    if is_platform_superadmin(request.user):
        return space
    if superadmin_only or security_settings.editor_via(request.user, space) is None:
        raise PermissionDenied(gettext("Only a platform superadmin or this space's Space Manager can see PII access."))
    return space


class PiiAccessView(APIView):
    permission_classes = [IsActiveStaff]
    serializer_class = PiiAccessStatusSerializer

    @extend_schema(tags=["PII access"], summary="PII access windows on a space",
                   description="A platform superadmin sees their own window and every open one; this space's "
                               "Space Manager sees the same list read-only. Lapsed windows are closed and "
                               "audited first.", responses={200: PiiAccessStatusSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        return _status(request, _space(request, makerspace_id, superadmin_only=False))

    @extend_schema(tags=["PII access"], summary="Open a 30-minute PII window",
                   description="Platform superadmin with recent re-authentication (403 `recent_reauth_required`). "
                               "Audited as `platform.pii_access_opened` in this space; 409 "
                               "`pii_access_already_open` when one is open.",
                   request=PiiAccessOpenSerializer,
                   responses={201: PiiAccessStatusSerializer, **ERRORS,
                              409: OpenApiResponse(ErrorSerializer, description="A window is already open.")})
    def post(self, request, makerspace_id):
        space = _space(request, makerspace_id, superadmin_only=True)
        require_recent_reauth(request)
        body = PiiAccessOpenSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            pii_access.open_grant(request.user, space, body.validated_data["reason"])
        except DjangoValidationError as exc:
            raise ValidationError({"detail": exc.messages[0], "code": exc.code or "invalid"}) from exc
        response = _status(request, space)
        response.status_code = status.HTTP_201_CREATED
        return response

    @extend_schema(tags=["PII access"], summary="Close my PII window now",
                   description="Platform superadmin; closes the caller's open window on this space and audits "
                               "`platform.pii_access_closed`. 404 when none is open.",
                   request=None, responses={200: PiiAccessStatusSerializer, **ERRORS})
    def delete(self, request, makerspace_id):
        space = _space(request, makerspace_id, superadmin_only=True)
        grant = get_object_or_404(PlatformPiiAccessGrant, makerspace=space, actor=request.user,
                                  closed_at__isnull=True, expires_at__gt=timezone.now())
        pii_access.close_grant(request.user, grant)
        return _status(request, space)
