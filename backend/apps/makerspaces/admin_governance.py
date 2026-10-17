"""Slim lifecycle governance visibility without tenant data or inference channels."""

from django.contrib import admin
from django.contrib.admin.views.main import ChangeList
from django.db.models import OuterRef, Q, Subquery
from django.urls import reverse
from django.utils.html import format_html
from django.utils.text import smart_split

from .models import MakerspaceArchiveRequest


class GovernanceChangeList(ChangeList):
    def get_ordering(self, request, queryset):
        # Even a hand-crafted ?o= index cannot order hidden rows by a private column.
        ordering = super().get_ordering(request, queryset)
        safe = [field for field in ordering if isinstance(field, str)
                and field.removeprefix("-") in {"name", "slug", "pk", "-pk"}]
        return safe if any(field.removeprefix("-") in {"name", "slug"} for field in safe) else ["name", "slug", "pk"]


class MakerspaceGovernanceMixin:
    list_display_links = None
    sortable_by = ("governance_name", "slug")
    ordering = ("name", "slug")

    def get_changelist(self, request, **kwargs):
        return GovernanceChangeList

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        # Hidden rows support name/slug search only. Applying tenant-setting filters
        # excludes them wholesale, rather than disclosing a setting through membership.
        neutral = {"q", "o", "p", "all", "e", "_popup", "_to_field"}
        if any(key not in neutral for key in request.GET):
            queryset = queryset.filter(superadmin_access_enabled=True)
        latest = MakerspaceArchiveRequest.objects.filter(
            makerspace_id=OuterRef("pk")
        ).order_by("-requested_at", "-pk")
        return queryset.annotate(governance_request_status=Subquery(latest.values("status")[:1]))

    def get_search_results(self, request, queryset, search_term):
        visible, duplicates = super().get_search_results(
            request, queryset.filter(superadmin_access_enabled=True), search_term,
        )
        hidden = queryset.filter(superadmin_access_enabled=False)
        for term in smart_split(search_term):
            term = term.strip("\"'")
            hidden = hidden.filter(Q(name__icontains=term) | Q(slug__icontains=term))
        return visible | hidden, duplicates

    @admin.display(description="Name", ordering="name")
    def governance_name(self, obj):
        if not obj.superadmin_access_enabled:
            return obj.name
        return format_html('<a href="{}">{}</a>', reverse(
            "admin:makerspaces_makerspace_change", args=[obj.pk]), obj.name)

    @admin.display(description="Lifecycle state")
    def lifecycle_state(self, obj):
        return "Archived" if obj.archived_at else obj.get_lifecycle_state_display()

    @admin.display(description="Archive request")
    def archive_request_status(self, obj):
        return obj.governance_request_status or "none"

    @admin.display(description="Public code")
    def governance_public_code(self, obj):
        return obj.public_code if obj.superadmin_access_enabled else "hidden"

    @admin.display(description="Location")
    def governance_location(self, obj):
        return obj.location if obj.superadmin_access_enabled else "hidden"

    @admin.display(description="Public inventory")
    def governance_public_inventory(self, obj):
        return str(obj.public_inventory_enabled) if obj.superadmin_access_enabled else "hidden"

    @admin.display(description="Frontend domain")
    def governance_domain(self, obj):
        return obj.frontend_domain if obj.superadmin_access_enabled else "hidden"

    @admin.display(description="Hidden from central directory")
    def governance_directory(self, obj):
        return str(obj.hidden_from_central_directory) if obj.superadmin_access_enabled else "hidden"

    @admin.display(description="Updated at")
    def governance_updated(self, obj):
        return obj.updated_at if obj.superadmin_access_enabled else "hidden"
