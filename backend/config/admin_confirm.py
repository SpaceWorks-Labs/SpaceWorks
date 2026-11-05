"""Dangerous /control/ list actions are labelled and confirmed (#188).

Most bulk actions with a lasting effect already render their own confirmation page
(archive, purge, suspend, disable account, reset two-step, ...). The ones below acted the
moment the button was pressed. They now show one confirmation page that names the
selected rows and says what will happen; confirming re-posts the same selection. The
action itself, its permission, its re-authentication step and its audit row are unchanged.
"""

from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.template.response import TemplateResponse

CONFIRMED_FIELD = "control_confirmed"

# "app_label.model_name.action": (what happens, irreversible?)
DANGEROUS_ACTIONS = {
    "accounts.user.reset_password_selected": (
        "Each selected account gets a new temporary password at once; the old one stops working.", True),
    "boxes.qrcode.revoke_selected": (
        "The selected QR codes stop working at once. A revoked code cannot be reactivated.", True),
    "machines.machine.retire_selected": (
        "The selected machines leave booking and job lists until you reactivate them.", False),
    "backup.backupdestination.retire_destinations": (
        "Off-site copies to the selected destinations stop and their stored credentials are wiped.", True),
    "apiclients.apikeyrequest.approve_and_issue": (
        "Working API credentials are issued to each requesting space.", False),
    "apiclients.apikeyrequest.reject_selected": ("The selected API key requests are closed as rejected.", True),
    "makerspaces.subdomainrequest.approve_and_provision": (
        "Each space gets its web address now, including its certificate.", False),
    "makerspaces.subdomainrequest.reject_selected": ("The selected web address requests are closed as rejected.", True),
    "operations.stocktakesession.apply_adjustments_selected": (
        "Every counted item's stock is changed to match the count.", True),
    "tenant_migration.selfhostmoverequest.approve_moves": (
        "The selected spaces may then be exported to their own server.", False),
    "tenant_migration.selfhostmoverequest.reject_moves": ("The selected move requests are closed as rejected.", True),
    "space_controls.platformannouncement.cancel_announcements": (
        "The selected banners stop showing at once. Emails already sent cannot be recalled.", True),
}


def _key(model_admin, action):
    return f"{model_admin.model._meta.label_lower}.{action}"


class ConfirmDangerousActionsMixin:
    def get_actions(self, request):
        actions = super().get_actions(request)
        for name, (func, action_name, description) in list(actions.items()):
            rule = DANGEROUS_ACTIONS.get(_key(self, name))
            if rule is not None:
                suffix = " (cannot be undone)" if rule[1] else " (asks you to confirm)"
                actions[name] = (func, action_name, f"{description}{suffix}")
        return actions

    def response_action(self, request, queryset):
        action = request.POST.get("action", "")
        rule = DANGEROUS_ACTIONS.get(_key(self, action))
        if rule is None or request.POST.get(CONFIRMED_FIELD) == "yes":
            return super().response_action(request, queryset)
        selected = request.POST.getlist(ACTION_CHECKBOX_NAME)
        if not selected and request.POST.get("select_across") != "1":
            return super().response_action(request, queryset)  # Django's own "nothing selected" path
        rows = self.get_queryset(request).filter(pk__in=selected) if selected else queryset
        posted = [(key, value) for key in request.POST if key != "csrfmiddlewaretoken"
                  for value in request.POST.getlist(key)]
        return TemplateResponse(request, "admin/control/confirm_action.html", {
            **self.admin_site.each_context(request),
            "title": "Please confirm", "opts": self.model._meta,
            "action_label": dict((name, desc) for name, (_f, _n, desc) in self.get_actions(request).items()).get(action, action),
            "warning": rule[0], "irreversible": rule[1], "rows": list(rows[:50]),
            "row_count": rows.count(), "posted": posted, "confirmed_field": CONFIRMED_FIELD,
        })
