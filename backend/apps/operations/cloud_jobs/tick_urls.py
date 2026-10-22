"""I includes this at api/v1/internal/free/ only under parsed profile=free."""
from django.urls import path

from .tick_policy import free_profile

app_name = "free_tick"
urlpatterns = []
if free_profile():
    from .tick_views import FreeTickView
    urlpatterns = [path("tick", FreeTickView.as_view(), name="tick")]
