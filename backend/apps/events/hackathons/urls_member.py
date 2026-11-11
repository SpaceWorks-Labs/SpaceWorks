"""Lane A URL list. G mounts only after policy and model registration."""
from django.urls import path
from .views_application import ApplicationView, ApplicationSubmitView, ApplicationWithdrawView, ApplicationRsvpView, ApplicationDateReviewView
from .views_teams import TeamListView, TeamDetailView
from .views_team_commands import InviteView, JoinRequestView, AcceptView, DeclineRequestView, LeaveView, LockView, CancelView, HandoverView, RemoveMemberView
from .views_finder import CommentsView, FinderView, FinderMeView

urlpatterns = [
    path("makerspaces/<int:makerspace_id>/events/<int:pk>/application/", ApplicationView.as_view(), name="events-programme-member-application-detail"),
    path("makerspaces/<int:makerspace_id>/events/<int:pk>/application/submit/", ApplicationSubmitView.as_view(), name="events-programme-member-application-submit"),
    path("makerspaces/<int:makerspace_id>/events/<int:pk>/application/withdraw/", ApplicationWithdrawView.as_view(), name="events-programme-member-application-withdraw"),
    path("makerspaces/<int:makerspace_id>/events/<int:pk>/application/rsvp/", ApplicationRsvpView.as_view(), name="events-programme-member-application-rsvp"),
    path("makerspaces/<int:makerspace_id>/events/<int:pk>/application/date-review/", ApplicationDateReviewView.as_view(), name="events-programme-member-application-date-review"),
    path("makerspaces/<int:makerspace_id>/events/<int:pk>/teams/", TeamListView.as_view(), name="events-programme-member-teams-list"),
    path("makerspaces/<int:makerspace_id>/events/<int:pk>/teams/<int:team_id>/", TeamDetailView.as_view(), name="events-programme-member-teams-detail"),
    path("makerspaces/<int:makerspace_id>/events/<int:pk>/teams/<int:team_id>/invite/", InviteView.as_view(), name="events-programme-member-teams-invite"),
    path("makerspaces/<int:makerspace_id>/events/<int:pk>/teams/<int:team_id>/join-request/", JoinRequestView.as_view(), name="events-programme-member-teams-join-request"),
    path("makerspaces/<int:makerspace_id>/events/<int:pk>/teams/<int:team_id>/accept/", AcceptView.as_view(), name="events-programme-member-teams-accept"),
    path("makerspaces/<int:makerspace_id>/events/<int:pk>/teams/<int:team_id>/decline-request/", DeclineRequestView.as_view(), name="events-programme-member-team-decline-request"),
    path("makerspaces/<int:makerspace_id>/events/<int:pk>/teams/<int:team_id>/leave/", LeaveView.as_view(), name="events-programme-member-teams-leave"),
    path("makerspaces/<int:makerspace_id>/events/<int:pk>/teams/<int:team_id>/lock/", LockView.as_view(), name="events-programme-member-teams-lock"),
    path("makerspaces/<int:makerspace_id>/events/<int:pk>/teams/<int:team_id>/cancel/", CancelView.as_view(), name="events-programme-member-team-cancel"),
    path("makerspaces/<int:makerspace_id>/events/<int:pk>/teams/<int:team_id>/handover/", HandoverView.as_view(), name="events-programme-member-team-handover"),
    path("makerspaces/<int:makerspace_id>/events/<int:pk>/teams/<int:team_id>/remove-member/", RemoveMemberView.as_view(), name="events-programme-member-team-remove-member"),
    path("makerspaces/<int:makerspace_id>/events/<int:pk>/teams/<int:team_id>/comments/", CommentsView.as_view(), name="events-programme-member-team-comments"),
    path("makerspaces/<int:makerspace_id>/events/<int:pk>/team-finder/", FinderView.as_view(), name="events-programme-member-team-finder"),
    path("makerspaces/<int:makerspace_id>/events/<int:pk>/team-finder/me/", FinderMeView.as_view(), name="events-programme-member-team-finder-me"),
]
