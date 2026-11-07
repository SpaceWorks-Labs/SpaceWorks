import { t } from "@lingui/core/macro";
import { ListRow, RelativeTime, StatusPill } from "../../../components/ui";
import { JOB_LABELS } from "./keyCopy";
import type { KeyJob } from "./spaceKeysApi";

const TONES = { running: "warn", completed: "success", failed: "danger" } as const;
const LABELS = { running: t`Running`, completed: t`Done`, failed: t`Failed` } as const;

/** Rotations, re-keys and re-indexes of this space, newest first; a running one shows its progress live. */
export function KeyJobsList({ jobs }: { jobs: KeyJob[] }) {
  if (!jobs.length) return <p className="text-sm text-muted">{t`No key jobs yet.`}</p>;
  return <div className="grid gap-2">{jobs.map(job => <ListRow key={job.id}
    title={t`${JOB_LABELS[job.kind]} · version ${job.from_version ?? "–"} → ${job.to_version}`}
    meta={<>started <RelativeTime date={job.started_at} exact /> {t` · ${job.rows_done} records done`}{job.rows_skipped ? t`, ${job.rows_skipped} skipped` : ""}{job.error_code ? ` · ${job.error_code}` : ""}</>}
    right={<StatusPill label={LABELS[job.status]} tone={TONES[job.status]} />} />)}
  </div>;
}
