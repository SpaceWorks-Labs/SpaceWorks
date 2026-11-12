// One programme: Members · Import · Card design · Settings, with the join link up top.
import { t } from "@lingui/core/macro";
import { useState } from "react";

import { CardDesigner } from "../../../components/card-designer/CardDesigner";
import { ErrorBlock, Tabs } from "../../../components/ui";
import { ScreenHelp } from "../../help/HelpLink";
import { CardJobList } from "../../cards/cardJobs";
import { ProgrammeImport } from "./ProgrammeImport";
import { ProgrammeArchivedBanner, RemoveProgramme } from "./ProgrammeLifecycle";
import { ProgrammeMembers } from "./ProgrammeMembers";
import { ProgrammeSettings } from "./ProgrammeSettings";
import { ApprovalLevelSelect } from "../../cards/ApprovalLevelSelect";
import { programmeJobsPath, useProgramme, useProgrammeApproval, useProgrammeDesign } from "./api";
import { LogoLoader } from "../../../components/LogoLoader";

type TabKey = "members" | "import" | "design" | "settings";

export function ProgrammePage({ programmeId, onBack, sheetImport = false }: {
  programmeId: number; onBack: () => void; sheetImport?: boolean;
}) {
  const programme = useProgramme(programmeId);
  const [tab, setTab] = useState<TabKey>("members");
  if (programme.isLoading) return <LogoLoader size={48} className="min-h-64 py-3" />;
  if (programme.isError || !programme.data) return <ErrorBlock error={programme.error} resource={t`programme`} onRetry={() => void programme.refetch()} />;
  const row = programme.data;
  const joinPath = `/o/${row.organization_slug}/ids/${row.slug}`;
  const tabs = [{ key: "members", label: t`Members`, count: row.counts.all }, ...(row.can_manage ? [{ key: "import", label: t`Import` }] : []),
    { key: "design", label: t`Card design` }, ...(row.can_manage ? [{ key: "settings", label: t`Settings` }] : [])];
  return <div className="grid gap-4">
    <ScreenHelp screen="cards.programmes" />
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="grid gap-1">
        <button type="button" className="w-fit text-sm text-muted underline" onClick={onBack}>{t`All programmes`}</button>
        <h2 className="text-xl font-semibold text-ink">{row.name}</h2>
        <p className="text-sm text-muted">{t`Numbers look like ${row.id_prefix}-${new Date().getFullYear()}-0001.`}</p>
      </div>
      {row.status === "active" && row.registration_open ? <div className="grid gap-1 rounded-control border border-line bg-panel p-3 text-sm">
        <span className="font-semibold text-ink">{t`Join link`}</span>
        <code className="break-all text-xs text-muted">{window.location.origin}{joinPath}</code>
        <button type="button" className="desk-button-ghost min-h-11 w-fit"
          onClick={() => void navigator.clipboard?.writeText(`${window.location.origin}${joinPath}`)}>{t`Copy link`}</button>
      </div> : <p className="text-sm text-muted">{t`Joining is closed. Open it in Settings.`}</p>}
    </div>
    <ProgrammeArchivedBanner programme={row} />
    <Tabs tabs={tabs} activeKey={tab} label={t`Programme`} onChange={(key) => setTab(key as TabKey)} />
    {tab === "members" ? <><CardJobList listPath={programmeJobsPath(row.id)} /><ProgrammeMembers programme={row} /></> : null}
    {tab === "import" ? <ProgrammeImport programme={row} onDone={() => setTab("members")} sheetImport={sheetImport} /> : null}
    {tab === "design" ? <ProgrammeDesign programmeId={row.id} makerspaceId={row.makerspace} canManage={row.can_manage} /> : null}
    {tab === "settings" ? <><ProgrammeSettings programme={row} /><RemoveProgramme programme={row} onDeleted={onBack} /></> : null}
  </div>;
}

function ProgrammeDesign({ programmeId, makerspaceId, canManage }: { programmeId: number; makerspaceId: number; canManage: boolean }) {
  const design = useProgrammeDesign(programmeId);
  if (design.isLoading) return <LogoLoader size={48} className="min-h-64 py-3" />;
  if (design.isError || !design.data) return <ErrorBlock error={design.error} resource={t`card design`} />;
  return <div className="grid gap-4">
    {canManage ? <ProgrammeApproval programmeId={programmeId} /> : null}
    <CardDesigner designId={design.data.id} makerspaceId={makerspaceId} canEdit={design.data.can_edit} title={t`Programme card design`} />
  </div>;
}

function ProgrammeApproval({ programmeId }: { programmeId: number }) {
  const { query, save } = useProgrammeApproval(programmeId);
  if (!query.data) return query.error ? <ErrorBlock error={query.error} resource={t`approval setting`} /> : null;
  return <div className="grid max-w-md gap-1">
    <ApprovalLevelSelect label={t`Design changes for this programme`} value={query.data.required} inherited={query.data.inherited}
      inheritLabel="Follow the organisation and space" disabled={save.isPending} onChange={(value) => save.mutate(value)} />
    {save.error ? <ErrorBlock error={save.error} /> : null}
  </div>;
}
