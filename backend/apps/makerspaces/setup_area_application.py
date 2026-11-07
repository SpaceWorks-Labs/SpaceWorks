"""One atomic installer application, using ordinary module and settings writers."""
from django.utils.translation import gettext
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.accounts import rbac
from apps.admin_api.permissions import require_action
from apps.makerspaces.models import Makerspace
from apps.tenant_migration.gate_runtime import assert_write_allowed
from .module_install import install_module, uninstall_module, ModuleInstallError
from .module_registry import BY_KEY, core_module_keys, dependents_of, module_available
from .request_access import effective_policy
from .setup_areas import AREAS, modules_for, features_for, INVENTORY_FEATURES
from .capabilities import FEATURES, validate_capabilities, feature_required_modules, prune_features
from .setup_settings import apply_settings, save_space
from .setup_defaults import initial_settings
from .security_settings_registry import is_security_feature

SETTING_AREAS = {"loan_policy": "inventory", "loan_charges": "inventory", "admission": "membership", "plan": "membership",
                 "machine_policy": "machines"}


class SettingsCreatedDuringLock(Exception):
    """Retry outside atomic when a concurrent writer created payment settings first."""


def validate_answers(answers):
    if not isinstance(answers, dict) or set(answers) - {"areas", "settings", "request_access", "without", "configure_areas", "enable_area_features"}:
        raise ValidationError(gettext("Use an object with areas, settings, request_access and optional without."))
    if "enable_area_features" in answers and type(answers["enable_area_features"]) is not bool:
        raise ValidationError({"enable_area_features": gettext("Use a boolean.")})
    areas = answers.get("areas")
    if not isinstance(areas, list) or any(not isinstance(key, str) or key not in AREAS for key in areas):
        raise ValidationError({"areas": gettext("Choose registered setup areas.")})
    if len(set(areas)) != len(areas):
        raise ValidationError({"areas": gettext("Areas must be unique.")})
    settings = answers.get("settings", {})
    if not isinstance(settings, dict) or set(settings) - {*SETTING_AREAS, "space", "notifications", "currency", "features"}:
        raise ValidationError({"settings": gettext("Unknown settings section.")})
    for key, area in SETTING_AREAS.items():
        if key in settings and area not in areas:
            raise ValidationError({key: gettext('Enable the {area} area first.').format(area=area)})
    if any(not isinstance(value, dict) for key, value in settings.items() if key != "currency"):
        raise ValidationError({"settings": gettext("Settings sections must be objects.")})
    overrides = settings.get("features", {})
    # Staff MFA is a platform rule since release 2 (#62); the old switch is no setup answer.
    if any(key not in {"inventory.self_checkout", "inventory.kiosk", "machines.certifications"}
           or type(value) is not bool for key, value in overrides.items()):
        raise ValidationError({"features": gettext("Use supported boolean setup feature switches.")})
    for key in overrides:
        area = "inventory" if key.startswith("inventory.") else "machines" if key.startswith("machines.") else None
        if area and area not in areas:
            raise ValidationError({key: gettext('Enable the {area} area first.').format(area=area)})
    space_fields = {"event_default_registration_audience", "timezone"}
    if set(settings.get("space", {})) - space_fields:
        raise ValidationError({"space": gettext("Unknown setup space field.")})
    if "event_default_registration_audience" in settings.get("space", {}) and "events" not in areas:
        raise ValidationError({"space": gettext("Enable Events to set its default audience.")})
    mode = answers.get("request_access")
    # Every borrow request needs an account (#75f); the answer only confirms which
    # accounts, and that follows from whether Membership is among the areas.
    if mode is not None and ("inventory" not in areas or mode not in ("members", "accounts")):
        raise ValidationError({"request_access": gettext("Choose members or accounts with Inventory enabled.")})
    if mode and ((mode == "members") != ("membership" in areas)):
        raise ValidationError({"request_access": gettext("Membership enabled requires members; otherwise choose accounts.")})
    without = answers.get("without", [])
    if not isinstance(without, list) or any(not isinstance(key, str) or key not in BY_KEY or key in core_module_keys() for key in without):
        raise ValidationError({"without": gettext("Use optional module keys.")})
    if "member_accounts" in without:
        raise ValidationError({"without": gettext("Personal accounts are always on in setup.")})
    configuring = answers.get("configure_areas", areas)
    if not isinstance(configuring, list) or any(key not in areas for key in configuring):
        raise ValidationError({"configure_areas": gettext("Choose a subset of enabled areas.")})
    return set(areas), settings, mode, set(without), set(configuring)


