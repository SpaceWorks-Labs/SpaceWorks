from django.contrib import admin, messages
from django.core.exceptions import ValidationError as DjangoValidationError
from unfold.admin import ModelAdmin

from apps.makerspaces import subdomain_decisions
from apps.makerspaces.models import SubdomainRequest
from config.admin_access import SuperuserOnlyModelAdmin
from django.utils.translation import gettext_lazy


@admin.register(SubdomainRequest)
class SubdomainRequestAdmin(SuperuserOnlyModelAdmin, ModelAdmin):
    actions = ["approve_and_provision", "reject_selected"]
    list_display = (
        "requested_label",
        "makerspace",
        "requested_by",
        "status",
        "created_at",
    )
    list_filter = ("status", "makerspace")
    search_fields = ("requested_label",)
    readonly_fields = (
        "status",
        "requested_label",
        "makerspace",
        "requested_by",
        "decided_by",
        "decided_at",
        "created_at",
        "updated_at",
    )

    @admin.action(description=gettext_lazy("Approve selected subdomain requests and provision"))
    def approve_and_provision(self, request, queryset):
        approved = skipped = 0
        for req in queryset.select_related("makerspace", "requested_by"):
            if req.status != SubdomainRequest.Status.PENDING:
                skipped += 1
                continue
            try:
                subdomain_decisions.approve(request.user, req)
            except DjangoValidationError as exc:
                if req.__class__.objects.filter(pk=req.pk).exclude(status=SubdomainRequest.Status.PENDING).exists():
                    skipped += 1  # decided meanwhile
                    continue
                self.message_user(request, f"{req.pk}: {getattr(exc, 'message', exc)}", level=messages.ERROR)
                continue
            approved += 1

        self.message_user(request, f"Approved {approved}, skipped {skipped}.")

    @admin.action(description=gettext_lazy("Reject selected subdomain requests"))
    def reject_selected(self, request, queryset):
        rejected = 0
        for req in queryset.select_related("makerspace", "requested_by"):
            if req.status != SubdomainRequest.Status.PENDING:
                continue
            try:
                subdomain_decisions.reject(request.user, req)
            except DjangoValidationError:
                continue  # decided meanwhile
            rejected += 1

        self.message_user(request, f"Rejected {rejected}.")
