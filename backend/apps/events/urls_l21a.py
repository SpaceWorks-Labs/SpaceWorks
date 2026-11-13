"""Lane L21a programme routes: review stages, participation switches, attendance, re-accept, crew, lists.

Mounted under the programme tree so every name is a catalogued `events-programme-*` route
(`accounts/programme_route_catalog.py`), classified for claims, delegation, origin scope,
API clients and the native decision there.
"""
from django.urls import path

from .contributions.views_crew import (
    CrewCateringView, CrewDecisionView, CrewDetailView, CrewRemoveView, CrewReorderView, CrewRosterView, CrewSignupView, CrewWithdrawView,
    PublicCrewView,
)
from .hackathons.views_stage_reviews import MyReviewStagesView, MyStageAssignmentsView, MyStageReviewSubmitView
from .hackathons.views_stages import (
    StageApplyView, StageDetailView, StageListView, StagePanelView, StagePreviewView, StageProgressView,
)
from .views_checkin_lists import (
    CheckInListDetailView, CheckInListLookupView, CheckInListReorderView, CheckInListScanUndoView,
    CheckInListScanView, CheckInListsView,
)
from .views_participation import (
    AttendanceMemberView, AttendanceStaffView, ParticipationSettingsView, RegistrationReacceptView,
)

STAGE = "events/<int:pk>/application-stages/<int:stage_id>/"
P = "events-programme-admin-"

ADMIN = [
    path("events/<int:pk>/application-stages/", StageListView.as_view(), name=P + "application-stages"),
    path(STAGE, StageDetailView.as_view(), name=P + "application-stage-detail"),
    path(STAGE + "panel/", StagePanelView.as_view(), name=P + "application-stage-panel"),
    path(STAGE + "assignment-preview/", StagePreviewView.as_view(), name=P + "application-stage-assignment-preview"),
    path(STAGE + "assignment-apply/", StageApplyView.as_view(), name=P + "application-stage-assignment-apply"),
    path(STAGE + "progress/", StageProgressView.as_view(), name=P + "application-stage-progress"),
    path("my-application-reviews/", MyReviewStagesView.as_view(), name=P + "my-application-reviews"),
    path(STAGE + "my-reviews/", MyStageAssignmentsView.as_view(), name=P + "application-stage-my-reviews"),
    path(STAGE + "my-reviews/<int:assignment_id>/", MyStageReviewSubmitView.as_view(),
         name=P + "application-stage-review-submit"),
    path("events/<int:pk>/participation-settings/", ParticipationSettingsView.as_view(),
         name=P + "participation-settings"),
    path("events/<int:pk>/attendance-confirmation/", AttendanceStaffView.as_view(), name=P + "attendance-confirmation"),
    path("events/<int:pk>/registrations/<int:registration_id>/reaccept/", RegistrationReacceptView.as_view(),
         name=P + "registration-reaccept"),
    path("events/<int:pk>/crew/", CrewRosterView.as_view(), name=P + "crew"),
    path("events/<int:pk>/crew/catering/", CrewCateringView.as_view(), name=P + "crew-catering"),
    path("events/<int:pk>/crew/reorder/", CrewReorderView.as_view(), name=P + "crew-reorder"),
    path("events/<int:pk>/crew/<int:crew_id>/", CrewDetailView.as_view(), name=P + "crew-detail"),
    path("events/<int:pk>/crew/<int:crew_id>/decide/", CrewDecisionView.as_view(), name=P + "crew-decide"),
    path("events/<int:pk>/crew/<int:crew_id>/remove/", CrewRemoveView.as_view(), name=P + "crew-remove"),
    path("events/<int:pk>/checkin-lists/", CheckInListsView.as_view(), name=P + "checkin-lists"),
    path("events/<int:pk>/checkin-lists/<int:list_id>/", CheckInListDetailView.as_view(), name=P + "checkin-list-detail"),
    path("events/<int:pk>/checkin-lists/<int:list_id>/lookup/", CheckInListLookupView.as_view(),
         name=P + "checkin-list-lookup"),
    path("events/<int:pk>/checkin-lists/<int:list_id>/scan/", CheckInListScanView.as_view(), name=P + "checkin-list-scan"),
    path("events/<int:pk>/checkin-lists/reorder/", CheckInListReorderView.as_view(), name=P + "checkin-list-reorder"),
    path("events/<int:pk>/checkin-lists/<int:list_id>/scan/<int:scan_id>/undo/", CheckInListScanUndoView.as_view(),
         name=P + "checkin-list-scan-undo"),
]

MEMBER = [
    path("events/<int:pk>/attendance/", AttendanceMemberView.as_view(), name="events-programme-member-attendance"),
    path("events/<int:pk>/crew-signup/", CrewSignupView.as_view(), name="events-programme-member-crew-signup"),
    path("events/<int:pk>/crew-signup/withdraw/", CrewWithdrawView.as_view(),
         name="events-programme-member-crew-withdraw"),
]

PUBLIC = [
    path("event-programmes/<uuid:public_token>/crew/", PublicCrewView.as_view(), name="events-programme-public-crew"),
]