@transaction.atomic
def apply_areas(actor, space, answers):
    areas, settings, mode, without, configuring = validate_answers(answers)
    enable_area_features = answers.get("enable_area_features", False)
    require_action(actor, rbac.Action.MANAGE_MAKERSPACE, space.pk)
    assert_write_allowed(space.pk)
    # Checkout/profile writers take payment-settings before the makerspace. Match that
    # order, including the concurrent first-row creation retry used by the profile API.
    from apps.payments.models import MakerspacePaymentSettings
    created_payment = False
    # Always insert before the root lock, as the profile API does: generated defaults
    # (a first currency) can need the row, and a concurrent settings creator needs its
    # FK key-share lock on the makerspace to finish inserting, so creating the row
    # under FOR UPDATE could deadlock on the unique index.
    try:
        with transaction.atomic():
            _, created_payment = MakerspacePaymentSettings.objects.get_or_create(makerspace=space)
    except DjangoValidationError:
        # save() runs full_clean(): a competing insert can surface as a uniqueness error.
        if not MakerspacePaymentSettings.objects.filter(makerspace=space).exists():
            raise
    payment = MakerspacePaymentSettings.objects.filter(makerspace=space).select_for_update().first()
    space = Makerspace.objects.select_for_update().get(pk=space.pk)
    if payment is None and MakerspacePaymentSettings.objects.filter(makerspace=space).exists():
        raise SettingsCreatedDuringLock()
    previous_features = set(space.enabled_features)
    previous_modules = set(space.enabled_modules) | core_module_keys()
    wanted = modules_for(areas) - without
    anchors = {"inventory": "request_workflow", "machines": "machines", "events": "events", "membership": "membership"}
    initial = {area for area in configuring if anchors.get(area) is None or anchors[area] in wanted}
    settings = initial_settings(initial, settings, first_setup="configure_areas" not in answers,
                                stored_currency=payment.default_currency if payment and not created_payment else None)
    unavailable = sorted(key for key in wanted if not module_available(key))
    if unavailable:
        raise ModuleInstallError(f"Setup areas require unavailable modules: {', '.join(unavailable)}.")
    # Legacy unknown keys are retained; only registered optional modules are removed.
    removing = (set(space.enabled_modules) & BY_KEY.keys()) - wanted - core_module_keys()
    while removing:
        ready = sorted(key for key in removing if not dependents_of(key, set(space.enabled_modules) - {key}))
        if not ready:
            raise ModuleInstallError("Selected areas conflict with installed module dependencies.")
        for key in ready:
            uninstall_module(space, key, actor)
            removing.remove(key)
    for key in sorted(wanted):
        install_module(space, key, actor)
    features = set(features_for(areas, wanted))
    if "configure_areas" in answers and not enable_area_features:
        # Standalone switches and always-installed modules also hold intentional
        # choices; an absent key in enabled_features is a stored opt-out.
        preserved_parents = previous_modules | {None}
        # A newly installed prerequisite (especially Online payments) activates its
        # domain features even when the domain itself was already configured.
        preserved = {key for key, definition in FEATURES.items()
                     if definition.parent_module in preserved_parents
                     and set(feature_required_modules(key)) <= previous_modules}
        if "inventory" in configuring:
            preserved -= {key for key, definition in FEATURES.items()
                          if definition.parent_module in AREAS["inventory"]}
            preserved -= INVENTORY_FEATURES | {"payments.loans"}
        if "inventory" in areas - configuring:
            preserved |= INVENTORY_FEATURES
        features = (features - preserved) | (previous_features & preserved)
    # Security keys change only through the security service (authority, lock floor,
    # audit), applied below once the generic writers are done.
    security = {key: enabled for key, enabled in settings.get("features", {}).items() if is_security_feature(key)}
    for key, enabled in settings.get("features", {}).items():
        if key in security:
            continue
        if enabled:
            features.add(key)
        else:
            features.discard(key)
    # Stored security choices always survive here (MFA is never part of the everything
    # preset either); only the security service below may change them.
    features = {key for key in features if not is_security_feature(key)} | {
        key for key in previous_features if is_security_feature(key)}
    if "inventory" not in areas:
        if "configure_areas" in answers:
            # Hiding lending is not cancelling the policy/charges on tools already
            # issued. Core loan features survive, just as they do when loans.enabled
            # is switched off in Features; optional-module children are pruned below.
            features |= {key for key in previous_features if key in FEATURES and FEATURES[key].parent_module in core_module_keys()}
            if "payments.loans" in previous_features and "payments" in wanted:
                features.add("payments.loans")
        else:
            features.discard("payments.loans")
        features.discard("loans.enabled")
    supported, _ = prune_features(features, wanted)
    _, canonical = validate_capabilities(sorted(wanted), supported, dormant_defaults=supported)
    space = save_space(actor, space, {"enabled_features": canonical}, restore_feature_configuration=True)
    space = apply_settings(actor, space, {key: value for key, value in settings.items() if key != "features"})
    # Admission stores the chosen mode/schema, but area features remain enabled even
    # when their settings make them inert (e.g. vouching with approval admission).
    space = save_space(actor, space, {"enabled_features": canonical}, restore_feature_configuration=True)
    if not enable_area_features:
        from . import security_settings
        for key, enabled in security.items():
            space = security_settings.set_setting(actor, space, key, enabled)
    if mode and effective_policy(space) != mode:
        raise ValidationError({"request_access": gettext('The live policy is {value}.').format(value=effective_policy(space))})
    return space
