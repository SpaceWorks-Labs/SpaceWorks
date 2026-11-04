"""Member routes for paid ticketing v2 (release 2 L6), spliced into `urls_member`."""

from django.urls import path

from .views_ticketing_claims import (
    MemberSeriesPassView, TicketClaimView, TicketTransferAcceptView, TicketTransferOfferView, TicketTypeChangeView,
)
from .views_ticketing_orders import (
    MemberEventOrderCreateView, MemberOrderAttendeesView, MemberOrderCancelView, MemberOrderChaseView,
    MemberOrderDetailView, MemberOrderListCreateView, MemberOrderQuoteView, MemberOrderSeatClaimView,
)

_SPACE = "makerspaces/<int:makerspace_id>/"

urlpatterns = [
    path(f"{_SPACE}events/<int:event_id>/orders/quote/", MemberOrderQuoteView.as_view(), name="member-event-order-quote"),
    path(f"{_SPACE}events/<int:event_id>/orders/", MemberEventOrderCreateView.as_view(), name="member-event-orders"),
    path(f"{_SPACE}orders/", MemberOrderListCreateView.as_view(), name="member-orders"),
    path(f"{_SPACE}orders/<int:order_id>/", MemberOrderDetailView.as_view(), name="member-order-detail"),
    path(f"{_SPACE}orders/<int:order_id>/attendees/", MemberOrderAttendeesView.as_view(),
         name="member-order-attendees"),
    path(f"{_SPACE}orders/<int:order_id>/chase/", MemberOrderChaseView.as_view(), name="member-order-chase"),
    path(f"{_SPACE}orders/<int:order_id>/cancel/", MemberOrderCancelView.as_view(), name="member-order-cancel"),
    path(f"{_SPACE}orders/<int:order_id>/seats/<int:seat_id>/claim/", MemberOrderSeatClaimView.as_view(),
         name="member-order-seat-claim"),
    path(f"{_SPACE}event-registrations/<int:pk>/transfer/", TicketTransferOfferView.as_view(),
         name="member-ticket-transfer"),
    path(f"{_SPACE}event-registrations/<int:pk>/change-type/", TicketTypeChangeView.as_view(),
         name="member-ticket-change-type"),
    path(f"{_SPACE}event-series/<int:series_id>/passes/", MemberSeriesPassView.as_view(),
         name="member-series-passes"),
    path("ticket-claims/<str:token>/", TicketClaimView.as_view(), name="member-ticket-claim"),
    path("ticket-transfers/<str:token>/", TicketTransferAcceptView.as_view(), name="member-ticket-transfer-accept"),
]
