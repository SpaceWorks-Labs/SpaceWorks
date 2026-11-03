"""Events' member-facing surface, mounted under `/api/v1/member/`.

Separate from `urls_admin.py` (staff) and `urls_public.py` (the public catalogue) for one
reason that is easy to get wrong: this route has to be **withdrawn by an events
tombstone**. Declaring it in `apps/makerspaces/urls.py` -- where the rest of the
`member/` surface lives -- would leave it resolving, and advertised in the OpenAPI schema,
on a deployment that ships no events app at all. `config.urls.separable` splices this
urlconf in place instead, exactly as it does for the other two.
"""

from django.urls import include, path
from apps.events.views_ticket import MemberEventTicketView, MemberEventTicketPngView

from apps.events.views_checkin import EventCheckInQrView
from apps.events.views_registration_cancel import MemberEventRegistrationCancelView
from apps.events.views_feedback_member import (
    MemberEventCertificateDownloadView,
    MemberEventFeedbackView,
)
from apps.events.views_member_events import (
    MemberCollaborativeEventListView,
    MemberCollaborativeEventRegistrationView,
)
from apps.events.views_calendar import MemberEventCalendarFeedView, MemberEventCalendarView

from .views_registration_calendar import MemberEventRegistrationCalendarView
from .views_event_history import MemberEventHistoryView
from .views_speakers import MemberSpeakerClaimView

urlpatterns = [
    path("makerspaces/<int:makerspace_id>/event-history/", MemberEventHistoryView.as_view(),
         name="member-event-history"),
    path("event-speaker-claims/", MemberSpeakerClaimView.as_view(), name="member-event-speaker-claim"),
    path("makerspaces/<int:makerspace_id>/event-registrations/<int:pk>/calendar.ics",
         MemberEventRegistrationCalendarView.as_view(), name="member-event-registration-calendar"),
    path('makerspaces/<int:makerspace_id>/event-registrations/<int:pk>/ticket/',
         MemberEventTicketView.as_view(), name='member-event-ticket'),
    path('makerspaces/<int:makerspace_id>/event-registrations/<int:pk>/ticket.png',
         MemberEventTicketPngView.as_view(), name='member-event-ticket-png'),
    path(
        'makerspaces/<int:makerspace_id>/event-registrations/<int:pk>/cancel/',
        MemberEventRegistrationCancelView.as_view(),
        name='member-event-registration-cancel',
    ),
    path(
        'makerspaces/<int:makerspace_id>/event-registrations/calendar.ics',
        MemberEventCalendarView.as_view(),
        name='member-event-calendar',
    ),
    path(
        'makerspaces/<int:makerspace_id>/event-calendar-feed/',
        MemberEventCalendarFeedView.as_view(),
        name='member-event-calendar-feed',
    ),
    path(
        'makerspaces/<int:makerspace_id>/collaborative-events/',
        MemberCollaborativeEventListView.as_view(),
        name='member-collaborative-events',
    ),
    path(
        'makerspaces/<int:makerspace_id>/collaborative-events/<int:pk>/register/',
        MemberCollaborativeEventRegistrationView.as_view(),
        name='member-collaborative-event-register',
    ),
    path(
        'makerspaces/<int:makerspace_id>/event-registrations/<int:pk>/qr',
        EventCheckInQrView.as_view(),
        name='member-event-checkin-qr',
    ),
    path(
        'makerspaces/<int:makerspace_id>/event-registrations/<int:pk>/feedback/',
        MemberEventFeedbackView.as_view(),
        name='member-event-feedback',
    ),
    path(
        'makerspaces/<int:makerspace_id>/event-certificates/<int:pk>/download/',
        MemberEventCertificateDownloadView.as_view(),
        name='member-event-certificate-download',
    ),
    # Owner stage forms, responses and stage-file uploads (staged_forms/urls_member.py).
    path("makerspaces/<int:makerspace_id>/events/<int:pk>/", include("apps.events.staged_forms.urls_member")),
    # Release 2 L6: ticket orders, seat claims, transfers, type changes and series passes.
    path("", include("apps.events.urls_ticketing_member")),
]
