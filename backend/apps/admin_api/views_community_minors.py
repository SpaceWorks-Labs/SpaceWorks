"""Decision 223 (k): staff routes for minors and guardian consent (lane L3b).

`manage_members` records a minor, clears the record, and records a guardian's signature taken on paper or at
the desk; `manage_makerspace` publishes the guardian-consent text and edits the community policy. Every
route answers 404 while `membership.minors` is off (the policy route needs only `membership`), and every
write is audited by the service with ids, versions and field names only (never a birth date, a contact
detail or the consent text).
"""
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.accounts.models import User
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.views_member_memberships import _makerspace
from apps.admin_api.views_membership_l4_common import staff_space
from apps.admin_api.views_roles import ERRORS
from apps.makerspaces import community_policy, minors
from apps.makerspaces.guards import require_module
from apps.makerspaces.models import GuardianConsent, GuardianConsentTerms, MinorProfile
from apps.makerspaces.serializers_community import (
    CommunityPolicySerializer, ConsentInputSerializer, ConsentSerializer, GuardianTermsInputSerializer,
    GuardianTermsSerializer, MinorProfileSerializer, MinorRecordInputSerializer, minors_queryset,
    staff_minor_payload, user_name,
)
from django.utils.translation import gettext

TAG = "Admin community"
MANAGE = rbac.Action.MANAGE_MAKERSPACE


class _Pager(PageNumberPagination):
    page_size = 24


def _connected_to_space(users, space):
    """Audit M9: only people already tied to THIS space (a membership row or application, a guest pass,
    an event registration or a presence visit) can be looked up, so the route is not a platform-wide
    account oracle. Anything else answers the same 404 as a missing account."""
    from apps.events.models import EventRegistration
    from apps.makerspaces.models import GuestPass, MakerspaceMembership
    from apps.presence.models import PresenceSession
    return users.filter(
        Q(pk__in=MakerspaceMembership.objects.filter(makerspace=space).values("user_id"))
        | Q(pk__in=GuestPass.objects.filter(makerspace=space).values("holder_id"))
        | Q(pk__in=EventRegistration.objects.filter(event__makerspace=space, member__isnull=False).values("member_id"))
        | Q(pk__in=PresenceSession.objects.filter(makerspace=space).values("account_id")))


def _person(space, user_id=None, email=None):
    users = _connected_to_space(User.objects.filter(
        account_kind="member", is_active=True, retired_at__isnull=True, merged_into__isnull=True), space)
    user = users.filter(pk=user_id).first() if user_id else users.filter(email__iexact=email).first()
    if user is None:
        raise NotFound(gettext("No account matches that person."))
    return user


def _profile(space, profile_id):
    return get_object_or_404(minors_queryset(space), pk=profile_id)


