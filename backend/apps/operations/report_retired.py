"""Decision 329 (b): reports kept only as read-only history of a retired feature.

Machine certifications were retired by decision 319 (machine access replaced them); their rows stay
as history. The two certification reports therefore:

* are titled "(retired)" in their definitions;
* are listed (catalogue, schedules list) only for a space that has certification records;
* are never offered for a NEW schedule (refused with 400); a schedule that already exists keeps
  running, and manual exports keep working. `machine-access-grants` is the live report.
"""

RETIRED_REPORT_KEYS = frozenset({"certification-holders", "certification-coverage"})


def has_history(makerspace):
    """Whether this space has any certification record to report on."""
    from apps.machines.models_certifications import CertificationType

    return CertificationType.objects.filter(makerspace=makerspace).exists()


def retired_report_listed(makerspace, definition):
    return definition.key not in RETIRED_REPORT_KEYS or has_history(makerspace)


def newly_schedulable(definition):
    return definition.schedulable and definition.key not in RETIRED_REPORT_KEYS
