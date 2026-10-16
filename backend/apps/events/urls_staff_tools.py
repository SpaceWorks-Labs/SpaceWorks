from django.urls import path

from apps.events.views_staff_tools import (
    EventDuplicateView, EventFeedbackTemplateView,
    EventRegistrationAnswersView, EventRegistrationRestoreView,
)

urlpatterns = [
    path("events/<int:pk>/duplicate/", EventDuplicateView.as_view(), name="admin-event-duplicate"),
    path("events/<int:pk>/feedback-survey/templates/", EventFeedbackTemplateView.as_view(), name="admin-event-feedback-template"),
    path("event-registrations/<int:pk>/answers/", EventRegistrationAnswersView.as_view(), name="admin-event-registration-answers"),
    path("event-registrations/<int:pk>/restore/", EventRegistrationRestoreView.as_view(), name="admin-event-registration-restore"),
]
