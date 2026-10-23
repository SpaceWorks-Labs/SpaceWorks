"""Opt-in finder and private team comments share no contact directory."""
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from . import team_coordination
from .admission_errors import fail
from .api_base import MemberCommandView, paginated
from .api_schema import CommentSerializer, ERRORS, FinderSerializer, paginated_schema
from .api_schema_teams import FinderCardSerializer
from .serializers_commands import CommentInput, FinderInput
from .team_models import HackathonFinderProfile, HackathonTeam, HackathonTeamMember
from .team_projection import profile, project_team, require_own_team


class CommentsView(MemberCommandView):
    @extend_schema(tags=["Event teams"], request=None, responses={200: paginated_schema("ProgrammeCommentPage", CommentSerializer), **ERRORS})
    def get(self, request, makerspace_id, pk, team_id):
        self.member_target(request, makerspace_id, pk)
        team = require_own_team(event_id=pk, team_id=team_id, actor=request.user)
        return paginated(request, team.comments.order_by("created_at", "pk"), team_coordination.project_comment)

    @extend_schema(tags=["Event teams"], request=CommentInput, responses={201: CommentSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk, team_id):
        self.member_target(request, makerspace_id, pk)
        row = team_coordination.comment(event_id=pk, team_id=team_id, actor=request.user, data=self.command_data(request, CommentInput))
        return Response(team_coordination.project_comment(row), status=201)


class FinderView(MemberCommandView):
    @extend_schema(tags=["Event teams"], request=None, responses={200: {"type": "object"}, **ERRORS})
    def get(self, request, makerspace_id, pk):
        event, config = self.member_target(request, makerspace_id, pk)
        if not config.finder_enabled or config.team_mode != "individual_then_team":
            fail("not_found", "Not found.", status=404)
        skills = [v.strip() for v in request.query_params.get("skills", "").split(",") if v.strip()]
        if len(skills) > 20 or any(len(v) > 40 for v in skills):
            fail("invalid_skills", "Use up to 20 short skills.", status=400)
        teams = HackathonTeam.objects.filter(event=event, state="forming", seeking_members=True).order_by("pk")
        active_members = HackathonTeamMember.objects.filter(event=event, state="active").values("member_id")
        eligible_states = ("confirmed", "offered") if config.team_eligibility == "offered" else ("confirmed",)
        people = HackathonFinderProfile.objects.filter(event=event, opted_in=True,
            member__is_active=True, member__access_status="active", member__hackathon_applications__event=event,
            member__hackathon_applications__state__in=eligible_states).exclude(member_id__in=active_members).order_by("pk")
        if skills:
            teams, people = teams.filter(skills__contains=skills), people.filter(skills__contains=skills)
        # Paginate typed IDs first; evaluate live public-profile consent on this page.
        items = FinderRows(teams, people)
        def project(key):
            if key > 0:
                return project_team(teams.get(pk=key), actor=request.user, config=config, finder=True)
            row = people.get(pk=-key)
            return {"id": row.pk, "event_id": event.pk, "version": row.version, "kind": "person",
                    "intro": row.intro, "skills": row.skills, "profile": profile(event.pk, row.member_id)}
        return paginated(request, items, project)


class FinderMeView(MemberCommandView):
    @extend_schema(tags=["Event teams"], request=None, responses={200: FinderSerializer, **ERRORS})
    def get(self, request, makerspace_id, pk):
        event, config = self.member_target(request, makerspace_id, pk)
        if not config.finder_enabled:
            fail("not_found", "Not found.", status=404)
        row = HackathonFinderProfile.objects.filter(event=event, member=request.user).first()
        return Response(team_coordination.project_finder_profile(row, event_id=pk))

    @extend_schema(tags=["Event teams"], request=FinderInput, responses={200: FinderSerializer, **ERRORS})
    def patch(self, request, makerspace_id, pk):
        self.member_target(request, makerspace_id, pk)
        row = team_coordination.finder_profile(event_id=pk, actor=request.user, data=self.command_data(request, FinderInput))
        return Response(team_coordination.project_finder_profile(row, event_id=pk))


class FinderRows:
    """Slice two querysets without loading the entire opted-in directory."""
    def __init__(self, teams, people):
        self.teams, self.people = teams, people
        self.team_count, self.people_count = teams.count(), people.count()

    def __len__(self):
        return self.team_count + self.people_count

    def __getitem__(self, selection):
        if not isinstance(selection, slice) or selection.step not in (None, 1):
            raise TypeError("Finder pages require a contiguous slice.")
        start, stop = selection.start or 0, selection.stop or len(self)
        team_stop = min(stop, self.team_count)
        teams = list(self.teams.values_list("pk", flat=True)[start:team_stop]) if start < team_stop else []
        people_start, people_stop = max(start - self.team_count, 0), max(stop - self.team_count, 0)
        return teams + [-pk for pk in self.people.values_list("pk", flat=True)[people_start:people_stop]]
