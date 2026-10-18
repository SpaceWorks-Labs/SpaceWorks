"""Literal G integration manifest; this module does not register or enable paths."""

MODEL_MANIFEST = {
    "label": "events.EventAnswerDerivation",
    "import": "apps.events.answer_derivations.models.EventAnswerDerivation",
    "table": "events_eventanswerderivation",
    "fields": {
        "id": "BigAutoField primary key (allocate nextval outside domain transaction)",
        "event": "FK events.Event CASCADE, related_name=answer_derivations",
        "registration": "nullable FK events.EventRegistration CASCADE, related_name=answer_derivations",
        "application": "nullable FK events.HackathonApplication CASCADE, related_name=answer_derivations",
        "role_assignment": "nullable FK events.EventRoleAssignment CASCADE, related_name=answer_derivations",
        "question_id": "CharField(128)",
        "source_dob_envelope": "TextField editable=False, tenant ciphertext only",
        "event_date_revision": "PositiveIntegerField >=1",
        "as_of_date": "DateField, reviewed or frozen event-local start date",
        "locked_at": "nullable DateTimeField",
        "version": "PositiveIntegerField default=1 >=1",
        "source_history": "JSONField list default, editable=False, encrypted source/reason snapshots",
    },
    "constraints": {
        "event_derivation_one_subject": "exactly one of all three nullable subject FKs",
        "event_derivation_reg_question": "unique(registration, question_id) WHERE registration IS NOT NULL",
        "event_derivation_app_question": "unique(application, question_id) WHERE application IS NOT NULL",
        "event_derivation_role_question": "unique(role_assignment, question_id) WHERE role_assignment IS NOT NULL",
        "event_derivation_version_positive": "version >=1",
        "event_derivation_date_positive": "event_date_revision >=1",
    },
    "tenant_resolver": "event.makerspace_id",
    "insertion_lock_order": "source boundary -> atomic -> account_fences(owner IDs, tenant IDs) -> Event -> typed subject -> derivations",
    "insertion_account_guard": "every source insertion, including inline DOB and no-save choices, requires declared shared owner fence and live open/absent fence; no account row locks/key provisioning",
    "saved_dob_epoch_caveat": "prepared tenant source does not carry account-key epoch; erased/closed fences refuse, but ordinary vault field deletion/change, key rotation or non-erasing key revocation does not invalidate a prepared source while the fence remains open",
    "source_pii": {
        "source_dob_envelope": {
            "classification": "source", "index_kind": "none", "max_length": None,
            "makerspace_path": "event.makerspace_id", "mode": "explicit_tenant_envelope",
            "aad_field": "source_dob_envelope",
        },
        "source_history": {
            "mode": "typed_envelope_container", "blind_index": False,
            "encrypted_paths": {
                "[].source_dob_envelope": "same row pk + source_dob_envelope AAD field",
                "[].reason_envelope": "same row pk + reopen_reason_envelope AAD field",
            },
        },
    },
    "user_edges": {
        "direct": [],
        "indirect": ["registration.member", "application.member", "role_assignment.member"],
        "disposition": "typed parent owns pseudonymization; retain submitted/locked ciphertext",
    },
    "objects": [],
    "tenant_fidelity": "canonical retained event evidence; typed FK remap, rebind all AAD envelopes on ID/tenant remap",
    "portability_adapter": "apps.events.answer_derivations.portability.capture_event_sources/rebind_portable_envelopes",
    "public_or_staff_csv": "permitted derived age only; no source/history/envelope/vault references",
    "deployment_backup": "retain canonical row and tenant wrapped key custody",
    "vault_erasure": "no effect on independently submitted event source/history",
    "account_erasure": "delete unsubmitted draft sources; retain submitted/locked evidence through typed parent policy",
    "account_erasure_adapter": "workflow.erase_owner_drafts_locked before account-only key deletion; no account row locks",
    "event_or_tenant_purge": "delete before registration/application/role_assignment parents",
    "tombstone": "retain source lifecycle/export/purge metadata even without Events runtime",
    "reset": "no runtime token or external object; canonical evidence is not reset coordination",
}

COORDINATING_FIELDS = {
    "events.Event": {"event_date_revision": "PositiveIntegerField default=1"},
    "events.EventRegistration": {
        "answer_locked_at": "nullable DateTimeField", "date_review_required": "BooleanField default=False",
        "version": "PositiveIntegerField default=1",
    },
    "events.HackathonApplication": {
        "answer_locked_at": "nullable DateTimeField", "date_review_required": "BooleanField default=False",
        "version": "PositiveIntegerField default=1",
    },
    "events.EventRoleAssignment": {
        "form_schema_version": "versioned schema snapshot per C", "application_answers": "encrypted canonical answers per C",
        "answer_locked_at": "nullable DateTimeField", "date_review_required": "BooleanField default=False",
        "version": "PositiveIntegerField default=1",
    },
}
