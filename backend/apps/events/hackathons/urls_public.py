"""Lane A URL list. G mounts only after policy and model registration."""
from django.urls import path
from .views_application import ContextView

urlpatterns = [
    path("event-programmes/<uuid:public_token>/context/", ContextView.as_view(), name="events-programme-public-context"),
]
