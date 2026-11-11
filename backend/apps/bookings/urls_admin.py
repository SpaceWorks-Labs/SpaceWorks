"""Bookings' staff API, relocated out of `admin_api` (plan B5/B6, phase 14).

Separate from `urls_public.py`, which carries the member-facing space list,
availability and self-booking under `/api/v1/public/`; both are withdrawn by the same
tombstone.

Mounted at `admin_api`'s own `/api/v1/admin/` prefix with unchanged paths and route
names, so `origin_scope_routes` (keyed by bare `url_name`), the OpenAPI snapshot and
every `reverse()` are unaffected. No `app_name`, matching `admin_api`.

Ordering within the file is the original ordering: `spaces/<pk>/image/presign/` and
`spaces/<pk>/image/finalize/` must stay ahead of `spaces/<pk>/image/`, which would
otherwise never be the winning match for the more specific paths.
"""

from django.urls import path
from .urls_staff_grants import urlpatterns as staff_grant_patterns
from .urls_broadcasts import urlpatterns as broadcast_patterns
from .urls_website import admin_patterns as website_patterns

from apps.bookings.views_admin_bookings import (
    BookingApproveView,
    BookingCancelView,
    BookingCompleteView,
    BookingNoShowView,
    BookingRejectView,
    SpaceBookingListView,
)
from apps.bookings.views_admin_rules import BookableSpaceBookingRulesView
from apps.bookings.views_admin_booking_create import BookingEligibleMembersView
from apps.bookings.views_organization_booking import OrganizationBookingChoicesView, OrganizationBookingCreateView
from apps.bookings.views_admin_booking_quote import StaffBookingQuoteView
from apps.bookings.views_admin_booking_readiness import BookingReadinessView, StaffBookingReadinessView
from apps.bookings.views_admin_booking_availability import StaffBookingAvailabilityView
from apps.bookings.views_admin_machine_types import BookingMachineTypeListView
from apps.bookings.views_admin_spaces import (
    BookableSpaceDeactivateView,
    BookableSpaceDetailView,
    BookableSpaceImageDeleteView,
    BookableSpaceImageFinalizeView,
    BookableSpaceImagePresignView,
    BookableSpaceListCreateView,
)

from .views_recurrence import StaffRecurringBookingView

from .views_staff_tools import BookingCloneView, BookingDetailsEditView, BookingTimeEditView, BookingRestoreView

from .urls_arrival import urlpatterns as arrival_patterns

from .urls_passes import urlpatterns as pass_patterns
from .urls_p2 import admin_patterns as p2_patterns

from .views_loan_context import BookingLoanContextView
from .views_equipment_picker import BookingEquipmentKitsView, BookingEquipmentProductsView
from .views_included_hours import MemberIncludedHoursView
from .views_organization_hours import OrganizationHoursBankView, OrganizationHoursLedgerView

