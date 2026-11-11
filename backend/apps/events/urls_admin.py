"""Events' staff API, relocated out of `admin_api` (plan B5/B6, phase 13).

Separate from `urls_public.py`, which carries the member-facing event list and
registration under `/api/v1/public/`; both are withdrawn by the same tombstone.

Mounted at `admin_api`'s own `/api/v1/admin/` prefix with unchanged paths and route
names, so `origin_scope_routes` (keyed by bare `url_name`), the OpenAPI snapshot and
every `reverse()` are unaffected. No `app_name`, matching `admin_api`.
"""

from django.urls import include, path
from .urls_website import admin_patterns as website_patterns

from apps.events.views_admin import (
    EventCancelView,
    EventEligibleMemberListView,
    EventCompleteView,
    EventDetailView,
    EventListCreateView,
    EventPublishView,
    EventRegistrationApproveView,
    EventRegistrationCancelView,
    EventRegistrationListView,
    EventRegistrationMarkAttendedView,
    EventRegistrationPromoteView,
    EventRegistrationRejectView,
)
from apps.events.views_admin_organized import OrganizedEventListView
from apps.events.views_admin_organized_attendance import OrganizedEventAttendanceView
from apps.events.views_admin_image import EventImageView
from apps.events.views_admin_organizers import EventOrganizerView
from apps.events.views_checkin import EventCheckInResolveView
from apps.events.views_feedback_admin import (
    EventCertificateDownloadView,
    EventCertificateReissueView,
    EventCertificateRevokeView,
    EventFeedbackResponseListView,
    EventFeedbackSurveyCloseView,
    EventFeedbackSurveyOpenView,
    EventFeedbackSurveyView,
    EventRegistrationCorrectAttendanceView,
)
from apps.events.views_collaborators import (
    EventCollaborationInboxView,
    EventCollaborationRemoveView,
    EventCollaborationRespondView,
    EventCollaboratorListView,
)
from apps.events.views_badges import EventBadgePdfView, EventBadgeTemplateView

from .views_loan_context import EventLoanContextView
from .views_booking_decision import EventBookingDecisionView
from .views_booking_decision_replacement import EventBookingReplacementView
from .views_machine_booking_links import EventWorkshopMachineReplacementView, EventWorkshopMachinesView
from .urls_equipment_window import patterns as equipment_window_patterns
from .urls_venue import patterns as venue_patterns
from .urls_registration_queue import patterns as registration_queue_patterns
from .urls_admin_series import patterns as series_patterns

