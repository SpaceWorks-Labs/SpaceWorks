"""Staff sponsors: sponsors, tiers, perk checklists, sponsorship charges and event links.

Finance staff only, like donations (#100): reading needs `view_finance`, every write also
`record_payment`. Contact fields are scoped PII, masked for a superadmin without a window.
"""

from django.utils.translation import gettext
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.audit import services as audit
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.tenant_migration.gate_runtime import tenant_write

from . import serializers_sponsors as s
from . import sponsors
from .gates import SPONSORS, scoped, staff_space
from .models import Sponsor, SponsorEventLink, SponsorPerk, SponsorshipCharge, SponsorTier

ERRORS = {400: OpenApiResponse(ErrorSerializer), 403: OpenApiResponse(ErrorSerializer),
          404: OpenApiResponse(ErrorSerializer), 409: OpenApiResponse(ErrorSerializer)}
TAG = ["Sponsors (staff)"]


def _row(request, model, makerspace_id, pk, *, record=False, label="Not found."):
    staff_space(request.user, makerspace_id, SPONSORS, record=record)
    row = scoped(request.user, model, makerspace_id).filter(pk=pk).first()
    if row is None:
        raise NotFound(label)
    return row


def _ctx(request):
    return {"request": request}


class SponsorListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAG, summary="Sponsors", responses={200: s.SponsorSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        staff_space(request.user, makerspace_id, SPONSORS)
        rows = scoped(request.user, Sponsor, makerspace_id).select_related("tier")
        if request.query_params.get("archived") != "1":
            rows = rows.filter(archived_at__isnull=True)
        return Response(s.SponsorSerializer(rows[:500], many=True, context=_ctx(request)).data)

    @extend_schema(tags=TAG, summary="Add a sponsor", description="Audited `sponsor.created`; a tier copies its perks.",
                   request=s.SponsorSerializer, responses={201: s.SponsorSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, SPONSORS, record=True)
        payload = s.SponsorSerializer(data=request.data, context=_ctx(request))
        payload.is_valid(raise_exception=True)
        with tenant_write(space.pk):
            row = sponsors.save_sponsor(space, actor=request.user, data=payload.validated_data)
        return Response(s.SponsorSerializer(row, context=_ctx(request)).data, status=201)


class SponsorDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAG, summary="One sponsor", responses={200: s.SponsorSerializer, **ERRORS})
    def get(self, request, makerspace_id, pk):
        return Response(s.SponsorSerializer(_row(request, Sponsor, makerspace_id, pk), context=_ctx(request)).data)

    @extend_schema(tags=TAG, summary="Change a sponsor", description="Audited `sponsor.updated`.",
                   request=s.SponsorSerializer, responses={200: s.SponsorSerializer, **ERRORS})
    def patch(self, request, makerspace_id, pk):
        row = _row(request, Sponsor, makerspace_id, pk, record=True)
        payload = s.SponsorSerializer(row, data=request.data, partial=True, context=_ctx(request))
        payload.is_valid(raise_exception=True)
        with tenant_write(row.makerspace_id):
            row = sponsors.save_sponsor(row.makerspace, actor=request.user, data=payload.validated_data, sponsor=row)
        return Response(s.SponsorSerializer(row, context=_ctx(request)).data)


class SponsorArchiveView(APIView):
    permission_classes = [IsActiveStaff]
    archived = True

