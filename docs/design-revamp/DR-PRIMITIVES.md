# dr-primitives handoff

Branch: `lane/dr-primitives`. Wave 2a. Changes remain unstaged and uncommitted.

## Exported component API

Import values and exported types from `frontend/src/components/ui/index.ts`.

| Component | Props type |
| --- | --- |
| `PageHeader` | `PageHeaderProps & PageHeaderDetailSlots` |
| `Tabs` | `TabsProps` |
| `StatCard` | `StatCardProps (= Stat)` |
| `StatRow` | `StatRowProps` |
| `ListRow` | `ListRowProps` |
| `DateChip` | `DateChipProps` |
| `IdentityChip` | `IdentityChipProps` |
| `StatusPill` | `StatusPillProps` |
| `Callout` | `CalloutProps` |
| `SettingsSection` | `SettingsSectionProps` |
| `SettingsRow` | `SettingsRowProps` |
| `SettingsActions` | `SettingsActionsProps` |
| `DangerZone` | `DangerZoneProps` |
| `ActivityRail` | `ActivityRailProps` |
| `ActivityItem` | `ActivityItemProps` |
| `Avatar` | `AvatarProps` |
| `SegmentedControl` | `SegmentedControlProps` |
| `KeyValueCard` | `KeyValueCardProps` |
| `TicketCard` | `TicketCardProps` |
| `OverflowMenu` | `OverflowMenuProps` |
| `ProgressBar` | `ProgressBarProps` |
| `RelativeTime` | `RelativeTimeProps` |
| `ActionControl` | `ActionControlProps` |
| `Icon` | `IconProps` |
| `Badge` | `BadgeProps` |
| `StatusBadge` | `StatusBadgeProps` |
| `Card` | `CardProps` |
| `Field` | `FieldProps` |
| `Modal` | `ModalProps` |
| `ConfirmDialog` | `ConfirmDialogProps` |
| `DetailDrawer` | `DetailDrawerProps` |
| `DataTable` | `DataTableProps<T>` |
| `EmptyState` | `EmptyStateProps` |
| `Metric` | `MetricProps` |
| `FilterBar` | `FilterBarProps` |
| `BulkActionToolbar` | `BulkActionToolbarProps` |
| `ErrorBlock` | `ErrorBlockProps` |
| `ErrorText` | `ErrorTextProps` |
| `Pagination` | `PaginationProps` |
| `Skeleton` | `SkeletonProps` |
| `SkeletonRows` | `SkeletonRowsProps` |
| `ToastHost` | `no props` |
| `CameraCapture` | `CameraCaptureProps (retained; infer with ComponentProps)` |
| `CollapsibleSection` | `CollapsibleSectionProps (retained; infer with ComponentProps)` |
| `IconButton / IconLink` | `IconButtonProps / IconLinkProps (retained; infer with ComponentProps)` |
| `Spinner` | `no props (retained)` |

Other exports: `statusToneMap`, `formatRelativeTime`, `StatusBadgeTone`, `DataTableColumn<T>` and the slot types `Action`, `SecondaryAction`, `Tab`, `Stat`, `CalloutProps`, `Identity`, `QueryState`, `EmptyProps`, `PageHeaderProps`, `IconName`, `Tone`.

The shared slot declarations in `types.ts` preserve the spec contracts. `IconName` is the union of the explicitly mapped Lucide names in `icon.tsx`. PageHeader adds separate detail slots (`back`, `identity`, `status`) without changing the shared header type.

## Composition and compatibility

- Presentational primitives own local interaction state only. React/TanStack Query callers retain server state, permissions, mutations and invalidation.
- `ActionControl` centralises disabled/pending actions, reasons, confirmation ellipses and external-link attributes. `useRovingFocus.ts` centralises arrow/Home/End traversal for tabs, segmented controls and menus.
- Status words/maps remain unchanged. Badge and StatusBadge render through StatusPill; attention stats use an emphasis pill while values stay ink.
- `EmptyState` accepts the new `EmptyProps` message/action shape for heading-free P17 empties. Legacy title/description/action callers keep their heading and separate description, protecting existing queries and screen-reader navigation until wave 3.
- `ErrorBlock`/`ErrorText` accept optional `resource` and `onRetry` for the standard load-error sentence and Retry. Legacy raw error/validation messages remain visible.
- Field associates hints/errors through IDs while preserving explicit caller labels/descriptions. This keeps the input name short and its description useful.
- DataTable uses one table DOM with explicit roles and CSS reflow below md. The compact sort header and select-all remain reachable. CSS-generated, aria-hidden labels avoid duplicate cell text; empty-header cells have no label. Existing ordering, visibility, density, loading, identity and cross-page selection logic remains intact.
- Primary controls use the existing 10px control radius from PLAN section 0. Cards use existing panel/radius tokens; status tags remain round. No new colour values or token changes.

