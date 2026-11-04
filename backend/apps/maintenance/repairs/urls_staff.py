"""Staff routes of the repairs package, mounted at admin_api's `/api/v1/admin/` prefix."""

from django.urls import path

from . import views_contacts as contacts, views_issues as issues, views_maintenance as upkeep, views_staff as staff

M = "makerspaces/<int:makerspace_id>/"

urlpatterns = [
    path(f"{M}issues", issues.IssueListView.as_view(), name="admin-issues"),
    path(f"{M}issues/photos", staff.IssuePhotoUploadView.as_view(), name="admin-issue-photo-upload"),
    path(f"{M}my-jobs", staff.MyRepairJobsView.as_view(), name="admin-my-repair-jobs"),
    path(f"{M}service-state", staff.ServiceStateView.as_view(), name="admin-service-state"),
    path(f"{M}technicians", contacts.TechnicianListView.as_view(), name="admin-technicians"),
    path(f"{M}technicians/candidates", contacts.TechnicianCandidatesView.as_view(), name="admin-technician-candidates"),
    path(f"{M}technician-defaults", contacts.TechnicianDefaultsView.as_view(), name="admin-technician-defaults"),
    path(f"{M}subject-maintenance", upkeep.SubjectScheduleListView.as_view(), name="admin-subject-maintenance"),
    path(f"{M}my-maintenance", upkeep.MyMaintenanceView.as_view(), name="admin-my-maintenance"),
    path(f"{M}room-outages", upkeep.RoomOutageListView.as_view(), name="admin-room-outages"),
    path("issues/<int:pk>", issues.IssueDetailView.as_view(), name="admin-issue-detail"),
    path("issues/<int:pk>/triage", issues.IssueTriageView.as_view(), name="admin-issue-triage"),
    path("issues/<int:pk>/reject", issues.IssueRejectView.as_view(), name="admin-issue-reject"),
    path("issues/<int:pk>/assign", issues.IssueAssignView.as_view(), name="admin-issue-assign"),
    path("issues/<int:pk>/unassign", issues.IssueUnassignView.as_view(), name="admin-issue-unassign"),
    path("issues/<int:pk>/dispatch", issues.IssueDispatchView.as_view(), name="admin-issue-dispatch"),
    path("issues/<int:pk>/start", issues.IssueStartView.as_view(), name="admin-issue-start"),
    path("issues/<int:pk>/work-log", issues.IssueWorkLogView.as_view(), name="admin-issue-work-log"),
    path("issues/<int:pk>/parts", issues.IssuePartsView.as_view(), name="admin-issue-parts"),
    path("issues/<int:pk>/quote", issues.IssueQuoteView.as_view(), name="admin-issue-quote"),
    path("issues/<int:pk>/approve", issues.IssueApproveView.as_view(), name="admin-issue-approve"),
    path("issues/<int:pk>/payout", issues.IssuePayoutView.as_view(), name="admin-issue-payout"),
    path("issues/<int:pk>/fix", issues.IssueFixView.as_view(), name="admin-issue-fix"),
    path("issues/<int:pk>/close", issues.IssueCloseView.as_view(), name="admin-issue-close"),
    path("technicians/<int:pk>", contacts.TechnicianDetailView.as_view(), name="admin-technician-detail"),
    path("technicians/<int:pk>/opt-in-link", contacts.TechnicianOptInLinkView.as_view(),
         name="admin-technician-opt-in-link"),
    path("technicians/<int:pk>/consent", contacts.TechnicianConsentView.as_view(), name="admin-technician-consent"),
    path("subject-maintenance/<int:pk>", upkeep.SubjectScheduleDetailView.as_view(),
         name="admin-subject-maintenance-detail"),
    path("subject-maintenance/<int:pk>/run", upkeep.SubjectScheduleRunView.as_view(),
         name="admin-subject-maintenance-run"),
    path("maintenance/schedules/<int:pk>/run", upkeep.MachineScheduleRunView.as_view(),
         name="admin-machine-maintenance-run"),
]
