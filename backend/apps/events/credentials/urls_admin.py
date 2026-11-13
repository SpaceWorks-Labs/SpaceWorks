from django.urls import path
from .views import CredentialRotateView, CredentialRevokeView

urlpatterns = [
    path("events/<int:pk>/registrations/<int:registration_id>/credential/rotate/", CredentialRotateView.as_view(),
         name="events-programme-admin-registrations-credential-rotate"),
    path("events/<int:pk>/registrations/<int:registration_id>/credential/revoke/", CredentialRevokeView.as_view(),
         name="events-programme-admin-registrations-credential-revoke"),
]
