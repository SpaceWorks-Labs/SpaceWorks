from django.urls import path
from .views import PresentationView, ProfileOptionsView

urlpatterns = [
    path("makerspaces/<int:makerspace_id>/events/<int:pk>/profile-photo-options/", ProfileOptionsView.as_view(),
         name="events-programme-member-profile-photo-options"),
    path("makerspaces/<int:makerspace_id>/events/<int:pk>/presentation/", PresentationView.as_view(),
         name="events-programme-member-presentation-detail"),
]