class CommunityPolicyView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Read the community policy",
                   description="Requires manage_makerspace and the membership module. Settings for minors, "
                               "volunteer credit and the join follow-up; a space that never saved it gets the "
                               "defaults. Each group only matters while its membership.* switch is on.",
                   responses={200: CommunityPolicySerializer, **ERRORS})
    def get(self, request, makerspace_id):
        space = _makerspace(request.user, makerspace_id, MANAGE)
        require_module(space, "membership")
        return Response(CommunityPolicySerializer(community_policy.policy_for(space)).data)

    @extend_schema(tags=[TAG], summary="Change the community policy",
                   description="Partial update; changing a setting of a switched-off feature is refused with "
                               "`feature_disabled`. Audited with the changed field names.",
                   request=CommunityPolicySerializer(partial=True), responses={200: CommunityPolicySerializer, **ERRORS})
    def patch(self, request, makerspace_id):
        space = _makerspace(request.user, makerspace_id, MANAGE)
        require_module(space, "membership")
        data = CommunityPolicySerializer(community_policy.policy_for(space), data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        return Response(CommunityPolicySerializer(
            community_policy.update_policy(request.user, space, dict(data.validated_data))).data)


class MinorProfileListView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "minor_person_lookup"
    pagination_class = _Pager

    @extend_schema(tags=[TAG], summary="List the minors recorded in a space",
                   description="Requires manage_members and membership.minors. Shows an age or an 'under age' "
                               "declaration, never the birth date.",
                   responses={200: MinorProfileSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, "minors")
        pager = _Pager()
        page = pager.paginate_queryset(minors_queryset(space), request)
        return pager.get_paginated_response([staff_minor_payload(row) for row in page])

    @extend_schema(tags=[TAG], summary="Record a person as a minor",
                   description="By account id or e-mail, with a birth date or an 'under age' declaration and "
                               "the guardian (an account, or name and contact). Updates the record when one "
                               "exists. Audited as membership.minor_recorded.",
                   request=MinorRecordInputSerializer, responses={201: MinorProfileSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, "minors")
        data = MinorRecordInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        user = _person(space, values.pop("user_id", None), values.pop("user_email", None))
        guardian_id = values.pop("guardian_user_id", None)
        guardian = _person(space, guardian_id) if guardian_id else None
        profile = minors.record_minor(request.user, space, user, guardian_user=guardian, **values)
        return Response(staff_minor_payload(profile), status=status.HTTP_201_CREATED)


class MinorClearView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Stop treating a person as a minor",
                   description="Came of age or recorded by mistake. Consents stay as history. Audited.",
                   request=None, responses={200: MinorProfileSerializer, **ERRORS})
    def post(self, request, makerspace_id, profile_id):
        space = staff_space(request.user, makerspace_id, "minors")
        row = minors.clear_minor(request.user, _profile(space, profile_id))
        return Response(staff_minor_payload(row))


class ConsentHistorySerializer(ConsentSerializer):
    """One consent of a minor's history, live, expired or revoked (staff view)."""
    terms_version = serializers.CharField()
    signer = serializers.CharField(help_text="The name typed as the signature, or the guardian account's name.")
    recorded_by_name = serializers.CharField(allow_blank=True, help_text="Staff member who recorded a desk signature.")
    revoked_by_name = serializers.CharField(allow_blank=True)
    is_live = serializers.BooleanField(help_text="Signed, not revoked and not expired: the consent that admits the minor.")


def _consent_row(consent, now):
    return {"id": consent.pk, "terms_version": consent.terms_version, "method": consent.method,
            "signed_at": consent.signed_at, "valid_until": consent.valid_until, "revoked_at": consent.revoked_at,
            "signer": consent.signed_name or (user_name(consent.guardian_user) if consent.guardian_user_id else ""),
            "recorded_by_name": user_name(consent.recorded_by) if consent.recorded_by_id else "",
            "revoked_by_name": user_name(consent.revoked_by) if consent.revoked_by_id else "",
            "is_live": consent.revoked_at is None and consent.valid_until > now}


class MinorConsentRecordView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="List every guardian consent of a minor",
                   description="Requires manage_members and membership.minors. Newest first, including expired "
                               "and revoked consents, so staff can revoke an OLDER consent that is still live "
                               "(each is revoked through the consent revoke route). Read-only; nothing is audited.",
                   responses={200: ConsentHistorySerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id, profile_id):
        space = staff_space(request.user, makerspace_id, "minors")
        profile = _profile(space, profile_id)
        now = timezone.now()
        rows = profile.consents.select_related("guardian_user", "recorded_by", "revoked_by")
        return Response([_consent_row(row, now) for row in rows])

    @extend_schema(tags=[TAG], summary="Record a guardian's signature taken at the desk",
                   description="Paper or in person, on the CURRENT consent text. 409 `guardian_terms_missing` "
                               "when no text is published. Valid for the policy's consent_valid_days. Audited.",
                   request=ConsentInputSerializer, responses={201: ConsentSerializer, **ERRORS})
    def post(self, request, makerspace_id, profile_id):
        space = staff_space(request.user, makerspace_id, "minors")
        data = ConsentInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        consent = minors.sign_consent(
            request.user, _profile(space, profile_id), values["signed_name"], accepted=values["accepted"],
            method=GuardianConsent.Method.STAFF_RECORDED, operation_id=values.get("operation_id") or None)
        return Response(ConsentSerializer(consent).data, status=status.HTTP_201_CREATED)


class GuardianConsentRevokeView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Revoke a guardian consent",
                   description="The minor is refused again until a new consent is signed. Audited.",
                   request=None, responses={200: ConsentSerializer, **ERRORS})
    def post(self, request, makerspace_id, consent_id):
        space = staff_space(request.user, makerspace_id, "minors")
        row = get_object_or_404(GuardianConsent.objects.select_related("makerspace"), pk=consent_id, makerspace=space)
        return Response(ConsentSerializer(minors.revoke_consent(request.user, row)).data)


class GuardianTermsView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="List the guardian-consent texts",
                   description="Every published version, newest first; one is active. Requires manage_members "
                               "and membership.minors.",
                   responses={200: GuardianTermsSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, "minors")
        return Response(GuardianTermsSerializer(GuardianConsentTerms.objects.filter(makerspace=space), many=True).data)

    @extend_schema(tags=[TAG], summary="Publish new guardian-consent text",
                   description="Requires manage_makerspace. The previous version is kept and superseded; "
                               "guardians are asked to sign again, like a new waiver. Audited.",
                   request=GuardianTermsInputSerializer, responses={201: GuardianTermsSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, "minors", MANAGE)
        data = GuardianTermsInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        terms = minors.publish_terms(request.user, space, data.validated_data["body"],
                                     data.validated_data["version"])
        return Response(GuardianTermsSerializer(terms).data, status=status.HTTP_201_CREATED)