urlpatterns = [
    path("makerspace/<int:makerspace_id>/spaces/<int:space_id>/equipment-request-products", BookingEquipmentProductsView.as_view(), name="booking-equipment-request-products"),
    path("makerspace/<int:makerspace_id>/spaces/<int:space_id>/equipment-kits", BookingEquipmentKitsView.as_view(), name="booking-equipment-kits"),
    path("makerspace/<int:makerspace_id>/requests/<int:request_id>/booking-context", BookingLoanContextView.as_view(), name="admin-request-booking-context"),
    path("makerspace/<int:makerspace_id>/direct-loans/<int:loan_id>/booking-context", BookingLoanContextView.as_view(), name="admin-direct-loan-booking-context"),*p2_patterns, *staff_grant_patterns, *arrival_patterns, *pass_patterns, *broadcast_patterns, *website_patterns,
    path("spaces/<int:pk>/clone/", BookingCloneView.as_view(), name="admin-bookable-space-clone"),
    path("bookings/<int:pk>/details/", BookingDetailsEditView.as_view(), name="admin-booking-details-edit"),
    path("bookings/<int:pk>/time/", BookingTimeEditView.as_view(), name="admin-booking-time-edit"),
    path("bookings/<int:pk>/restore/", BookingRestoreView.as_view(), name="admin-booking-restore"),
    path("makerspace/<int:makerspace_id>/members/<int:user_id>/included-hours", MemberIncludedHoursView.as_view(), name="admin-member-included-hours"),
    path("makerspace/<int:makerspace_id>/organizations/<int:organization_id>/hours-bank/", OrganizationHoursBankView.as_view(), name="admin-org-hours-bank"),
    path("makerspace/<int:makerspace_id>/organizations/<int:organization_id>/hours-bank/ledger/", OrganizationHoursLedgerView.as_view(), name="admin-org-hours-bank-ledger"),
    path('spaces/<int:pk>/recurring-bookings/', StaffRecurringBookingView.as_view(), name='admin-recurring-bookings'),
    path('spaces/<int:pk>/bookings/quote/', StaffBookingQuoteView.as_view(), name='admin-space-booking-quote'),
    path('spaces/<int:pk>/bookings/readiness/', StaffBookingReadinessView.as_view(), name='admin-space-booking-readiness'),
    path('spaces/<int:pk>/bookings/availability/', StaffBookingAvailabilityView.as_view(), name='admin-space-booking-availability'),
    path('bookings/<int:pk>/readiness/', BookingReadinessView.as_view(), name='admin-booking-readiness'),
    path(
        'makerspaces/<int:makerspace_id>/booking-machine-types/',
        BookingMachineTypeListView.as_view(), name='admin-booking-machine-types',
    ),
    path(
        'makerspaces/<int:makerspace_id>/spaces/',
        BookableSpaceListCreateView.as_view(),
        name='admin-bookable-space-list-create',
    ),
    path(
        'spaces/<int:pk>/',
        BookableSpaceDetailView.as_view(),
        name='admin-bookable-space-detail',
    ),
    path(
        'spaces/<int:pk>/deactivate/',
        BookableSpaceDeactivateView.as_view(),
        name='admin-bookable-space-deactivate',
    ),
    path(
        'spaces/<int:pk>/image/presign/',
        BookableSpaceImagePresignView.as_view(),
        name='admin-bookable-space-image-presign',
    ),
    path(
        'spaces/<int:pk>/image/finalize/',
        BookableSpaceImageFinalizeView.as_view(),
        name='admin-bookable-space-image-finalize',
    ),
    path(
        'spaces/<int:pk>/image/',
        BookableSpaceImageDeleteView.as_view(),
        name='admin-bookable-space-image-delete',
    ),
    path(
        'spaces/<int:pk>/bookings/',
        SpaceBookingListView.as_view(),
        name='admin-space-booking-list',
    ),
    path('spaces/<int:pk>/organization-bookings/', OrganizationBookingCreateView.as_view(),
         name='admin-space-organization-booking'),
    path('spaces/<int:pk>/organization-bookings/choices/', OrganizationBookingChoicesView.as_view(),
         name='admin-space-organization-booking-choices'),
    path(
        'spaces/<int:pk>/eligible-members/',
        BookingEligibleMembersView.as_view(),
        name='admin-space-booking-eligible-members',
    ),
    path(
        'spaces/<int:pk>/booking-rules/',
        BookableSpaceBookingRulesView.as_view(),
        name='admin-bookable-space-booking-rules',
    ),
    path(
        'bookings/<int:pk>/approve/',
        BookingApproveView.as_view(),
        name='admin-booking-approve',
    ),
    path(
        'bookings/<int:pk>/reject/',
        BookingRejectView.as_view(),
        name='admin-booking-reject',
    ),
    path(
        'bookings/<int:pk>/cancel/',
        BookingCancelView.as_view(),
        name='admin-booking-cancel',
    ),
    path(
        'bookings/<int:pk>/complete/',
        BookingCompleteView.as_view(),
        name='admin-booking-complete',
    ),
    path(
        'bookings/<int:pk>/no-show/',
        BookingNoShowView.as_view(),
        name='admin-booking-no-show',
    ),
]
