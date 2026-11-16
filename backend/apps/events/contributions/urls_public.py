from django.urls import path
from .views_public import VolunteerPostingPublicView

urlpatterns = [path("event-programmes/<uuid:public_token>/volunteer-postings/",
    VolunteerPostingPublicView.as_view(), name="events-programme-public-volunteer-postings")]
