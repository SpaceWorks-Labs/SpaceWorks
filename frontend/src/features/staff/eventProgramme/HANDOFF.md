# Lane F frontend handoff

Worktree `ev-f`, branch `lane/events-f`. No staging, commits, generated client/schema
changes, shared routes, shell primitives or `frontend/src/test/staffActor.ts` edits.

## Built per approved plan

- Section 10 gap 4 / 12A: form-v2 question cards, stable choice IDs and Other text,
  bounds, disclosure, profile mapping, earlier-question all/any conditions with bounded
  nesting, keyboard reorder buttons, sample validation and explicit legacy draft upgrade.
  Existing shared fields/builders dispatch v2 while retaining v1 primitive values.
  Compound emergency contacts permit blank relationship. Derived age uses event-local
  date arithmetic, remains absent from submitted answers and requires explicit date review.
  Sensitive save choices default off; hidden/server answers, mappings and choices are
  excluded from memberFormInput. Existing snapshots never reveal derivation IDs as values.
- Gap 5: brand composer designs, typed CTA editor, audience/template suggestions, reuse,
  immutable server desktop/mobile previews in sandboxed frames, self test, count/checkbox
  confirmation, future scheduling, status history and cancellation. Retry IDs remain stable
  for unchanged commands. Legacy cancel is strict `{}`; v2 cancel sends the CAS command.
- Gaps 6-8: permission-projected readiness/Waiting for you, opt-in event-day polling,
  zero-safe check-in meter and arrival buckets, authorized Next up presentation, funnel
  denominators/caveats/hints, capped share bars and a two-period signup table.
- Gaps 11-13: bounded canvas crop/rotate/straighten/brightness/contrast with numeric
  controls, reset/undo, card/social previews and alt-text callback; publishing's three
  questions, saved-site release choice, upload blocking, conflict-preserved drafts and
  dirty save/discard/navigation warnings; fixed brand accent choices with inheritance.
- Gaps 14-15: own security activity ListLayout; acknowledged organization leave with
  authority invalidation and backend owner/reauth errors; scoped series guest filters
  and per-occurrence authorized details; platform DashboardLayout aggregates and nullable MFA.
- Section 10 delight row 8: Excellent/Good/Okay/Poor radios use explicit revision-specific
  numeric/string or stable-option mappings, preserving legacy numeric meanings.
- Section 13: actor/session-scoped query suffixes preserve existing invalidation prefixes.
  Denied refreshes remove cached programme/form/series rows without a refetch loop.
  Forms/publishing clear local edits; broadcast denials hide data and invalidate history;
  a denied cover save releases its File/blob/preview URLs/alt/history. Exported
  ProgrammeSessionBoundary remounts its subtree when the session identity changes.

React owns unsaved input; TanStack Query owns server projections and invalidation. The
dirty bar never treats an event-settings save as website release. Cover transforms produce
a fresh bounded JPEG; the server remains responsible for sniffing/re-encoding and ownership.
No computed age or personal form draft is written to browser storage.

## Exact production files

Modified existing:

- `frontend/src/features/forms/CustomAnswersView.tsx`
- `frontend/src/features/forms/CustomFormBuilder.tsx`
- `frontend/src/features/forms/CustomFormFields.tsx`
- `frontend/src/features/forms/customFormTypes.ts`
- `frontend/src/features/staff/EventAnalyticsPanel.tsx`
- `frontend/src/features/staff/EventBroadcastsPanel.tsx` (thin re-export)

New under `frontend/src/features/forms/`:
`ageAtEvent.ts`, `ConditionEditor.tsx`, `conditions.ts`, `FormBuilderV2.tsx`,
`FormV2Fields.tsx`, `index.ts`, `QuestionEditor.tsx`, `QuestionInput.tsx`, `types.ts`,
`upgradeLegacyForm.ts`.

New under `frontend/src/features/staff/eventProgramme/`:
`AccentPresetPicker.tsx`, `api.ts`, `broadcastApi.ts`, `BroadcastComposer.tsx`,
`BroadcastDeliveryControls.tsx`, `coverImage.ts`, `CoverPhotoEditor.tsx`, `DirtySaveBar.tsx`,
`EventBroadcastsPanel.tsx`, `EventDayPanel.tsx`, `EventFunnel.tsx`,
`EventProgrammeAnalytics.tsx`, `EventPublishingPanel.tsx`, `EventReadinessPanel.tsx`,
`index.ts`, `NextUpEvents.tsx`, `ProgrammeFormEditor.tsx`, `SeriesGuestList.tsx`,
`sessionScope.tsx`, `useOperationId.ts`, `WordFeedbackRating.tsx`.

