"""Release-2 admission settings: switches and the settings-authority layer (L4).

* `gate_settings` refuses (403 `feature_disabled`) a write that uses a switched-off
  feature: the NEVER / AFTER_LAPSE rejoin rules (`membership.plan_rules`), the
  member-number pattern (`membership.member_numbers`) and the consent purposes and
  notice version (`membership.consent`). Stored values stay when a switch goes off.
* `authorize_settings` routes every changed key through `assert_setting_write`
  (LANE-RULES §13). Membership has no module-manager role, so these stay the Space
  Manager's (or the superadmin's); each change is audited as `settings.changed`.
"""
from django.utils.translation import gettext
from rest_framework.exceptions import PermissionDenied

from apps.makerspaces.membership_features import membership_feature_on

MODULE = "membership"
GATED = {
    "plan_rules": ("rejoin_dues_rule", "rejoin_after_days"),
    "member_numbers": ("member_number_pattern",),
    "consent": ("consent_purposes", "privacy_notice_version"),
}


def gate_settings(makerspace, values, row):
    """Refuse CHANGING a gated field while its switch is off. Re-sending the stored value
    (the editor posts every field back) is not a change, so saved data never blocks a save."""
    for key, names in GATED.items():
        changed = [name for name in names if name in values and values[name] != getattr(row, name, None)]
        if key == "plan_rules":
            changed = [name for name in changed if name != "rejoin_dues_rule"
                       or values[name] in ("never", "after_lapse")]
        if changed and not membership_feature_on(makerspace, key):
            raise PermissionDenied({"code": "feature_disabled", "feature": f"membership.{key}",
                                    "detail": gettext("Turn on membership.%(key)s to change: %(value)s.") % {"key": key, "value": ", ".join(changed)}})
    return values


def authorize_settings(actor, makerspace, values):
    """`{key: decision}` for every key being written; raises a typed 403 when refused."""
    from apps.makerspaces.settings_authority import assert_setting_write
    return {key: assert_setting_write(actor, makerspace, MODULE, f"{MODULE}.{key}") for key in values}


def record_settings(actor, makerspace, before, row, decisions):
    from apps.makerspaces.settings_authority import record_change
    for key, decision in decisions.items():
        if key == "recipe":
            continue
        after = getattr(row, key, None)
        after = getattr(after, "pk", after)
        record_change(actor, makerspace, MODULE, f"{MODULE}.{key}", _plain(before.get(key)), _plain(after), decision)


def _plain(value):
    if hasattr(value, "pk"):
        return value.pk
    if value is None or isinstance(value, (bool, int, str, list, dict)):
        return value
    return str(value)
