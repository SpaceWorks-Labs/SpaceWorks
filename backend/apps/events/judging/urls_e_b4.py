"""Parity E-B4 judging routes: scores CSV, results unpublish and submission reinstate.

Kept apart from `urls.py` (its route manifest is a frozen contract). Mounted under `admin/` by
`events/urls_programme.py`; each name is catalogued in `accounts/programme_route_catalog_e_b4.py`.
"""
from django.urls import path

from apps.events.submissions.views_reinstate import ReinstateView
from .views_e_b4 import ResultsUnpublish, ScoresExport

P = "events-programme-admin-"
ADMIN = [
    path("events/<int:pk>/judging/scores-export/", ScoresExport.as_view(), name=P + "scores-export"),
    path("events/<int:pk>/results/unpublish/", ResultsUnpublish.as_view(), name=P + "results-unpublish"),
    path("events/<int:pk>/submissions/<int:submission_id>/reinstate/", ReinstateView.as_view(),
         name=P + "submissions-reinstate"),
]