New extras:
`frontend/src/features/accountActivity/SecurityActivityPage.tsx`,
`frontend/src/features/organizationLeave/OrganizationLeaveCard.tsx`,
`frontend/src/features/platformInsights/PlatformInsightsPage.tsx`.

## Model manifest and routes

No frontend ORM/model changes or route mounting. Components consume F's frozen readiness,
live, publishing, form editor/validate, series guests, broadcast, member leave/security
and platform insights paths. EventProgrammeAnalytics requests the existing generic report
route with report key `event-programme` and event subject filters; G must register that key.

## Verification

`npx tsc -b`: **passed**, including the final denial cleanup and legacy-cancel parity changes.

`npx vitest run --config vitest.local-junction.config.ts --configLoader runner` with all
seven exact paths below: **7 files / 46 tests passed**. Six files are new; the unchanged
FeedbackFormControls suite protects existing feedback behavior.

```text
src/features/forms/forms.test.tsx
src/features/forms/FeedbackFormControls.test.tsx
src/features/staff/eventProgramme/programme.test.tsx
src/features/staff/eventProgramme/broadcast.test.tsx
src/features/staff/eventProgramme/coverImage.test.ts
src/features/staff/eventProgramme/coverPhoto.test.tsx
src/features/accountActivity/extras.test.tsx
```

Coverage includes the committed form/emergency fixtures, normalization/hidden-answer parity,
explicit DOB review, legacy choices, optional emergency relationship, axe on form controls,
stale publishing edits, exact recipient confirmation, legacy cancellation, retry identity,
bounded cover encoding, authority-refused cache refresh and cover-byte/URL cleanup.
`git diff --check -- frontend`: passed. All touched production files stay below 300 lines.
No Docker, Django, backend tests or real-browser visual review were run by this sublane.

## CROSS-LANE / UNFINISHED — required before integration acceptance

1. **G, before route acceptance:** mount exports in `AppRoutes.tsx`,
   `staff/EventDrawer.tsx`, `staff/eventDrawerTabs.ts`, `staff/EventOverview.tsx`,
   `staff/EventSeriesDrawer.tsx` and `staff/panels/DashboardPanel.tsx` as appropriate.
   Feed NextUpEvents the existing authorized event projection; this component does not
   create a global list or bypass permission-filtered queries.
2. **G + A/C/P, before submit acceptance:** wire v2 controlled `formState` /
   `onFormStateChange`, prefill/version/save-intent preparation and `memberFormInput`
   into their owned admission/contribution and existing non-lane consumers. Inject B/P
   authorized file selection through `renderAsset`. Legacy answer-only callbacks cannot
   by themselves transport save choices or DOB derivations. Preserve explicit date review;
   prefill GET is not owner confirmation.
3. **G, before image/publishing acceptance:** implement CoverPhotoEditor's
   `onSave(file, altText)` with the correct existing public-cover or private page-revision
   transport, persist alt text, install F's server canonicalization, and connect
   `onPendingChange` to publishing blocking. Saving a private cover draft must not alter
   an already released page. Wire accent preset persistence through G-owned event fields.
4. **G, before analytics acceptance:** register `event-programme` using F's
   `reports_events_programme.build_event_programme` at the existing report infrastructure.
5. **G, before feedback acceptance:** mount WordFeedbackRating in the existing supported
   event-feedback consumer with its actual schema revision's explicit mapping. Never
   infer or collapse an unknown historical numeric scale.
6. **G + F-UI verification, before security acceptance:** mount ProgrammeSessionBoundary
   around protected drawers/routes/cover trees for logout/context changes. Pass global
   401/403/404 denial into its `error` prop so externally revoked access also unmounts
   children and runs blob cleanup. Direct form/series/cover denial branches are tested;
   integrated logout/context/global-denial remounts still need browser tests in those
   G-owned callers. Test names should cover `auth context discards drafts and blobs` and
   `global permission withdrawal unmounts protected editors`.
7. **G, before commit:** add exact ignore exceptions for all six new test files above;
   repository ignore rules currently hide them from ordinary untracked status.
8. **G / visual QA owner, before final acceptance:** run integrated light/dark, 44px,
   keyboard, screen-reader, reduced-motion and real-browser contrast/cover-preview tests,
   plus the required Impeccable brand audit. Unit axe cannot establish browser contrast
   or actual canvas image appearance. Server-generated broadcast previews use
   `sandbox="allow-same-origin"` to load the application's Gilroy fonts while scripts,
   forms and popups remain blocked. Verify `document.fonts` loading in a real browser
   for both previews. Resolve findings before enabling the programme.
