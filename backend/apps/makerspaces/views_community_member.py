"""Decision 223 (k): the member's side of guardian consent, volunteer hours and the join call to action.

Guardian routes work for the named guardian ACCOUNT (a guardian need not be a member). Volunteer routes work
for the member's own hours and credits. The join prefill works for a signed-in non-member who attended an
event or holds a guest pass. Every route answers 404 while its `membership.*` switch (or the membership
module) is off, and never returns anything about another person's account.
"""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.account_kind_guards import require_member_account
from apps.accounts.schemas_self_service import ACCOUNT_ERRORS as ERRORS
from apps.makerspaces import join_funnel, minors, volunteer_hours
from apps.makerspaces.membership_features import require_membership_feature
from apps.makerspaces.models import GuardianConsent, MinorProfile, VolunteerCredit, VolunteerHourEntry
from apps.makerspaces.serializers_community import (
    ConsentInputSerializer, ConsentSerializer, GuardianConsentPageSerializer, JoinPrefillSerializer,
    VolunteerCreditSerializer, VolunteerEntrySerializer, VolunteerLogInputSerializer, dependent_payload,
)
from apps.makerspaces.servability import servable_queryset

TAG = "Member community"


def _space(user, makerspace_id, feature):
    require_member_account(user)
    if not user.is_active or user.access_status != "active":
        raise PermissionDenied()
    return require_membership_feature(get_object_or_404(servable_queryset(), pk=makerspace_id), feature)


def _dependent(user, space, profile_id):
    return get_object_or_404(MinorProfile.objects.select_related("user", "makerspace"),
                             pk=profile_id, makerspace=space, guardian_user=user, cleared_at__isnull=True)


class GuardianConsentPageView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=[TAG], summary="Guardian consent: the text and the people you are guardian of",
                   description="The active consent text, and for each minor who names YOUR account as guardian "
                               "whether a consent stands and the history. Needs membership.minors.",
                   responses={200: GuardianConsentPageSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        space = _space(request.user, makerspace_id, "minors")
        profiles = (MinorProfile.objects.filter(makerspace=space, guardian_user=request.user, cleared_at__isnull=True)
                    .select_related("user").prefetch_related("consents"))
        return Response(GuardianConsentPageSerializer({
            "terms": minors.active_terms(space), "dependents": [dependent_payload(p) for p in profiles]}).data)


class GuardianConsentSignView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=[TAG], summary="Sign the guardian consent for a minor",
                   description="E-signature on the CURRENT text: tick accepted and type your full name. Valid for "
                               "the space's consent period; a new text asks again. 403 `not_the_guardian` unless "
                               "you are the named guardian; 409 `guardian_terms_missing` if no text is published. "
                               "Audited as membership.guardian_consent_signed.",
                   request=ConsentInputSerializer, responses={201: ConsentSerializer, **ERRORS})
    def post(self, request, makerspace_id, profile_id):
        space = _space(request.user, makerspace_id, "minors")
        profile = _dependent(request.user, space, profile_id)
        data = ConsentInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        consent = minors.sign_consent(
            request.user, profile, values["signed_name"], accepted=values["accepted"],
            method=GuardianConsent.Method.GUARDIAN_ACCOUNT, operation_id=values.get("operation_id") or None)
        return Response(ConsentSerializer(consent).data, status=status.HTTP_201_CREATED)


class GuardianConsentRevokeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=[TAG], summary="Withdraw your guardian consent",
                   description="Revokes every standing consent for that minor; they are refused again until a "
                               "new one is signed. Audited.", request=None, responses={200: ConsentSerializer(many=True), **ERRORS})
    def post(self, request, makerspace_id, profile_id):
        space = _space(request.user, makerspace_id, "minors")
        profile = _dependent(request.user, space, profile_id)
        rows = [minors.revoke_consent(request.user, c)
                for c in GuardianConsent.objects.filter(profile=profile, revoked_at__isnull=True)]
        return Response(ConsentSerializer(rows, many=True).data)


class MemberVolunteerHoursView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=[TAG], summary="Your volunteer hours in this space",
                   description="Needs membership.volunteer_credit.",
                   responses={200: VolunteerEntrySerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        space = _space(request.user, makerspace_id, "volunteer_credit")
        rows = VolunteerHourEntry.objects.filter(makerspace=space, member=request.user).select_related("member")
        return Response(VolunteerEntrySerializer(rows[:100], many=True).data)

    @extend_schema(tags=[TAG], summary="Log hours you volunteered",
                   description="Waits for staff approval; you must hold an active membership. Audited.",
                   request=VolunteerLogInputSerializer, responses={201: VolunteerEntrySerializer, **ERRORS})
    def post(self, request, makerspace_id):
        space = _space(request.user, makerspace_id, "volunteer_credit")
        data = VolunteerLogInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        values.pop("member_id", None)
        entry = volunteer_hours.log_hours(request.user, space, request.user, by_staff=False, **values)
        return Response(VolunteerEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


class MemberVolunteerCreditsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=[TAG], summary="Your volunteer credits",
                   description="Credits you earned and where they were applied. Needs membership.volunteer_credit.",
                   responses={200: VolunteerCreditSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        space = _space(request.user, makerspace_id, "volunteer_credit")
        rows = VolunteerCredit.objects.filter(makerspace=space, member=request.user).order_by("-created_at", "-pk")
        return Response(VolunteerCreditSerializer(rows[:100], many=True).data)


class JoinPrefillView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=[TAG], summary="Pre-fill a membership request from an event ticket or guest pass",
                   description="The 'Join' call to action. Pass `registration_id` (an event you attended) or "
                               "`guest_pass_id`. Returns what to pre-fill; submit it to the ordinary admission "
                               "route. 404 `source_not_found` when the ticket or pass is not yours, 409 "
                               "`already_member`. Needs membership.join_funnel.",
                   parameters=[OpenApiParameter("registration_id", int), OpenApiParameter("guest_pass_id", int)],
                   responses={200: JoinPrefillSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        space = _space(request.user, makerspace_id, "join_funnel")
        params = request.query_params
        found = join_funnel.join_prefill(
            request.user, space,
            registration_id=int(params["registration_id"]) if params.get("registration_id", "").isdigit() else None,
            guest_pass_id=int(params["guest_pass_id"]) if params.get("guest_pass_id", "").isdigit() else None)
        return Response(JoinPrefillSerializer(found).data)
