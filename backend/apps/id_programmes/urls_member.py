"""Member programme routes under /api/v1/member/: accepting an emailed invite."""
from django.urls import path

from .views_public import InviteAcceptView

urlpatterns = [
    path("id-programme-invites/accept", InviteAcceptView.as_view(), name="member-id-programme-invite-accept"),
]
