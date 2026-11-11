"""Lane L21b programme routes outside judging: the filtered staff lists and their CSV exports.

Mounted under the programme tree so each name is a catalogued `events-programme-*` route
(`accounts/programme_route_catalog_l21b.py`).
"""
from django.urls import path

from .hackathons.views_mlh_presets import MlhPresetsView
from .views_staff_lists import EventStaffList, EventStaffListExport, EventStaffListPresets

P = "events-programme-admin-"
ADMIN = [
    path("events/<int:pk>/lists/<str:list_key>/", EventStaffList.as_view(), name=P + "staff-list"),
    path("events/<int:pk>/lists/<str:list_key>/export/", EventStaffListExport.as_view(), name=P + "staff-list-export"),
    path("events/<int:pk>/lists/<str:list_key>/presets/", EventStaffListPresets.as_view(), name=P + "staff-list-presets"),
    path("events/<int:pk>/hackathon/mlh-presets/", MlhPresetsView.as_view(), name=P + "hackathon-mlh-presets"),  # EP-9
]
