"""Public card routes under /api/v1/public/ (release 2 L3)."""
from django.urls import path

from .views_public_verify import CardVerificationView

urlpatterns = [
    path("card-verifications/<str:token>", CardVerificationView.as_view(), name="public-card-verification"),
]
