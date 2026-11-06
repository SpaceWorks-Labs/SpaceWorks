// ID programmes this space hosts for an organisation it belongs to: pick the organisation,
// see its programmes with their counts, start a new one from a preset, open one.
import { t } from "@lingui/core/macro";
import { useState } from "react";

import { Badge, EmptyState, ErrorBlock, Skeleton } from "../../../components/ui";
import { ScreenHelp } from "../../help/HelpLink";
import { useOrganizations } from "../../staff/organizationsApi";
import { ProgrammePage } from "./ProgrammePage";
import { useCreateProgramme, useProgrammes, type Programme } from "./api";

const STATUS_TONE = { draft: "neutral", active: "success", closed: "warn" } as const;
const STATUS_LABEL = { draft: t`Draft`, active: t`Open`, closed: t`Closed` } as const;
const PRESETS = [{ value: "", label: t`Blank` }, { value: "students", label: t`Student ID` },
  { value: "volunteers", label: t`Volunteer ID` }, { value: "staff", label: t`Staff ID` }];

export function ProgrammesTab({ makerspaceId, sheetImport = false }: { makerspaceId: number; sheetImport?: boolean }) {
  const organizations = useOrganizations({ active: true });
  const [organizationId, setOrganizationId] = useState<number | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const chosen = organizationId ?? organizations.data?.results[0]?.id ?? null;
  const programmes = useProgrammes(chosen);
  const rows = (programmes.data ?? []).filter((row) => row.makerspace === makerspaceId);
  if (open !== null) return <ProgrammePage programmeId={open} onBack={() => setOpen(null)} sheetImport={sheetImport} />;
  if (organizations.isLoading) return <Skeleton className="h-40 w-full" />;
  if (organizations.isError) return <ErrorBlock error={organizations.error} resource="organisations" />;
  if (!organizations.data?.results.length) return <EmptyState title={t`No organisations yet`}
    description={t`ID programmes belong to an organisation that owns this space. Add one under Organisations first.`} />;

  return <div className="grid gap-4">
    <ScreenHelp screen="cards.programmes" />
    <label className="grid max-w-sm gap-1 text-xs font-semibold text-muted"><span>{t`Organisation`}</span>
      <select className="desk-input min-h-11" value={chosen ?? ""} onChange={(event) => setOrganizationId(Number(event.target.value))}>
        {organizations.data.results.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
      </select>
    </label>
    {chosen !== null ? <NewProgramme organizationId={chosen} makerspaceId={makerspaceId} onCreated={setOpen} /> : null}
    {programmes.isLoading ? <Skeleton className="h-24 w-full" /> : null}
    {programmes.isError ? <ErrorBlock error={programmes.error} resource="programmes" /> : null}
    {programmes.data && !rows.length ? <p className="text-sm text-muted">{t`No programmes yet for this organisation here.`}</p> : null}
    <ul className="grid gap-3 sm:grid-cols-2">
      {rows.map((row) => <ProgrammeCardRow key={row.id} programme={row} onOpen={() => setOpen(row.id)} />)}
    </ul>
  </div>;
}

function ProgrammeCardRow({ programme, onOpen }: { programme: Programme; onOpen: () => void }) {
  return <li className="grid gap-2 rounded-card border border-line bg-panel p-4">
    <div className="flex items-start justify-between gap-2">
      <h3 className="text-base font-semibold text-ink">{programme.name}</h3>
      <Badge tone={STATUS_TONE[programme.status]}>{STATUS_LABEL[programme.status]}</Badge>
    </div>
    <p className="text-sm text-muted">{t`${programme.counts.approved} approved · ${programme.counts.pending} waiting · ${programme.counts.all} in all`}{programme.registration_open ? t` · joining open` : ""}</p>
    <div><button type="button" className="desk-button min-h-11" onClick={onOpen}>{t`Open`}</button></div>
  </li>;
}

function NewProgramme({ organizationId, makerspaceId, onCreated }: { organizationId: number; makerspaceId: number;
  onCreated: (id: number) => void }) {
  const create = useCreateProgramme(organizationId);
  const [name, setName] = useState("");
  const [preset, setPreset] = useState("");
  return <form className="flex flex-wrap items-end gap-2" onSubmit={(event) => {
    event.preventDefault();
    create.mutate({ makerspace_id: makerspaceId, name: name.trim(), preset }, { onSuccess: (row) => { setName(""); onCreated(row.id); } });
  }}>
    <label className="grid gap-1 text-xs font-semibold text-muted"><span>{t`New programme`}</span>
      <input className="desk-input min-h-11" value={name} maxLength={80} placeholder={t`Student ID 2026`}
        onChange={(event) => setName(event.target.value)} /></label>
    <label className="grid gap-1 text-xs font-semibold text-muted"><span>{t`Start from`}</span>
      <select className="desk-input min-h-11" value={preset} onChange={(event) => setPreset(event.target.value)}>
        {PRESETS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
      </select></label>
    <button type="submit" className="desk-button-primary min-h-11" disabled={name.trim().length < 2 || create.isPending}>
      {create.isPending ? t`Creating…` : t`Create`}</button>
    {create.error ? <div className="basis-full"><ErrorBlock error={create.error} /></div> : null}
  </form>;
}
