// One programme: Members · Import · Card design · Settings, with the join link up top.
import { useState } from "react";

import { CardDesigner } from "../../../components/card-designer/CardDesigner";
import { ErrorBlock, Skeleton, Tabs } from "../../../components/ui";
import { ScreenHelp } from "../../help/HelpLink";
import { CardJobList } from "../../cards/cardJobs";
import { ProgrammeImport } from "./ProgrammeImport";
import { ProgrammeMembers } from "./ProgrammeMembers";
import { ProgrammeSettings } from "./ProgrammeSettings";
import { ApprovalLevelSelect } from "../../cards/ApprovalLevelSelect";
import { programmeJobsPath, useProgramme, useProgrammeApproval, useProgrammeDesign } from "./api";

type TabKey = "members" | "import" | "design" | "settings";

export function ProgrammePage({ programmeId, onBack, sheetImport = false }: {
  programmeId: number; onBack: () => void; sheetImport?: boolean;
}) {
  const programme = useProgramme(programmeId);
  const [tab, setTab] = useState<TabKey>("members");
  if (programme.isLoading) return <Skeleton className="h-64 w-full" />;
  if (programme.isError || !programme.data) return <ErrorBlock error={programme.error} resource="programme" onRetry={() => void programme.refetch()} />;
  const row = programme.data;
  const joinPath = `/o/${row.organization_slug}/ids/${row.slug}`;
  const tabs = [{ key: "members", label: "Members", count: row.counts.all }, ...(row.can_manage ? [{ key: "import", label: "Import" }] : []),
    { key: "design", label: "Card design" }, ...(row.can_manage ? [{ key: "settings", label: "Settings" }] : [])];
  return <div className="grid gap-4">
    <ScreenHelp screen="cards.programmes" />
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="grid gap-1">
        <button type="button" className="w-fit text-sm text-muted underline" onClick={onBack}>All programmes</button>
        <h2 className="text-xl font-semibold text-ink">{row.name}</h2>
        <p className="text-sm text-muted">Numbers look like {row.id_prefix}-{new Date().getFullYear()}-0001.</p>
      </div>
      {row.status === "active" && row.registration_open ? <div className="grid gap-1 rounded-control border border-line bg-panel p-3 text-sm">
        <span className="font-semibold text-ink">Join link</span>
        <code className="break-all text-xs text-muted">{window.location.origin}{joinPath}</code>
        <button type="button" className="desk-button-ghost min-h-11 w-fit"
          onClick={() => void navigator.clipboard?.writeText(`${window.location.origin}${joinPath}`)}>Copy link</button>
      </div> : <p className="text-sm text-muted">Joining is closed. Open it in Settings.</p>}
    </div>
    <Tabs tabs={tabs} activeKey={tab} label="Programme" onChange={(key) => setTab(key as TabKey)} />
    {tab === "members" ? <><CardJobList listPath={programmeJobsPath(row.id)} /><ProgrammeMembers programme={row} /></> : null}
    {tab === "import" ? <ProgrammeImport programme={row} onDone={() => setTab("members")} sheetImport={sheetImport} /> : null}
    {tab === "design" ? <ProgrammeDesign programmeId={row.id} canManage={row.can_manage} /> : null}
    {tab === "settings" ? <ProgrammeSettings programme={row} /> : null}
  </div>;
}

function ProgrammeDesign({ programmeId, canManage }: { programmeId: number; canManage: boolean }) {
  const design = useProgrammeDesign(programmeId);
  if (design.isLoading) return <Skeleton className="h-64 w-full" />;
  if (design.isError || !design.data) return <ErrorBlock error={design.error} resource="card design" />;
  return <div className="grid gap-4">
    {canManage ? <ProgrammeApproval programmeId={programmeId} /> : null}
    <CardDesigner designId={design.data.id} canEdit={design.data.can_edit} title="Programme card design" />
  </div>;
}

function ProgrammeApproval({ programmeId }: { programmeId: number }) {
  const { query, save } = useProgrammeApproval(programmeId);
  if (!query.data) return query.error ? <ErrorBlock error={query.error} resource="approval setting" /> : null;
  return <div className="grid max-w-md gap-1">
    <ApprovalLevelSelect label="Design changes for this programme" value={query.data.required} inherited={query.data.inherited}
      inheritLabel="Follow the organisation and space" disabled={save.isPending} onChange={(value) => save.mutate(value)} />
    {save.error ? <ErrorBlock error={save.error} /> : null}
  </div>;
}
