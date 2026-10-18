"""Owner history is core and identity-bound, independent of membership/Events."""
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from apps.accounts.account_kind_guards import require_member_account
from apps.makerspaces.servability import servable_q
from .http import PrivateView, obligation, body, paginate
from . import serializers as s
from . import serializers_responses as r
from . import payee_workflow
from .obligation_models import EventPayoutObligation
from .queries import summary


class MemberPayoutListView(PrivateView):
    @extend_schema(tags=["Event payouts"], responses={200: r.PayoutPage, **s.ERRORS})
    def get(self, request):
        from apps.accounts.reauthentication import binding
        binding(request)
        require_member_account(request.user)
        rows = EventPayoutObligation.objects.filter(servable_q("makerspace"), owner_member=request.user).order_by("-created_at", "pk")
        return paginate(request, rows, lambda row: summary(obligation(request, row.pk, owner=True), request=request, owner=True))


class MemberPayoutDetailView(PrivateView):
    @extend_schema(tags=["Event payouts"], responses={200: r.MemberPayoutDetail, **s.ERRORS})
    def get(self, request, obligation_id):
        row = obligation(request, obligation_id, owner=True)
        return Response({**summary(row, request=request, owner=True), "payee": payee_workflow.projection(payee_workflow.current(row)),
            "entries": list(row.entries.values("id", "amount_minor", "currency", "method", "reference", "paid_at", "amends_id", "is_void"))})


class MemberPayeeView(PrivateView):
    @extend_schema(tags=["Event payouts"], responses={200: r.OwnerPayeeContext, **s.ERRORS})
    def get(self, request, obligation_id):
        from .templates import configured_templates, template_descriptors
        row = obligation(request, obligation_id, owner=True)
        return Response({"payee": payee_workflow.projection(payee_workflow.current(row)),
            "templates": sorted(configured_templates(row.makerspace_id)[0]),
            "routing_document_methods": sorted(configured_templates(row.makerspace_id)[1]),
            "template_definitions": template_descriptors(row.makerspace_id) if row.state == "open" else [],
            "disclosure_version": 1, "disclosure": "Routing details are used for this obligation and are visible to finance. "
                "Details and routing documents are purged 30 days after full payment or finance cancellation, unless a finance hold applies. "
                "They are not saved to Saved details."})

    @extend_schema(tags=["Event payouts"], request=s.OwnerPayeeCommand, responses={200: s.PayoutResultSerializer, **s.ERRORS})
    def put(self, request, obligation_id):
        obligation(request, obligation_id, owner=True)
        return Response(payee_workflow.put(request=request, obligation_id=obligation_id, data=body(request, s.OwnerPayeeCommand)))

    @extend_schema(tags=["Event payouts"], request=s.OwnerPayeeDeleteCommand, responses={200: s.PayoutResultSerializer, **s.ERRORS})
    def delete(self, request, obligation_id):
        return Response(payee_workflow.delete(request=request, obligation_id=obligation_id,
            data=body(request, s.OwnerPayeeDeleteCommand)))


class MemberPayeeRevealView(PrivateView):
    @extend_schema(tags=["Event payouts"], request=s.PayeeRevealCommand, responses={200: s.RevealSerializer, **s.ERRORS})
    def post(self, request, obligation_id):
        obligation(request, obligation_id, owner=True)
        return Response(payee_workflow.reveal(request=request, obligation_id=obligation_id,
            data=body(request, s.PayeeRevealCommand), owner=True))
