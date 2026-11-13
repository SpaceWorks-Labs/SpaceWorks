"""``/control/`` screens for platform IP access (#62): *IP rules* and *Automatic blocks*.

Superadmin only, behind the control step-up (``reauthentication_control``). Every rule
save and delete and every unblock is an audit row; the metadata never carries a raw
address (an unblock names the block's HMAC key). Automatic blocks never email anyone
(Q14); they expire on their own and the superadmin may lift one early here or with
``manage.py login_security --unblock``.
"""

from django import forms
from django.contrib import admin, messages
from django.utils import timezone
from unfold.admin import ModelAdmin

from apps.accounts import ip_rules
from apps.accounts.ip_rule_edits import LOCKOUT_MESSAGE, unblock, would_lock_out
from apps.accounts.models import IPAccessRule, IPAutoBlock
from apps.audit import services as audit
from config.admin_access import SuperuserOnlyModelAdmin
from django.utils.translation import gettext_lazy
from django.utils.translation import gettext


class IPAccessRuleForm(forms.ModelForm):
    class Meta:
        model = IPAccessRule
        fields = ("cidr", "action", "note", "expires_at")
        help_texts = {
            "cidr": "One address (203.0.113.7) or a network (203.0.113.0/24, 2001:db8::/48).",
            "action": "Allow beats every deny rule and every automatic block. Deny always applies.",
            "expires_at": "Leave empty to keep the rule until it is deleted.",
        }

    editor_address = None  # set by the admin from the request

    def clean_cidr(self):
        try:
            return ip_rules.canonical_cidr(self.cleaned_data["cidr"])
        except ValueError as exc:
            raise forms.ValidationError(gettext("Enter an IP address or a network in CIDR form.")) from exc

    def clean(self):
        cleaned = super().clean()
        replacing = self.instance.cidr if self.instance.pk else None
        if would_lock_out(self.editor_address, cleaned.get("cidr"), cleaned.get("action"), replacing_cidr=replacing):
            raise forms.ValidationError(LOCKOUT_MESSAGE)
        return cleaned


@admin.register(IPAccessRule)
class IPAccessRuleAdmin(SuperuserOnlyModelAdmin, ModelAdmin):
    form = IPAccessRuleForm
    list_display = ("cidr", "action", "note", "expires_at", "created_by", "created_at")
    list_filter = ("action",)
    search_fields = ("cidr", "note")
    readonly_fields = ("created_by", "created_at")

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        from config.client_ip import get_throttle_client_ip

        form.editor_address = ip_rules.parse_address(get_throttle_client_ip(request))
        return form

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        audit.record(request.user, "platform.ip_rule_saved", target=obj, meta={
            "via": "control", "created": not change, "action": obj.action,
            "changed_fields": sorted(form.changed_data or ())})

    def delete_model(self, request, obj):
        self._record_delete(request, obj)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self._record_delete(request, obj)
        super().delete_queryset(request, queryset)
        ip_rules.invalidate()  # a queryset delete sends no post_delete per row

    def _record_delete(self, request, obj):
        audit.record(request.user, "platform.ip_rule_deleted", target=obj,
                     meta={"via": "control", "action": obj.action})


@admin.register(IPAutoBlock)
class IPAutoBlockAdmin(SuperuserOnlyModelAdmin, ModelAdmin):
    list_display = ("network", "blocked_until", "is_active", "created_at")
    ordering = ("-blocked_until",)
    readonly_fields = ("network", "blocked_until", "created_at")
    exclude = ("ip_key",)
    actions = ("unblock_selected",)

    @admin.display(boolean=True, description=gettext_lazy("Blocking now"))
    def is_active(self, obj):
        return obj.blocked_until > timezone.now()

    @admin.action(description=gettext_lazy("Unblock the selected addresses now"))
    def unblock_selected(self, request, queryset):
        count = unblock(request.user, queryset)
        self.message_user(request, f"Unblocked {count} address(es).", level=messages.SUCCESS)

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)  # lifting a block is an audited unblock
        return actions

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
