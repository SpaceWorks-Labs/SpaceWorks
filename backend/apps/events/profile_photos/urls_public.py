from django.urls import path
from .views_public import PublicCardPhotoView

urlpatterns = [path("event-programmes/<uuid:public_token>/member-cards/<uuid:card_public_id>/photo/",
                    PublicCardPhotoView.as_view(), name="events-programme-public-member-card-photo")]
