from django.urls import path
from .views_invites import EventInviteListView, EventInviteRevokeView
from .views_ticketing import EventTicketListView, EventPromoListView, EventPromoRevokeView, EventCategoryListView
from .views_ticketing_money import (
    EventPassTypeDetailView, EventPassTypeListView, EventRefundPolicyView, EventVenueFeeChargeView, EventVenueFeeView,
)
from .views_ticketing_staff import (
    EventAddonDetailView, EventAddonListView, EventOrderDetailView, EventOrderListView,
    EventRegistrationCollectPaymentView, EventRegistrationPayLinkView, EventSalesSettingsView,
)

urlpatterns = [
    path("events/<int:pk>/invites/", EventInviteListView.as_view(), name="admin-event-invites"),
    path("event-invites/<int:pk>/revoke/", EventInviteRevokeView.as_view(), name="admin-event-invite-revoke"),
    path("events/<int:pk>/ticket-types/", EventTicketListView.as_view(), name="admin-event-tickets"),
    path("events/<int:pk>/promo-codes/", EventPromoListView.as_view(), name="admin-event-promos"),
    path("event-promos/<int:pk>/revoke/", EventPromoRevokeView.as_view(), name="admin-event-promo-revoke"),
    path("makerspaces/<int:makerspace_id>/event-categories/", EventCategoryListView.as_view(), name="admin-event-categories"),
    # Release 2 L6: paid ticketing v2 and venue fees.
    path("events/<int:pk>/addons/", EventAddonListView.as_view(), name="admin-event-addons"),
    path("event-addons/<int:pk>/", EventAddonDetailView.as_view(), name="admin-event-addon-detail"),
    path("events/<int:pk>/sales-settings/", EventSalesSettingsView.as_view(), name="admin-event-sales-settings"),
    path("events/<int:pk>/orders/", EventOrderListView.as_view(), name="admin-event-orders"),
    path("event-orders/<int:pk>/", EventOrderDetailView.as_view(), name="admin-event-order-detail"),
    path("event-registrations/<int:pk>/collect-payment/", EventRegistrationCollectPaymentView.as_view(),
         name="admin-event-registration-collect-payment"),
    path("event-registrations/<int:pk>/pay-link/", EventRegistrationPayLinkView.as_view(),
         name="admin-event-registration-pay-link"),
    path("events/<int:pk>/refund-policy/", EventRefundPolicyView.as_view(), name="admin-event-refund-policy"),
    path("events/<int:pk>/venue-fee/", EventVenueFeeView.as_view(), name="admin-event-venue-fee"),
    path("events/<int:pk>/venue-fee/charge/", EventVenueFeeChargeView.as_view(), name="admin-event-venue-fee-charge"),
    path("event-series/<int:pk>/pass-types/", EventPassTypeListView.as_view(), name="admin-event-series-pass-types"),
    path("event-pass-types/<int:pk>/", EventPassTypeDetailView.as_view(), name="admin-event-pass-type-detail"),
]
