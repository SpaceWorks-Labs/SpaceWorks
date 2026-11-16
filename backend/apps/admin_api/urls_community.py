"""Decision 223 (k), lane L3b: staff routes for minors, guardian consent and volunteer hours."""
from django.urls import path

from apps.admin_api.views_community_minors import (
    CommunityPolicyView, GuardianConsentRevokeView, GuardianTermsView, MinorClearView, MinorConsentRecordView,
    MinorProfileListView,
)
from apps.admin_api.views_community_volunteer import (
    VolunteerCreditListView, VolunteerCreditVoidView, VolunteerHoursDecideView, VolunteerHoursImportView,
    VolunteerHoursListView,
)

_SPACE = "makerspaces/<int:makerspace_id>"

urlpatterns = [
    path(f"{_SPACE}/community-policy", CommunityPolicyView.as_view(), name="admin-community-policy"),
    path(f"{_SPACE}/minors", MinorProfileListView.as_view(), name="admin-minors"),
    path(f"{_SPACE}/minors/<int:profile_id>/clear", MinorClearView.as_view(), name="admin-minor-clear"),
    path(f"{_SPACE}/minors/<int:profile_id>/consents", MinorConsentRecordView.as_view(),
         name="admin-minor-consent-record"),
    path(f"{_SPACE}/guardian-consents/<int:consent_id>/revoke", GuardianConsentRevokeView.as_view(),
         name="admin-guardian-consent-revoke"),
    path(f"{_SPACE}/guardian-terms", GuardianTermsView.as_view(), name="admin-guardian-terms"),
    path(f"{_SPACE}/volunteer-hours", VolunteerHoursListView.as_view(), name="admin-volunteer-hours"),
    path(f"{_SPACE}/volunteer-hours/import-event-shifts", VolunteerHoursImportView.as_view(),
         name="admin-volunteer-hours-import"),
    path(f"{_SPACE}/volunteer-hours/<int:entry_id>/decide", VolunteerHoursDecideView.as_view(),
         name="admin-volunteer-hours-decide"),
    path(f"{_SPACE}/volunteer-credits", VolunteerCreditListView.as_view(), name="admin-volunteer-credits"),
    path(f"{_SPACE}/volunteer-credits/<int:credit_id>/void", VolunteerCreditVoidView.as_view(),
         name="admin-volunteer-credit-void"),
]
