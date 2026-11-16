"""Decision 223 (k), lane L3b: member routes for guardian consent, volunteer hours and the join prefill."""
from django.urls import path

from apps.makerspaces.views_community_minor_status import OwnGuardianConsentStatusView
from apps.makerspaces.views_community_member import (
    GuardianConsentPageView, GuardianConsentRevokeView, GuardianConsentSignView, JoinPrefillView,
    MemberVolunteerCreditsView, MemberVolunteerHoursView,
)

_MEMBER = "member/makerspaces/<int:makerspace_id>"

urlpatterns = [
    path(f"{_MEMBER}/guardian-consents", GuardianConsentPageView.as_view(), name="member-guardian-consents"),
    path(f"{_MEMBER}/guardian-consents/<int:profile_id>/sign", GuardianConsentSignView.as_view(),
         name="member-guardian-consent-sign"),
    path(f"{_MEMBER}/guardian-consents/<int:profile_id>/revoke", GuardianConsentRevokeView.as_view(),
         name="member-guardian-consent-revoke"),
    path(f"{_MEMBER}/my-guardian-consent", OwnGuardianConsentStatusView.as_view(), name="member-own-guardian-consent"),
    path(f"{_MEMBER}/volunteer-hours", MemberVolunteerHoursView.as_view(), name="member-volunteer-hours"),
    path(f"{_MEMBER}/volunteer-credits", MemberVolunteerCreditsView.as_view(), name="member-volunteer-credits"),
    path(f"{_MEMBER}/join-prefill", JoinPrefillView.as_view(), name="member-join-prefill"),
]
