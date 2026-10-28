"""Superadmin-only structured capability controls for Makerspace admin."""

from django import forms
from django.contrib import messages

from apps.audit import services as audit
from apps.makerspaces.capabilities import FEATURE_DEFINITIONS, validate_capabilities
from apps.makerspaces.admin_images import MakerspaceAdminForm as ImageMakerspaceAdminForm
from apps.makerspaces.admin_capability_completion import FEATURES, complete_selection, matrix_rules
from apps.makerspaces.module_registry import BY_KEY, MODULES, module_available
from apps.makerspaces.request_access import effective_policy
from apps.makerspaces.admin_security import MakerspaceSecurityAdminMixin
from apps.makerspaces.security_settings_registry import is_security_feature


def _labels(keys):
    return ", ".join(BY_KEY[key].label if key in BY_KEY else FEATURES[key].label if key in FEATURES else key
                     for key in keys)


class CapabilityMatrixWidget(forms.CheckboxSelectMultiple):
    template_name = "admin/makerspaces/capability_matrix.html"

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        # The server's own completion rules as data, so the script ticks and unticks
        # exactly what clean_capabilities would. No checkbox is ever disabled: a disabled
        # checkbox is omitted from POST, which would silently clear it on save.
        context["capability_rules"] = matrix_rules()
        return context


def _module_label(definition):
    # Core is labelled, not disabled: a disabled checkbox is omitted from POST, and
    # unchecking core is already harmless because canonicalization adds it back.
    suffix = " (core, always on)" if definition.is_core else ""
    if definition.requires_modules:
        suffix += f" (requires {', '.join(definition.requires_modules)})"
    return f"{definition.label}{suffix}"


def _feature_label(feature):
    requirements = [
        requirement
        for requirement in (feature.parent_module, *feature.requires_modules, *feature.requires_features)
        if requirement
    ]
    if not requirements:
        return f"-> {feature.label}"
    return f"-> {feature.label} (requires {', '.join(requirements)})"


def _choice_label(feature):
    # Security keys are shown, never edited, here: they change only through the
    # Security section (Space Manager/superadmin authority, step-up and audit).
    if is_security_feature(feature.key):
        return f"-> {feature.label} (read-only here; change it under Security)"
    return _feature_label(feature)

class MakerspaceAdminForm(ImageMakerspaceAdminForm):
    capabilities = forms.MultipleChoiceField(
        required=False,
        label="Modules and features",
        widget=CapabilityMatrixWidget,
    )

    class Meta(ImageMakerspaceAdminForm.Meta):
        exclude = ("enabled_modules", "enabled_features")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Sourced from the registry, not "defaults + keys already on the row". That old
        # rule meant a module absent from the defaults could never be offered on a new
        # makerspace -- which is why `notifications` was enforced but unreachable.
        choices = [
            (f"module:{definition.key}", _module_label(definition))
            for definition in MODULES
        ]
        # Unknown legacy keys stay selectable so saving cannot silently drop them.
        known = {definition.key for definition in MODULES}
        choices.extend(
            (f"module:{key}", f"{key.replace('_', ' ').title()} (unrecognised)")
            for key in (self.instance.enabled_modules or [])
            if key not in known
        )
        choices.extend(
            (f"feature:{item.key}", _choice_label(item))
            for item in FEATURE_DEFINITIONS
        )
        self.fields["capabilities"].choices = choices
        selected = [f"module:{key}" for key in self.instance.enabled_modules or []]
        selected.extend(f"feature:{key}" for key in self.instance.enabled_features or [])
        self.initial["capabilities"] = selected
        self.capability_before = {
            "modules": sorted(set(self.instance.enabled_modules or [])),
            "features": sorted(set(self.instance.enabled_features or [])),
        }
        # Captured here, from the UNMODIFIED instance: `clean_capabilities` rewrites
        # `enabled_modules` in place, so by `save_model` the old policy is gone. Ticking
        # `membership` in this matrix forces account-less requests off inside
        # `Makerspace.save()`, and the module/feature lists alone cannot tell an
        # `anyone -> members` change from an `accounts -> members` one.
        self.request_access_before = effective_policy(self.instance)

    def clean_capabilities(self):
        values = self.cleaned_data["capabilities"]
        modules = [value.removeprefix("module:") for value in values if value.startswith("module:")]
        features = [value.removeprefix("feature:") for value in values if value.startswith("feature:")
                    and not is_security_feature(value.removeprefix("feature:"))]
        features += [key for key in self.capability_before["features"] if is_security_feature(key)]
        # MP-28 / owner decisions #82 and #87: the same rules the page script applies
        # (admin_capability_completion), so a save that bypasses the script lands in the
        # same place and nothing is silently re-ticked.
        result = complete_selection(self.capability_before["modules"], modules, features)
        unavailable = [key for key in result.added if not module_available(key)]
        if unavailable:
            raise forms.ValidationError(
                f"The ticked modules and features require {', '.join(unavailable)}, which this "
                "deployment does not ship (TOMBSTONED_APPS)."
            )
        self.capability_dependencies_added = result.added
        self.capability_turned_off = result.turned_off_modules + result.turned_off_features
        try:
            modules, features = validate_capabilities(result.modules, result.features)
        except Exception as exc:
            raise forms.ValidationError(exc.messages) from exc
        self.instance.enabled_modules = modules
        self.instance.enabled_features = features
        return values


class MakerspaceCapabilityAdminMixin(MakerspaceSecurityAdminMixin):
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        before = getattr(form, "capability_before", {"modules": [], "features": []})
        after = {
            "modules": sorted(set(obj.enabled_modules or [])),
            "features": sorted(set(obj.enabled_features or [])),
        }
        request_access_before = getattr(form, "request_access_before", None)
        request_access_after = effective_policy(obj)
        request_access_changed = (
            request_access_before is not None
            and request_access_before != request_access_after
        )
        dependencies_added = getattr(form, "capability_dependencies_added", [])
        turned_off = getattr(form, "capability_turned_off", [])
        if dependencies_added:
            self.message_user(request, f"Also enabled {_labels(dependencies_added)}: the modules "
                              "and features you ticked require them.", messages.WARNING)
        if turned_off:
            self.message_user(request, f"Also turned off {_labels(turned_off)}: they need a module "
                              "you unticked.", messages.WARNING)
        if change and (before != after or request_access_changed):
            meta = {"before": before, "after": after}
            if dependencies_added:
                meta["dependencies_added"] = dependencies_added
            if turned_off:
                meta["dependents_turned_off"] = turned_off
            if request_access_changed:
                meta["request_access"] = {
                    "before": request_access_before,
                    "after": request_access_after,
                }
            audit.record(
                request.user,
                "makerspace.capabilities_changed",
                makerspace=obj,
                target=obj,
                meta=meta,
            )
