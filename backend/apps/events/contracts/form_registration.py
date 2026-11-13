"""Install A/C/D form-definition adapters into F's single schema/editor engine."""

from django.utils.translation import gettext
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

from apps.events.credentials.boundary import advance
from apps.events.hackathons.admission_models import HackathonConfig
from apps.events.contributions.models_roles import EventRolePosting
from apps.events.mentoring.models_rounds import MentorRound
from apps.events.judging.models_definitions import HackathonTrack
from apps.events.programme.providers import FormProvider, register_form
from apps.makerspaces.guards import require_feature

FORMS = {
    "application": (HackathonConfig, "application_form", None, "events.hackathons"),
    "volunteer": (EventRolePosting, "form_schema", "posting_id", "events.volunteering"),
    "mentor": (EventRolePosting, "form_schema", "posting_id", "events.mentoring"),
    "round": (MentorRound, "form_schema", "round_id", "events.mentor_rounds"),
    "track": (HackathonTrack, "form", "track_id", "events.hackathons"),
}


def provider(key):
    model, field, selector_name, feature = FORMS[key]
    def resolve(*, event, actor, selector, locked):
        from apps.events.hackathons.admission_feature import admission_enabled
        # The application form serves hackathons and any one-off event (#128 C-32).
        if key != "application" or not admission_enabled(event.makerspace):
            require_feature(event.makerspace, feature)
        rows = model.objects.select_for_update() if locked else model.objects.all()
        filters = {"event_id": event.pk}
        if selector_name:
            filters["pk"] = selector[selector_name]
        if key in ("volunteer", "mentor"):
            filters["role"] = key
        return get_object_or_404(rows, **filters)
    def read(*, event, actor, target):
        return getattr(target, field)
    def save_locked(*, event, actor, target, schema):
        if key == "round" and target.state != "draft":
            raise ValidationError({"schema": gettext("Close or create a draft round before changing its form.")})
        # No definition callback writes answers or bypasses F's revision guard.
        setattr(target, field, schema)
        target.version += 1
        target.save(update_fields=(field, "version"))
        advance(event)
    return FormProvider(key, resolve, read, save_locked)


class ProfileFields:
    def descriptors(self):
        from apps.forms_schema.profile_fields import PROFILE_FIELDS
        return tuple({"field_key": row.field_key, "sensitive": row.sensitive,
                      "persistable": row.persistable, "default_save": row.default_save}
                     for row in PROFILE_FIELDS.values())

    def normalize(self, key, value):
        from apps.forms_schema.profile_fields import normalize_profile_value
        return normalize_profile_value(key, value)


def install():
    for key in FORMS:
        register_form(provider(key))
    from apps.accounts.saved_details.fields import install_core_profile_fields
    install_core_profile_fields()
