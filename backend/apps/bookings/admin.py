from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.accounts.admin_pii_masking import PiiMaskingAdminMixin
from apps.bookings.models import BookableSpace, Booking
from apps.separability.tombstones import app_is_tombstoned
from config.admin_access import SuperuserOnlyModelAdmin
from django.utils.translation import gettext_lazy


class BookableSpaceAdmin(SuperuserOnlyModelAdmin, ModelAdmin):
    list_display = (
        'name',
        'makerspace',
        'is_active',
        'is_public',
        'show_public_availability',
        'show_public_booker_names',
    )
    list_filter = (
        'is_active',
        'is_public',
        'show_public_availability',
        'show_public_booker_names',
    )
    readonly_fields = tuple(field.name for field in BookableSpace._meta.fields)
    fields = readonly_fields

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class BookingAdmin(PiiMaskingAdminMixin, SuperuserOnlyModelAdmin, ModelAdmin):
    pii_extra_fields = ('booker_name',)
    list_display = ('booker_name', 'space', 'starts_at', 'ends_at', 'status')
    list_filter = ('status',)
    readonly_fields = tuple(field.name for field in Booking._meta.fields)
    fields = readonly_fields

    @admin.display(description=gettext_lazy('Name'))
    def booker_name(self, obj):
        return obj.name

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# Registered rather than decorated: the admin screens are runtime surfaces a tombstone
# removes, while the rows stay reachable through the ORM and the purge path. The setting
# is consulted instead of the manifest because admin autodiscovery runs before this
# app's ready(). See separability.tombstones.app_is_tombstoned.
if not app_is_tombstoned("bookings"):
    admin.site.register(BookableSpace, BookableSpaceAdmin)
    admin.site.register(Booking, BookingAdmin)
