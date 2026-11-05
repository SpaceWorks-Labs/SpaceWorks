"""Versioned configuration and private immutable code-of-conduct revisions."""
from .admission_errors import check_version, fail
from .admission_models import HackathonApplication, HackathonCocRevision
from .admission_ports import ports
from .admission_transactions import command, record
from .capacity_admission import occupancy
from .serializers_config import ConfigInput, validate_rubric

CONFIG_FIELDS = tuple(key for key in ConfigInput().fields if key not in ("operation_id", "expected_version", "coc_body"))


def update(*, event_id, actor, data):
    with command(event_id=event_id, actor=actor, data=data, action="config.edit", configuration=True) as ctx:
        config = ctx.config
        if ctx.reference:
            return config
        # A never-configured disabled config is a virtual version0 resource.
        initial = not HackathonCocRevision.objects.filter(event=ctx.event).exists()
        check_version(None if ctx.created_config else config, data["expected_version"])
        if HackathonApplication.objects.filter(event=ctx.event).exists():
            if any(key in data and data[key] != getattr(config, key) for key in ("team_mode", "application_form", "optional_mlh_schema")):
                fail("applications_exist", "Reopen a new form revision through the admission review process.")
        if "application_form" in data:
            ports().forms.validate_schema(data["application_form"])
        if data.get("optional_mlh_schema"):
            ports().forms.validate_schema(data["optional_mlh_schema"])
        if "review_rubric" in data:
            if data["review_rubric"].get("criteria") or (data.get("enabled", config.enabled) and data.get("review_mode", config.review_mode) != "auto"):
                validate_rubric(data["review_rubric"])
            if not initial and data["review_rubric"] != config.review_rubric:
                if data["review_rubric"]["revision"] <= config.review_rubric.get("revision", 0):
                    fail("rubric_revision_changed", "Increase the rubric revision.")
                config.review_round += 1
        from apps.events.submissions.stage_config import changed_window, refuse_multi_stage, sync_after_save
        refuse_multi_stage(config, data)  # #178: several stages each own their window.
        window_changed = changed_window(config, data)
        for key in CONFIG_FIELDS:
            if key in data:
                setattr(config, key, data[key])
        from .admission_feature import applications_only
        if applications_only(ctx.event.makerspace):
            # Applications for any event (#128 C-32) have no teams, finder or submissions.
            config.team_mode = "solo"
        if config.team_mode == "solo":
            config.team_min = config.team_max = 1
            config.finder_enabled = False
        if config.finder_enabled and config.team_mode != "individual_then_team":
            fail("invalid_finder_mode", "Team finder is available for individual applications.", status=400)
        if config.team_min > config.team_max:
            fail("invalid_team_size", "Minimum team size exceeds maximum.", status=400)
        for start, end in ((config.application_opens_at, config.application_closes_at), (config.submission_opens_at, config.submission_deadline)):
            if start and end and start >= end:
                fail("invalid_window", "The close time must follow the opening time.", status=400)
        for value in (config.application_closes_at, config.team_lock_at, config.submission_opens_at, config.submission_deadline):
            if value and value > ctx.event.ends_at:
                fail("invalid_window", "Programme deadlines must fit the event.", status=400)
        if not ports().upload_policy_supported(name=config.upload_policy, version=config.upload_policy_version):
            fail("invalid_upload_policy", "Choose a supported upload policy and version.", status=400)
        # G supplies the real deployment tier; no client may claim self-host.
        managed = ports().storage_budget_limit(event_id=event_id)
        if managed is not None and (config.storage_budget_bytes is None or config.storage_budget_bytes > managed):
            config.storage_budget_bytes = managed
        if config.storage_budget_bytes is not None and ports().storage_budget_used(event_id=event_id) > config.storage_budget_bytes:
            fail("storage_budget_in_use", "The budget cannot be smaller than stored files and active reservations.", status=413)
        counts = occupancy(ctx.event, config)
        if config.offer_capacity is not None and config.offer_capacity < counts["offered"] + counts["confirmed"]:
            fail("capacity_full", "The offer ceiling cannot be lower than current allocations.")
        if "coc_body" in data:
            config.coc_revision = 1 if initial else config.coc_revision + 1
            HackathonCocRevision.objects.create(event=ctx.event, revision=config.coc_revision, body=data["coc_body"])
        if config.enabled and not HackathonCocRevision.objects.filter(event=ctx.event, revision=config.coc_revision).exists():
            fail("coc_required", "Write a code of conduct before enabling applications.", status=400)
        if config.enabled and config.review_mode != "auto":
            validate_rubric(config.review_rubric)
        config.version = 1 if ctx.created_config else config.version + 1
        config.save()
        sync_after_save(config, actor, window_changed)
        record(ctx, "config_updated", config, version=config.version, enabled=config.enabled,
               offer_capacity=config.offer_capacity)
        ctx.finish("config", config.pk)
        return config


def project(config):
    from django.forms.models import model_to_dict
    result = model_to_dict(config, fields=CONFIG_FIELDS)
    result.update(id=config.pk, event_id=config.event_id, version=config.version, state="enabled" if config.enabled else "disabled",
                  allowed_actions=["edit"], counts=occupancy(config.event, config))
    coc = HackathonCocRevision.objects.filter(event_id=config.event_id, revision=config.coc_revision).first()
    result["coc"] = {"revision": coc.revision, "body": coc.body} if coc else None
    return result
