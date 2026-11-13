"""Publication/deadline/gating policies without Django or a forms-engine fork."""

from datetime import UTC, datetime, timedelta
import unittest

from apps.events.staged_forms.deadlines import reminder_times, resolve
from apps.events.staged_forms.policy import (
    Completion, StagePolicyError, missing_requirements, require_stage_schema, validate_audience, validate_blocking,
)


class StagePolicies(unittest.TestCase):
    def schema(self, question):
        return {"questions": [{"id": "q", "type": "short_text", **question}]}

    def test_hidden_optional_sensitive_age_questions_cannot_publish(self):
        for question in ({"type": "date_of_birth"}, {"type": "age_at_event"},
                         {"type": "date", "profile_field_key": "date_of_birth"},
                         {"type": "number", "profile_field_key": "age_at_event"}):
            for flags in ({"required": False}, {"visibility": "server"}, {"sensitive": True}):
                with self.subTest(question=question, flags=flags):
                    with self.assertRaisesRegex(StagePolicyError, "stage_age_question_unsupported"):
                        require_stage_schema(self.schema({**question, **flags}))

    def test_nonempty_derivations_are_refused_even_with_no_age_question(self):
        with self.assertRaisesRegex(StagePolicyError, "stage_age_question_unsupported"):
            require_stage_schema(self.schema({}), derivations={"q": {"source": "inline_dob"}})

    def test_empty_derivations_and_nonage_date_question_work(self):
        schema = self.schema({"type": "date"})
        self.assertIs(require_stage_schema(schema, derivations={}), schema)

    def test_stage_files_cannot_use_finance_or_resume_purposes(self):
        for purpose in ("reimbursement_receipt", "reimbursement_payee_document", "resume", "external_url"):
            with self.assertRaisesRegex(StagePolicyError, "stage_file_purpose_unsupported"):
                require_stage_schema(self.schema({"type": "file", "file": {"purpose": purpose}, "sensitive": True}))
        require_stage_schema(self.schema({"type": "file", "file": {"purpose": "stage_form_file"}}))

    def test_audience_rejects_age_and_untyped_track_selectors(self):
        base = {"roles": [], "track_ids": [], "travel_requested": None}
        for change in ({"min_age": 18}, {"track_ids": [True]}, {"track_ids": ["1"]}, {"travel_requested": "yes"}):
            with self.assertRaises(StagePolicyError):
                validate_audience({**base, **change})

    def test_ordinary_event_cannot_block_nonexistent_rsvp(self):
        with self.assertRaisesRegex(StagePolicyError, "stage_rsvp_unsupported"):
            validate_blocking(stage="application", activation_point="", required=True, missed_action="block",
                              blocked_actions=["rsvp"], hackathon=False)

    def test_dependency_cycles_are_refused(self):
        for stage, point, action in (("post_event", "", "check_in"), ("pre_event", "", "rsvp"),
                                     ("accepted_rsvp", "rsvp", "rsvp")):
            with self.assertRaisesRegex(StagePolicyError, "stage_dependency_cycle"):
                validate_blocking(stage=stage, activation_point=point, required=True, missed_action="block",
                                  blocked_actions=[action], hackathon=True)

    def test_missing_assignment_blocks_without_creating_anything(self):
        assignments = {}
        self.assertEqual(missing_requirements({10}, assignments), (10,))
        self.assertEqual(assignments, {})

    def test_cancel_exempts_but_replacement_requires_new_pinned_submission(self):
        cancelled = Completion(state="cancelled", pinned_form_revision_id=2, submitted_form_revision_id=1,
                               submitted_response_id=50, completed_response_id=None)
        self.assertEqual(missing_requirements({10}, {10: cancelled}), ())
        reopened = Completion(state="open", pinned_form_revision_id=2, submitted_form_revision_id=1,
                              submitted_response_id=50, completed_response_id=None)
        self.assertEqual(missing_requirements({10}, {10: reopened}), (10,))

    def test_old_pin_or_response_pointer_cannot_satisfy_completed(self):
        for form, response in ((1, 50), (2, 51), (None, 50)):
            completion = Completion(state="completed", pinned_form_revision_id=2, submitted_form_revision_id=form,
                                    submitted_response_id=response, completed_response_id=50)
            self.assertFalse(completion.satisfies())
        self.assertTrue(Completion(state="completed", pinned_form_revision_id=2, submitted_form_revision_id=2,
                                   submitted_response_id=50, completed_response_id=50).satisfies())


class StageDeadlines(unittest.TestCase):
    def setUp(self):
        self.at = datetime(2026, 10, 18, tzinfo=UTC)
        self.base = {"triggered_at": self.at, "event_start": self.at + timedelta(days=10),
                     "event_end": self.at + timedelta(days=12), "opening_mode": "trigger",
                     "due_mode": "after_trigger", "due_after_seconds": 86400}

    def test_relative_deadline_is_member_trigger_specific(self):
        result = resolve(**self.base)
        self.assertEqual(result.due_at, self.at + timedelta(days=1))

    def test_event_offsets_use_correct_anchor(self):
        result = resolve(**{**self.base, "opening_mode": "event_end", "opening_offset_seconds": 0,
                            "due_mode": "event_end", "due_after_seconds": None, "due_event_offset_seconds": 86400})
        self.assertEqual(result.opens_at, self.at + timedelta(days=12))
        self.assertEqual(result.due_at, self.at + timedelta(days=13))

    def test_invalid_shape_negative_interval_naive_date_and_inverted_dates_refused(self):
        for change in ({"due_after_seconds": 0}, {"due_after_seconds": True}, {"due_after_seconds": 31536001},
                       {"due_at": self.at}, {"triggered_at": self.at.replace(tzinfo=None)},
                       {"event_end": self.at}, {"opening_mode": "absolute", "opens_at": self.at + timedelta(days=2)}):
            with self.assertRaises(StagePolicyError):
                resolve(**{**self.base, **change})

    def test_reminders_never_precede_or_equal_activation(self):
        times = reminder_times(triggered_at=self.at, due_at=self.at + timedelta(days=2), offsets=[-604800, -86400])
        self.assertEqual(times, (self.at + timedelta(days=1),))

    def test_reminder_offsets_are_bounded_unique_negative_seconds(self):
        for offsets in ([True], [0], [1], [-1, -1], [-1] * 11, [-31536001]):
            with self.assertRaises(StagePolicyError):
                reminder_times(triggered_at=self.at, due_at=self.at + timedelta(days=2), offsets=offsets)


if __name__ == "__main__":
    unittest.main()