## Files changed

All paths below are relative to `frontend/src/components/ui/` unless prefixed with `docs/`.

Modified existing source:

- `Badge.tsx`
- `BulkActionToolbar.tsx`
- `Card.tsx`
- `ConfirmDialog.tsx`
- `DataTable.tsx`
- `DetailDrawer.tsx`
- `EmptyState.tsx`
- `ErrorBlock.tsx`
- `ErrorText.tsx`
- `Field.tsx`
- `FilterBar.tsx`
- `ListColumns.tsx`
- `Metric.tsx`
- `Modal.tsx`
- `Pagination.tsx`
- `Skeleton.tsx`
- `StatusBadge.tsx`
- `ToastHost.tsx`
- `index.ts`

Added source:

- `ActionControl.tsx`
- `ActivityItem.tsx`
- `ActivityRail.tsx`
- `Avatar.tsx`
- `Callout.tsx`
- `DangerZone.tsx`
- `DateChip.tsx`
- `IdentityChip.tsx`
- `KeyValueCard.tsx`
- `ListRow.tsx`
- `OverflowMenu.tsx`
- `PageHeader.tsx`
- `ProgressBar.tsx`
- `RelativeTime.tsx`
- `SegmentedControl.tsx`
- `SettingsActions.tsx`
- `SettingsRow.tsx`
- `SettingsSection.tsx`
- `StatCard.tsx`
- `StatRow.tsx`
- `StatusPill.tsx`
- `Tabs.tsx`
- `TicketCard.tsx`
- `icon.tsx`
- `tones.ts`
- `types.ts`
- `useRovingFocus.ts`

Added ignored tests:

- `ActionControl.test.tsx`
- `ActivityItem.test.tsx`
- `ActivityRail.test.tsx`
- `Avatar.test.tsx`
- `Badge.test.tsx`
- `BulkActionToolbar.test.tsx`
- `Callout.test.tsx`
- `Card.test.tsx`
- `ConfirmDialog.test.tsx`
- `DangerZone.test.tsx`
- `DataTable.reflow.test.tsx`
- `DateChip.test.tsx`
- `DetailDrawer.test.tsx`
- `EmptyState.test.tsx`
- `ErrorBlock.test.tsx`
- `ErrorText.test.tsx`
- `Field.test.tsx`
- `FilterBar.test.tsx`
- `IdentityChip.test.tsx`
- `KeyValueCard.test.tsx`
- `ListRow.test.tsx`
- `Metric.test.tsx`
- `Modal.test.tsx`
- `OverflowMenu.keyboard.test.tsx`
- `OverflowMenu.test.tsx`
- `PageHeader.test.tsx`
- `Pagination.test.tsx`
- `ProgressBar.test.tsx`
- `RelativeTime.refresh.test.tsx`
- `RelativeTime.test.tsx`
- `SegmentedControl.test.tsx`
- `SettingsActions.test.tsx`
- `SettingsRow.test.tsx`
- `SettingsSection.test.tsx`
- `Skeleton.test.tsx`
- `SkeletonRows.test.tsx`
- `StatCard.test.tsx`
- `StatRow.test.tsx`
- `StatusBadge.test.tsx`
- `StatusPill.test.tsx`
- `Tabs.state.test.tsx`
- `Tabs.test.tsx`
- `TicketCard.test.tsx`
- `icon.test.tsx`

Added handoff files:

- `docs/design-revamp/DR-PRIMITIVES.md` (this report)
- `docs/design-revamp/seeds/dr-primitives-tests.sha256` (SHA-256 of every new ignored test)

No test deletions or renames. Seeded UI tests changed: none. Existing tests retain their original assertions.

## Verification

Run from `frontend/`: `npx tsc -b`, `npx vitest run`, `npm run build`. Windows invokes the same npm executables via `.cmd` because PowerShell blocks the `.ps1` shims. Final results are reported in the task response.

The local Codex CLI doctor reports unavailable configuration/provider connectivity, so no separate CLI review is claimed. The browser tool reports no available browser, so no visual/browser contrast pass is claimed. Unit axe uses `src/test/axe.ts` and does not measure rendered colour contrast. Temporary preview files and the dev process were removed after the unavailable-browser check.