    @extend_schema(tags=TAG, summary="Archive or restore a sponsor (kept; off the wall while archived)",
                   description="Audited `sponsor.archived` / `sponsor.restored`.", request=None,
                   responses={200: s.SponsorSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk):
        row = _row(request, Sponsor, makerspace_id, pk, record=True)
        with tenant_write(row.makerspace_id):
            row = sponsors.archive_sponsor(row, actor=request.user, archived=self.archived)
        return Response(s.SponsorSerializer(row, context=_ctx(request)).data)


class TierListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAG, summary="Sponsor tiers", responses={200: s.TierSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        staff_space(request.user, makerspace_id, SPONSORS)
        return Response(s.TierSerializer(scoped(request.user, SponsorTier, makerspace_id), many=True).data)

    @extend_schema(tags=TAG, summary="Add a sponsor tier", description="Audited `sponsor.tier_created`.",
                   request=s.TierSerializer, responses={201: s.TierSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        from .services import space_currency

        space = staff_space(request.user, makerspace_id, SPONSORS, record=True)
        payload = s.TierSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        with tenant_write(space.pk):
            row = payload.save(makerspace=space, currency=space_currency(space))
            audit.record(request.user, "sponsor.tier_created", makerspace=space, target=row, meta={"tier_id": row.pk})
        return Response(s.TierSerializer(row).data, status=201)


class TierDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAG, summary="Change a sponsor tier", description="Audited `sponsor.tier_updated`.",
                   request=s.TierSerializer, responses={200: s.TierSerializer, **ERRORS})
    def patch(self, request, makerspace_id, pk):
        row = _row(request, SponsorTier, makerspace_id, pk, record=True)
        payload = s.TierSerializer(row, data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        with tenant_write(row.makerspace_id):
            row = payload.save()
            audit.record(request.user, "sponsor.tier_updated", makerspace=row.makerspace, target=row,
                         meta={"tier_id": row.pk, "fields": sorted(payload.validated_data)})
        return Response(s.TierSerializer(row).data)


class PerkListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAG, summary="Perks: tier templates and sponsor checklists",
                   responses={200: s.PerkSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        staff_space(request.user, makerspace_id, SPONSORS)
        rows = scoped(request.user, SponsorPerk, makerspace_id).select_related("fulfilled_by")
        if str(request.query_params.get("sponsor") or "").isdigit():
            rows = rows.filter(sponsor_id=int(request.query_params["sponsor"]))
        return Response(s.PerkSerializer(rows[:500], many=True).data)

    @extend_schema(tags=TAG, summary="Add a perk to a tier (template) or a sponsor (checklist)",
                   description="Audited `perk.created`; a tier perk is copied to that tier's sponsors.",
                   request=s.PerkSerializer, responses={201: s.PerkSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, SPONSORS, record=True)
        payload = s.PerkSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        with tenant_write(space.pk):
            row = sponsors.save_perk(space, actor=request.user, data=payload.validated_data)
            if row.tier_id:
                for sponsor in Sponsor.objects.filter(tier_id=row.tier_id, archived_at__isnull=True):
                    sponsors.copy_tier_perks(sponsor, actor=request.user)
        return Response(s.PerkSerializer(row).data, status=201)


class PerkFulfilView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAG, summary="Tick or untick a sponsor's perk",
                   description="Audited `perk.fulfilled` / `perk.reopened`; records who and when.",
                   request=s.FulfilSerializer, responses={200: s.PerkSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk):
        row = _row(request, SponsorPerk, makerspace_id, pk, record=True, label="Perk not found.")
        payload = s.FulfilSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        with tenant_write(row.makerspace_id):
            row = sponsors.fulfil_perk(row, actor=request.user, **payload.validated_data)
        return Response(s.PerkSerializer(row).data)


class ChargeListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAG, summary="A sponsor's agreed payments", responses={200: s.ChargeSerializer(many=True),
                                                                             **ERRORS})
    def get(self, request, makerspace_id, pk):
        sponsor = _row(request, Sponsor, makerspace_id, pk)
        return Response(s.ChargeSerializer(sponsor.charges.all(), many=True).data)

    @extend_schema(tags=TAG, summary="Record what a sponsor agreed to pay",
                   description="Raises one account-less charge (subject `sponsorship`) staff settle offline or send "
                               "as a pay link. Audited `sponsor.charge_raised`.",
                   request=s.ChargeCreateSerializer, responses={201: s.ChargeSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk):
        sponsor = _row(request, Sponsor, makerspace_id, pk, record=True)
        payload = s.ChargeCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        with tenant_write(sponsor.makerspace_id):
            charge, _payment = sponsors.raise_charge(sponsor, actor=request.user, **payload.validated_data)
        return Response(s.ChargeSerializer(charge).data, status=201)


class ChargeReturnSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="", max_length=500)


class ChargeReturnView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAG, summary="Open a case to return a sponsor's payment",
                   description="A refund case in area `donations`; staff approve it in the refund-case queue (#59).",
                   request=ChargeReturnSerializer, responses={200: s.ChargeSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk):
        from apps.payments.models import Payment

        from .refunds import open_return_case

        charge = _row(request, SponsorshipCharge, makerspace_id, pk, record=True, label="Charge not found.")
        payment = Payment.objects.get(makerspace_id=makerspace_id, subject_type="sponsorship", subject_id=charge.pk)
        with tenant_write(charge.makerspace_id):
            body = ChargeReturnSerializer(data=request.data)
            body.is_valid(raise_exception=True)
            open_return_case(payment, actor=request.user, reason=body.validated_data["reason"])
        return Response(s.ChargeSerializer(charge).data)


class EventLinkListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAG, summary="Events this sponsor is linked to",
                   responses={200: s.EventLinkSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id, pk):
        sponsor = _row(request, Sponsor, makerspace_id, pk)
        rows = sponsor.event_links.select_related("event_sponsor__event")
        return Response(s.EventLinkSerializer(rows, many=True).data)

    @extend_schema(tags=TAG, summary="Link a sponsor to an event's own sponsor row (never a copy)",
                   description="Audited `sponsor.event_linked`. 400 `event_sponsor_linked` when it is someone else's.",
                   request=s.EventLinkCreateSerializer, responses={201: s.EventLinkSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk):
        from apps.events.models import EventSponsor

        sponsor = _row(request, Sponsor, makerspace_id, pk, record=True)
        payload = s.EventLinkCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        event_sponsor = EventSponsor.objects.filter(pk=payload.validated_data["event_sponsor"],
                                                    makerspace_id=makerspace_id).first()
        if event_sponsor is None:
            raise NotFound(gettext("Event sponsor not found."))
        with tenant_write(sponsor.makerspace_id):
            link = sponsors.link_event_sponsor(sponsor, event_sponsor, actor=request.user)
        return Response(s.EventLinkSerializer(link).data, status=201)


class EventSponsorChoicesView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAG, summary="This space's event-level sponsors, to link a sponsor to",
                   responses={200: s.EventSponsorChoiceSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        from apps.events.models import EventSponsor

        staff_space(request.user, makerspace_id, SPONSORS)
        rows = rbac.scope_by_action(request.user, rbac.Action.VIEW_FINANCE, EventSponsor.objects.filter(
            makerspace_id=makerspace_id), field="makerspace_id").select_related("event").order_by("-event__starts_at", "pk")
        linked = dict(SponsorEventLink.objects.filter(makerspace_id=makerspace_id).values_list(
            "event_sponsor_id", "sponsor_id"))
        return Response(s.EventSponsorChoiceSerializer([{
            "id": row.pk, "label": row.label, "event_id": row.event_id, "event_title": row.event.title,
            "active": row.active, "linked_sponsor_id": linked.get(row.pk)} for row in rows[:300]], many=True).data)


class EventLinkDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAG, summary="Unlink a sponsor from an event", description="Audited `sponsor.event_unlinked`.",
                   request=None, responses={204: None, **ERRORS})
    def delete(self, request, makerspace_id, pk):
        link = _row(request, SponsorEventLink, makerspace_id, pk, record=True, label="Link not found.")
        with tenant_write(link.makerspace_id):
            sponsors.unlink_event_sponsor(link, actor=request.user)
        return Response(status=204)
