"""Lane A URL list. G mounts only after policy and model registration."""
from django.urls import path
from .views_config import ConfigView
from .views_review import ApplicationListView, ReviewAssignView, ReviewView
from .views_decisions import DecisionPreviewView, DecisionStageView, DecisionReleaseView, DecisionCancelView, DecisionDetailView, ExtendRsvpView, StaffRsvpView

urlpatterns = [
    path("events/<int:pk>/hackathon/", ConfigView.as_view(), name="events-programme-admin-hackathon"),
    path("events/<int:pk>/applications/", ApplicationListView.as_view(), name="events-programme-admin-applications"),
    path("events/<int:pk>/application-review/assign/", ReviewAssignView.as_view(), name="events-programme-admin-application-review-assign"),
    path("events/<int:pk>/application-reviews/<int:review_id>/", ReviewView.as_view(), name="events-programme-admin-application-reviews"),
    path("events/<int:pk>/application-decisions/preview/", DecisionPreviewView.as_view(), name="events-programme-admin-application-decisions-preview"),
    path("events/<int:pk>/application-decisions/stage/", DecisionStageView.as_view(), name="events-programme-admin-application-decisions-stage"),
    path("events/<int:pk>/application-decisions/release/", DecisionReleaseView.as_view(), name="events-programme-admin-application-decisions-release"),
    path("events/<int:pk>/application-decisions/cancel/", DecisionCancelView.as_view(), name="events-programme-admin-application-decisions-cancel"),
    path("events/<int:pk>/application-decisions/<int:batch_id>/", DecisionDetailView.as_view(), name="events-programme-admin-application-decisions-detail"),
    path("events/<int:pk>/applications/<int:application_id>/extend-rsvp/", ExtendRsvpView.as_view(), name="events-programme-admin-applications-extend-rsvp"),
    path("events/<int:pk>/applications/<int:application_id>/rsvp-on-behalf/", StaffRsvpView.as_view(), name="events-programme-admin-applications-rsvp-on-behalf"),
]
