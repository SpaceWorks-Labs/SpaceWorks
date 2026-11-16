"""The /control/ fallback for the space controls (#185; the web console is primary, #190).

Each action calls exactly the service the web console calls, so authority, audit and mail
are identical. The reason-bearing actions show a confirmation page first; recent control
re-authentication is enforced by ``MakerspaceAdmin``'s ``RecentReauthenticationAdminMixin``.
"""

from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.core.exceptions import ValidationError as DjangoValidationError
from django.template.response import TemplateResponse
from rest_framework.exceptions import APIException

from . import services_access, services_schedule
from django.utils.translation import gettext_lazy

TEMPLATE = "admin/space_controls/control_confirmation.html"


def _message(exc):
    detail = getattr(exc, "detail", None) or getattr(exc, "messages", None) or str(exc)
    if isinstance(detail, dict):
        detail = detail.get("detail") or " ".join(str(value) for value in detail.values())
    if isinstance(detail, list):
        detail = " ".join(str(value) for value in detail)
    return str(detail)


class MakerspaceSpaceControlsAdminMixin:
    def _run_control(self, request, queryset, *, run, done, action, title, explanation, needs_reason=False):
        spaces = list(queryset)
        if needs_reason and "confirm_control" not in request.POST:
            return TemplateResponse(request, TEMPLATE, {
                **self.admin_site.each_context(request), "title": title, "spaces": spaces,
                "action_name": action, "action_checkbox_name": ACTION_CHECKBOX_NAME, "opts": self.model._meta,
                "needs_reason": True, "explanation": explanation, "submit_label": title,
            })
        reason = request.POST.get("reason", "")
        for space in spaces:
            try:
                run(request.user, space.pk, reason)
            except (APIException, DjangoValidationError) as exc:
                self.message_user(request, f"{space.name}: {_message(exc)}", level=messages.ERROR)
            else:
                self.message_user(request, f"{done} {space.name}.", level=messages.SUCCESS)
        return None

    @admin.action(description=gettext_lazy("Pause (suspend) selected spaces"))
    def suspend_makerspaces(self, request, queryset):
        return self._run_control(
            request, queryset, run=services_access.suspend, done="Paused", action="suspend_makerspaces",
            title="Pause spaces", needs_reason=True,
            explanation="Staff and members see a paused page, public pages go offline, scheduled jobs and "
                        "outbound messages stop. Nothing is deleted. Each Space Manager is emailed.")

    @admin.action(description=gettext_lazy("Unblock selected paused spaces"))
    def unsuspend_makerspaces(self, request, queryset):
        return self._run_control(request, queryset, run=lambda actor, pk, _reason: services_access.unsuspend(actor, pk),
                                 done="Unblocked", action="unsuspend_makerspaces", title="Unblock spaces",
                                 explanation="")

    @admin.action(description=gettext_lazy("Make selected spaces read-only"))
    def read_only_makerspaces(self, request, queryset):
        return self._run_control(
            request, queryset, run=services_access.set_read_only, done="Made read-only",
            action="read_only_makerspaces", title="Make spaces read-only", needs_reason=True,
            explanation="Everyone can view and export, but nothing new can be created. The reason is shown "
                        "in the space's banner and emailed to its Space Managers.")

    @admin.action(description=gettext_lazy("End read-only mode for selected spaces"))
    def lift_read_only_makerspaces(self, request, queryset):
        return self._run_control(request, queryset,
                                 run=lambda actor, pk, _reason: services_access.lift_read_only(actor, pk),
                                 done="Ended read-only mode for", action="lift_read_only_makerspaces",
                                 title="End read-only mode", explanation="")

    @admin.action(description=gettext_lazy("Cancel the scheduled archive or purge of selected spaces"))
    def cancel_makerspace_schedules(self, request, queryset):
        return self._run_control(request, queryset, run=lambda actor, pk, _reason: services_schedule.cancel(actor, pk),
                                 done="Cancelled the schedule of", action="cancel_makerspace_schedules",
                                 title="Cancel schedules", explanation="")


SPACE_CONTROL_ACTIONS = ["suspend_makerspaces", "unsuspend_makerspaces", "read_only_makerspaces",
                         "lift_read_only_makerspaces", "cancel_makerspace_schedules"]
