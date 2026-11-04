from django.urls import path
from .urls_website import public_patterns as website_patterns

from apps.events.views_public import (
    PublicEventListView,
    PublicEventRegistrationView,
)
from apps.events.views_feedback_public import PublicEventFeedbackView
from apps.events.views_calendar import (
    PublicEventCalendarView,
    PublicMemberEventCalendarFeedView,
)


from .views_public_detail import PublicEventDetailView
from .views_ticketing_shop import PublicEventTicketShopView

from .views_organization_audience import EventOrganizationEligibilityView
from .views_event_share import PublicEventShareImageView

urlpatterns = [
    *website_patterns,
    path("<slug:makerspace_slug>/events/<uuid:public_token>/share.png", PublicEventShareImageView.as_view(),
         name="public-event-share-image"),
    path("<slug:makerspace_slug>/events/<uuid:public_token>/eligibility/", EventOrganizationEligibilityView.as_view(), name="public-event-organization-eligibility"),
    path("<slug:makerspace_slug>/events/<uuid:public_token>/", PublicEventDetailView.as_view(), name="public-event-detail"),
    path("<slug:makerspace_slug>/events/<uuid:public_token>/tickets/", PublicEventTicketShopView.as_view(),
         name="public-event-ticket-shop"),
    path(
        '<slug:makerspace_slug>/events/',
        PublicEventListView.as_view(),
        name='public-event-list',
    ),
    path(
        '<slug:makerspace_slug>/events/<uuid:public_token>/register/',
        PublicEventRegistrationView.as_view(),
        name='public-event-register',
    ),
    path(
        '<slug:makerspace_slug>/events/<uuid:public_token>/feedback/',
        PublicEventFeedbackView.as_view(),
        name='public-event-feedback',
    ),
    path(
        '<slug:makerspace_slug>/events/<uuid:public_token>/calendar.ics',
        PublicEventCalendarView.as_view(),
        name='public-event-calendar',
    ),
    path(
        '<slug:makerspace_slug>/event-calendar/<str:raw_token>.ics',
        PublicMemberEventCalendarFeedView.as_view(),
        name='public-event-calendar-feed',
    ),
]
