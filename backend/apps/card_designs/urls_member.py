"""Holder card routes under /api/v1/member/ (release 2 L3): "My cards"."""
from django.urls import path

from .views_holder import MyCardDownloadView, MyCardEmailView, MyCardRotateLinkView, MyCardSettingsView, MyCardsView
from .views_holder_face import MyCardFaceView, MyCardFontView
from .views_holder_photo import (MyCardJobResultView, MyCardJobView, MyCardPhotoCleanupView, MyCardPhotoDecisionView,
                                 MyCardPhotoDiscardView, MyCardPhotoView, MyCardWalletView)

_CARD = "cards/<str:kind>/<int:card_id>"

urlpatterns = [
    path("cards", MyCardsView.as_view(), name="member-cards"),
    path(f"{_CARD}/download", MyCardDownloadView.as_view(), name="member-card-download"),
    path(f"{_CARD}/face", MyCardFaceView.as_view(), name="member-card-face"),
    path(f"{_CARD}/fonts/<slug:family_slug>/<int:weight>", MyCardFontView.as_view(), name="member-card-font"),
    path(f"{_CARD}/email", MyCardEmailView.as_view(), name="member-card-email"),
    path(f"{_CARD}/settings", MyCardSettingsView.as_view(), name="member-card-settings"),
    path(f"{_CARD}/rotate-link", MyCardRotateLinkView.as_view(), name="member-card-rotate-link"),
    path(f"{_CARD}/photo", MyCardPhotoView.as_view(), name="member-card-holder-photo"),
    path(f"{_CARD}/photo/cleanup", MyCardPhotoCleanupView.as_view(), name="member-card-photo-cleanup"),
    path(f"{_CARD}/photo/accept", MyCardPhotoDecisionView.as_view(), name="member-card-photo-accept"),
    path(f"{_CARD}/photo/discard", MyCardPhotoDiscardView.as_view(), name="member-card-photo-discard"),
    path(f"{_CARD}/wallet/<str:platform>", MyCardWalletView.as_view(), name="member-card-wallet"),
    path("card-jobs/<int:pk>", MyCardJobView.as_view(), name="member-card-job"),
    path("card-jobs/<int:pk>/result", MyCardJobResultView.as_view(), name="member-card-job-result"),
]
