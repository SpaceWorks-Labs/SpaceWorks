"""/control/: approve, reject and run Space Managers' self-host move requests (#128 C-23).

Superadmin only; every POST passes the /control/ re-authentication step-up. "Run export"
takes the one-shot age public key the TARGET operator supplied (#111 Q7); the download
streams the encrypted archive to the signed-in superadmin only and is audited.
"""
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from rest_framework.exceptions import APIException

from apps.accounts.reauthentication import require_recent_reauth
from apps.accounts.reauthentication_control import RecentReauthenticationAdminMixin
from apps.audit import services as audit

from . import selfhost_move as moves
from .admin import ReadOnlyMigrationAdmin
from .models_selfhost_move import SelfHostMoveRequest
from django.utils.translation import gettext_lazy


class SelfHostMoveRequestAdmin(RecentReauthenticationAdminMixin, ReadOnlyMigrationAdmin):
    list_display = ("makerspace", "status", "requested_by", "requested_at", "decided_at", "exported_at", "move_page")
    list_filter = ("status", "requested_at")
    readonly_fields = tuple(field.name for field in SelfHostMoveRequest._meta.fields if field.name != "artifact_path")
    actions = ("approve_moves", "reject_moves")

    @admin.display(description=gettext_lazy("Export"))
    def move_page(self, obj):
        from django.utils.html import format_html
        return format_html('<a href="{}">Open</a>', reverse("admin:tenant_migration_selfhostmoverequest_run", args=[obj.pk]))

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def get_urls(self):
        view = self.admin_site.admin_view
        return [path("<uuid:pk>/run/", view(self.run_view), name="tenant_migration_selfhostmoverequest_run"),
                *super().get_urls()]

    @admin.action(description=gettext_lazy("Approve the selected move requests"), permissions=["view"])
    def approve_moves(self, request, queryset):
        self._decide(request, queryset, approve=True)

    @admin.action(description=gettext_lazy("Reject the selected move requests"), permissions=["view"])
    def reject_moves(self, request, queryset):
        self._decide(request, queryset, approve=False)

    def _decide(self, request, queryset, *, approve):
        require_recent_reauth(request)
        for move in queryset:
            try:
                moves.decide(request.user, move, approve=approve)
            except APIException as exc:
                self.message_user(request, f"{move.makerspace}: {exc.detail}", messages.ERROR)

    def run_view(self, request, pk):
        if not self.has_view_permission(request):
            raise PermissionDenied()
        move = get_object_or_404(SelfHostMoveRequest.objects.select_related("makerspace"), pk=pk)
        if request.method == "POST":
            response = self._recent_redirect(request)
            if response is not None:
                return response
            require_recent_reauth(request)
            action = request.POST.get("action")
            if action == "download":
                return self._download(request, move)
            try:
                if action == "export":
                    moves.start_export(request.user, move, request.POST.get("recipient", ""))
                    self.message_user(request, "Export started. Refresh this page to follow it.")
                elif action == "discard":
                    moves.discard_artifact(request.user, move)
                    self.message_user(request, "Export file deleted from the server.")
            except APIException as exc:
                self.message_user(request, str(exc.detail), messages.ERROR)
            return redirect(reverse("admin:tenant_migration_selfhostmoverequest_run", args=[move.pk]))
        return TemplateResponse(request, "admin/tenant_migration/selfhost_move.html", {
            **self.admin_site.each_context(request), "title": f"Move {move.makerspace.name} to its own server",
            "move": move, "opts": self.model._meta, "has_file": bool(move.artifact_path),
        })

    def _download(self, request, move):
        if move.status != SelfHostMoveRequest.Status.EXPORTED or not move.artifact_path:
            raise Http404()
        try:
            handle = open(move.artifact_path, "rb")
        except OSError:
            raise Http404() from None
        audit.record(request.user, "selfhost_move.downloaded", makerspace=move.makerspace, target=move,
                     meta={"status": move.status, "artifact_sha256": move.artifact_sha256})
        return FileResponse(handle, as_attachment=True, filename=f"{move.makerspace.slug}-move.tar.age",
                            content_type="application/octet-stream")
