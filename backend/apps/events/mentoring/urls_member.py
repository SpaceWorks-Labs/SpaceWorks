from django.urls import path
from . import views_help as h, views_office_hours as o

B = "makerspaces/<int:makerspace_id>/events/<int:pk>/"
N = "events-programme-member-"
urlpatterns = [
    path(B + "office-hours/", o.OfficeHoursListView.as_view(), name=N + "office-hours-list"),
    path(B + "office-hours/bookings/", o.OfficeHoursBookingListView.as_view(), name=N + "office-hours-booking-list"),
    path(B + "office-hours/<int:slot_id>/bookings/", o.OfficeHoursBookingCreateView.as_view(), name=N + "office-hours-booking-create"),
    path(B + "office-hours/bookings/<int:booking_id>/cancel/", o.OfficeHoursBookingCancelView.as_view(), name=N + "office-hours-booking-cancel"),
    path(B + "help/", h.HelpCollectionView.as_view(), name=N + "help-collection"),
    path(B + "help/<int:help_id>/", h.HelpDetailView.as_view(), name=N + "help-detail"),
    path(B + "help/<int:help_id>/comments/", h.HelpCommentsView.as_view(), name=N + "help-comments"),
    path(B + "help/<int:help_id>/cancel/", h.HelpCancelView.as_view(), name=N + "help-cancel"),
    path(B + "help/<int:help_id>/reopen/", h.HelpReopenView.as_view(), name=N + "help-reopen"),
]
