"""Open item A27 (ROLE-COMPLETENESS PE7): a minor reads their OWN guardian-consent standing.

Read-only and about the caller only: whether this space treats them as a minor, whether a guardian
consent currently stands (and until when), and the space's rules that follow from it. It never
returns the guardian's contact details (scoped personal data) or anyone else's profile. 404 while
`membership.minors` (or the membership module) is off, like every other community route.
"""
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.schemas_self_service import ACCOUNT_ERRORS as ERRORS
from apps.makerspaces import minors
from apps.makerspaces.community_policy import policy_for
from apps.makerspaces.models import GuardianConsent
from apps.makerspaces.views_community_member import TAG, _space


class OwnConsentStatusSerializer(serializers.Serializer):
    applies = serializers.BooleanField(help_text="False when this space does not treat you as a minor.")
    state = serializers.ChoiceField(choices=["not_applicable", "current", "pending", "expired", "terms_missing"])
    valid_until = serializers.DateTimeField(allow_null=True)
    guardian_named = serializers.BooleanField()
    guardian_must_be_present = serializers.BooleanField()
    may_borrow = serializers.BooleanField()
    may_use_machines = serializers.BooleanField()


def own_status(user, space, now=None):
    now = now or timezone.now()
    profile = minors.profile_for(space, user)
    policy = policy_for(space)
    if not minors.is_minor(profile, policy):
        return {"applies": False, "state": "not_applicable", "valid_until": None, "guardian_named": False,
                "guardian_must_be_present": False, "may_borrow": True, "may_use_machines": True}
    consent = minors.current_consent(profile, now)
    if consent is not None:
        state = "current"
    elif minors.active_terms(space) is None:
        state = "terms_missing"
    else:
        state = "expired" if GuardianConsent.objects.filter(profile=profile).exists() else "pending"
    return {"applies": True, "state": state, "valid_until": consent.valid_until if consent else None,
            "guardian_named": bool(profile.guardian_user_id or profile.guardian_email),
            "guardian_must_be_present": policy.guardian_must_be_present,
            "may_borrow": policy.minors_may_borrow, "may_use_machines": policy.minors_may_use_machines}


class OwnGuardianConsentStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=[TAG], summary="Your own guardian consent status",
                   description="For a member under the space's age of majority: whether a guardian consent "
                               "currently stands, until when, and what the space allows. About the caller only; "
                               "never returns guardian contact details. Needs membership.minors.",
                   responses={200: OwnConsentStatusSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        space = _space(request.user, makerspace_id, "minors")
        return Response(OwnConsentStatusSerializer(own_status(request.user, space)).data)