urlpatterns = [
    path("makerspace/<int:makerspace_id>/events/<int:event_id>/booking-link", EventBookingDecisionView.as_view(), name="admin-event-booking-link"),
    path("makerspace/<int:makerspace_id>/events/<int:event_id>/booking-link/replacement", EventBookingReplacementView.as_view(), name="admin-event-booking-replacement"),
    path("makerspace/<int:makerspace_id>/events/<int:event_id>/workshop-machines", EventWorkshopMachinesView.as_view(), name="admin-event-workshop-machines"),
    path("makerspace/<int:makerspace_id>/events/<int:event_id>/workshop-machines/<int:link_id>/replacement", EventWorkshopMachineReplacementView.as_view(), name="admin-event-workshop-machine-replacement"),
    path("makerspace/<int:makerspace_id>/requests/<int:request_id>/event-context", EventLoanContextView.as_view(), name="admin-request-event-context"),
    path("makerspace/<int:makerspace_id>/direct-loans/<int:loan_id>/event-context", EventLoanContextView.as_view(), name="admin-direct-loan-event-context"),
    *equipment_window_patterns,
    *venue_patterns,
    *registration_queue_patterns,
    path("", include("apps.events.urls_credentials")),
    *website_patterns,
    path("", include("apps.events.urls_communications")),
    path("", include("apps.events.urls_staff_tools")),
    path("", include("apps.events.urls_staff_grants")),
    path("", include("apps.events.urls_checkin_admin")),
    path("", include("apps.events.urls_partners")),
    path("", include("apps.events.urls_ticketing")),
    path("", include("apps.events.urls_speakers")),
    path("", include("apps.events.urls_public_surface")),
    # Stage definitions, assignments, milestones and response review (staged_forms/urls_admin.py).
    path("events/<int:pk>/", include("apps.events.staged_forms.urls_admin")),
    *series_patterns,
    path(
        'makerspaces/<int:makerspace_id>/events/',
        EventListCreateView.as_view(),
        name='admin-event-list-create',
    ),
    path(
        'events/<int:pk>/',
        EventDetailView.as_view(),
        name='admin-event-detail',
    ),
    path(
        'events/<int:pk>/publish/',
        EventPublishView.as_view(),
        name='admin-event-publish',
    ),
    path(
        'events/<int:pk>/cancel/',
        EventCancelView.as_view(),
        name='admin-event-cancel',
    ),
    path(
        'events/<int:pk>/complete/',
        EventCompleteView.as_view(),
        name='admin-event-complete',
    ),
    path(
        'events/<int:pk>/image',
        EventImageView.as_view(),
        name='admin-event-image',
    ),
    path(
        'events/<int:pk>/registrations/',
        EventRegistrationListView.as_view(),
        name='admin-event-registration-list',
    ),
    path(
        'events/<int:pk>/organizers/',
        EventOrganizerView.as_view(),
        name='admin-event-organizers',
    ),
    path(
        'events/<int:pk>/badge-template/',
        EventBadgeTemplateView.as_view(),
        name='admin-event-badge-template',
    ),
    path(
        'events/<int:pk>/badges.pdf',
        EventBadgePdfView.as_view(),
        name='admin-event-badges-pdf',
    ),
    path(
        'events/<int:pk>/feedback-survey/',
        EventFeedbackSurveyView.as_view(),
        name='admin-event-feedback-survey',
    ),
    path(
        'events/<int:pk>/feedback-survey/open/',
        EventFeedbackSurveyOpenView.as_view(),
        name='admin-event-feedback-survey-open',
    ),
    path(
        'events/<int:pk>/feedback-survey/close/',
        EventFeedbackSurveyCloseView.as_view(),
        name='admin-event-feedback-survey-close',
    ),
    path(
        'events/<int:pk>/feedback-responses/',
        EventFeedbackResponseListView.as_view(),
        name='admin-event-feedback-responses',
    ),
    path(
        'events/<int:pk>/collaborators/',
        EventCollaboratorListView.as_view(),
        name='admin-event-collaborators',
    ),
    path(
        'event-collaborations/<int:pk>/remove/',
        EventCollaborationRemoveView.as_view(),
        name='admin-event-collaboration-remove',
    ),
    path(
        'makerspaces/<int:makerspace_id>/event-collaborations/',
        EventCollaborationInboxView.as_view(),
        name='admin-event-collaboration-inbox',
    ),
    path(
        'event-collaborations/<int:pk>/respond/',
        EventCollaborationRespondView.as_view(),
        name='admin-event-collaboration-respond',
    ),
    path(
        'events/<int:pk>/eligible-members/',
        EventEligibleMemberListView.as_view(),
        name='admin-event-eligible-members',
    ),
    path(
        'event-registrations/<int:pk>/mark-attended/',
        EventRegistrationMarkAttendedView.as_view(),
        name='admin-event-registration-mark-attended',
    ),
    path(
        'event-registrations/<int:pk>/correct-attendance/',
        EventRegistrationCorrectAttendanceView.as_view(),
        name='admin-event-registration-correct-attendance',
    ),
    path(
        'event-certificates/<int:pk>/download/',
        EventCertificateDownloadView.as_view(),
        name='admin-event-certificate-download',
    ),
    path(
        'event-certificates/<int:pk>/revoke/',
        EventCertificateRevokeView.as_view(),
        name='admin-event-certificate-revoke',
    ),
    path(
        'event-certificates/<int:pk>/reissue/',
        EventCertificateReissueView.as_view(),
        name='admin-event-certificate-reissue',
    ),
    path(
        'event-registrations/<int:pk>/approve/',
        EventRegistrationApproveView.as_view(),
        name='admin-event-registration-approve',
    ),
    path(
        'event-registrations/<int:pk>/cancel/',
        EventRegistrationCancelView.as_view(),
        name='admin-event-registration-cancel',
    ),
    path(
        'event-registrations/<int:pk>/reject/',
        EventRegistrationRejectView.as_view(),
        name='admin-event-registration-reject',
    ),
    path(
        'event-registrations/<int:pk>/promote/',
        EventRegistrationPromoteView.as_view(),
        name='admin-event-registration-promote',
    ),
    path(
        'organized-events/',
        OrganizedEventListView.as_view(),
        name='admin-organized-event-list',
    ),
    path(
        'organized-events/attendance/',
        OrganizedEventAttendanceView.as_view(),
        name='admin-organized-event-attendance',
    ),
]
