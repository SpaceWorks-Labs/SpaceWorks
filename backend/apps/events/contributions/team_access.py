"""Contributor team operations resolve A's real roster, never contact guesses."""
from django.utils.translation import gettext
from django.shortcuts import get_object_or_404
from django.utils import timezone
from apps.events.hackathons.team_models import HackathonTeam, HackathonTeamMember
from apps.events.programme_locks import assert_lock_context
from .errors import ProgrammeError


class TeamAccess:
    def own_ids(self, *, actor_id, event_id):
        return tuple(HackathonTeamMember.objects.filter(event_id=event_id, member_id=actor_id,
            state="active", team__state__in=("forming", "locked")).values_list("team_id", flat=True))

    def member_ids(self, *, event_id, team_id):
        get_object_or_404(HackathonTeam, event_id=event_id, pk=team_id)
        return tuple(HackathonTeamMember.objects.filter(event_id=event_id, team_id=team_id,
            state="active").order_by("member_id").values_list("member_id", flat=True))

    def require_member(self, *, actor_id, event_id, team_id):
        from apps.events.answer_derivations.subjects import require_member
        require_member(actor_id)
        get_object_or_404(HackathonTeamMember, event_id=event_id, team_id=team_id,
            member_id=actor_id, state="active", team__state__in=("forming", "locked"))

    def require_eligible(self, *, event_id, team_id, at):
        from apps.events.hackathons.admission_workflow import require_team_eligible
        require_team_eligible(event_id=event_id, team_id=team_id, at=at)

    def skills(self, *, event_id, team_id):
        return tuple(get_object_or_404(HackathonTeam, pk=team_id, event_id=event_id).skills)

    def alias(self, *, event_id, team_id):
        return get_object_or_404(HackathonTeam, pk=team_id, event_id=event_id).name

    def ids(self, *, event_id, practice_run_id):
        if practice_run_id:
            from apps.events.mentoring.models_rounds import MentorImportPreview
            import json
            preview = MentorImportPreview.objects.filter(event_id=event_id, practice_run_id=practice_run_id,
                committed_at__isnull=False).order_by("-committed_at").first()
            return tuple(sorted(item["team_id"] for item in json.loads(preview.mapping))) if preview else ()
        return tuple(HackathonTeam.objects.filter(event_id=event_id).exclude(state="disbanded").order_by("pk").values_list("pk", flat=True))

    def require_practice(self, *, event_id, team_id, practice_run_id):
        get_object_or_404(HackathonTeam, pk=team_id, event_id=event_id)
        if practice_run_id and team_id not in self.ids(event_id=event_id, practice_run_id=practice_run_id):
            raise ProgrammeError("practice_scope_mismatch", gettext("Use a team mapped to this practice run."), status=404)

    def validate_import(self, *, event_id, rows):
        if not isinstance(rows, list) or not 1 <= len(rows) <= 500:
            raise ProgrammeError("invalid_import", gettext("Use 1–500 explicit mappings."), status=400)
        result, seen = [], set()
        for item in rows:
            if not isinstance(item, dict) or set(item) != {"team_id", "member_ids", "alias"}:
                raise ProgrammeError("invalid_import", gettext("Use explicit team and member IDs."), status=400)
            team_id, members, alias = item["team_id"], item["member_ids"], item["alias"]
            if (type(team_id) is not int or team_id in seen or not isinstance(members, list)
                    or any(type(pk) is not int for pk in members) or len(set(members)) != len(members)
                    or not isinstance(alias, str) or not alias.strip() or len(alias) > 100
                    or any(ord(c) < 32 for c in alias)):
                raise ProgrammeError("invalid_import", gettext("Check the explicit mapping."), status=400)
            team = get_object_or_404(HackathonTeam, event_id=event_id, pk=team_id)
            if set(members) != set(self.member_ids(event_id=event_id, team_id=team_id)):
                raise ProgrammeError("mapping_changed", gettext("Import must match the current admitted roster."))
            seen.add(team_id)
            result.append({"team_id": team_id, "member_ids": sorted(members), "alias": alias.strip()})
        return sorted(result, key=lambda item: item["team_id"])

    def import_locked(self, *, event_id, mapping, practice_run_id, locks):
        assert_lock_context(locks)
        if locks.event_id != event_id:
            raise RuntimeError("Use the declared event scope.")
        # Import selects real teams for Mentor Desk. Admission/roster ownership
        # stays in A; the committed preview is the durable mapping and alias source.
        ids = sorted(item["team_id"] for item in mapping)
        list(HackathonTeam.objects.select_for_update().filter(event_id=event_id, pk__in=ids).order_by("pk"))
        if self.validate_import(event_id=event_id, rows=mapping) != mapping:
            raise ProgrammeError("mapping_changed", gettext("Review the current team mapping."))
