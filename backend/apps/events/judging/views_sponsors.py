"""All participant/contributor consent HTTP routes converge on D's single writer."""

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.response import Response

from .api_common import ERRORS, MemberView, PrivateView, admin_event, paginated, schema
from .ports import runtime
from .serializers import CommandInput, ResultEnvelope, SponsorGrantInput, SponsorProposalInput, validated
from .serializers_read import ConsentCommandRead, ConsentPage, ConsentRead, SponsorSubmissionPage, SponsorSubmissionRead
from .sponsor_consent_workflow import grant_command, project_owner, revoke_command
from .sponsors import resume_download, submissions


class ResumeConsents(MemberView):
    @schema(response=ConsentPage, page=True)
    def get(self, request, pk, makerspace_id):
        self.event(request, pk, makerspace_id)
        runtime().owner_subject(event_id=pk, member_id=request.user.pk)
        context = project_owner(event_id=pk, member_id=request.user.pk)
        return paginated(request, context["consents"], ConsentRead, sponsors=context["sponsors"])

    @schema(request=SponsorGrantInput, response=ConsentCommandRead, status=201,
            description="Explicit owner consent for one named sponsor/current résumé/recruiting purpose. False by default.")
    def post(self, request, pk, makerspace_id):
        self.event(request, pk, makerspace_id)
        subject = runtime().owner_subject(event_id=pk, member_id=request.user.pk)
        return Response(grant_command(pk, actor=request.user, data=request.data, subject=subject), status=201)


class ResumeConsentRevoke(MemberView):
    @schema(request=CommandInput, response=ConsentCommandRead)
    def post(self, request, pk, makerspace_id, consent_id):
        self.event(request, pk, makerspace_id)
        return Response(revoke_command(pk, consent_id, actor=request.user, data=request.data))


class SponsorSubmissions(PrivateView):
    @schema(response=SponsorSubmissionPage, page=True)
    def get(self, request, pk, sponsor_id):
        event = admin_event(request, pk, "view_sponsor_track")
        projects = submissions(request.user, event, sponsor_id)
        from .models_definitions import HackathonPrize
        prizes = list(HackathonPrize.objects.filter(event=event, sponsor_id=sponsor_id,
            winner_selection_mode="sponsor_proposal").order_by("order", "pk").values("id", "version", "name"))
        return paginated(request, projects, SponsorSubmissionRead, prizes=prizes)


class SponsorResumeDownload(PrivateView):
    @extend_schema(tags=["Event programme sponsors"], parameters=[OpenApiParameter("Range", str, OpenApiParameter.HEADER)],
        responses={(200, "application/pdf"): OpenApiResponse(bytes, description="Private PDF; no-store gated stream, never redirect."),
                   (206, "application/pdf"): OpenApiResponse(bytes, description="Single bounded byte range."),
                   416: OpenApiResponse(description="Invalid/unsatisfiable range."), **ERRORS})
    def get(self, request, pk, sponsor_id, participant_asset_id):
        event = admin_event(request, pk, "view_sponsor_track")
        return resume_download(request.user, event, sponsor_id, participant_asset_id, request)


class SponsorWinnerProposal(PrivateView):
    @schema(request=SponsorProposalInput, response=ResultEnvelope, status=201)
    def post(self, request, pk, sponsor_id, prize_id):
        from django.http import Http404
        from .boundary import command, mutation, owned
        from .models_definitions import HackathonPrize
        from .results_workflow import propose_winner_locked
        values = validated(SponsorProposalInput, request.data)
        with mutation(pk, request.user, permission="view_sponsor_track") as (event, locks):
            def run():
                prize = owned(HackathonPrize, pk, prize_id, expected=values["expected_version"])
                if prize.sponsor_id != sponsor_id:
                    raise Http404
                proposal_id = propose_winner_locked(event=event, actor=request.user, prize_id=prize_id,
                    snapshot_id=values["snapshot_id"], locks=locks)
                return {"id": proposal_id, "event_id": pk, "version": 1, "state": "proposed", "allowed_actions": []}
            return Response(command(event, request.user, values, path=f"sponsors/{sponsor_id}/prizes/{prize_id}/propose", run=run), status=201)
