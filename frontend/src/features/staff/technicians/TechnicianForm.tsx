import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Modal } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import { useSubjectOptions } from "../repairs/subjectsApi";
import {
  CHANNEL_LABELS, useArchiveTechnician, useOptInLink, useSaveTechnician, useWithdrawConsent,
  type Channel, type CoverageRow, type OptInLink, type Technician,
} from "./techniciansApi";

type Candidate = { person_id: number; name: string; is_technician: boolean };
const CHANNELS = Object.keys(CHANNEL_LABELS) as Channel[];

/** Add or change one technician. An in-house person's coverage is their Technician scope, so
 *  only the Space Manager sets it; a contractor's coverage only pre-selects them. */
export function TechnicianForm({ makerspaceId, technician, canSetCoverage, onClose }: {
  makerspaceId: number; technician: Technician | null; canSetCoverage: boolean; onClose: () => void;
}) {
  const save = useSaveTechnician(makerspaceId);
  const [kind, setKind] = useState<"external" | "in_house">(technician?.kind ?? "external");
  const [person, setPerson] = useState("");
  const [form, setForm] = useState({ name: technician?.name ?? "", email: technician?.email ?? "", phone: technician?.phone ?? "",
    telegram_handle: technician?.telegram_handle ?? "", notes: technician?.notes ?? "" });
  const [channels, setChannels] = useState<Channel[]>(technician?.channels ?? ["email"]);
  const [coverage, setCoverage] = useState<CoverageRow[]>(technician?.coverage ?? []);
  const candidates = useQuery({ queryKey: ["technicians", makerspaceId, "candidates"], enabled: !technician && kind === "in_house",
    queryFn: () => staffRequest<Candidate[]>(`/admin/makerspaces/${makerspaceId}/technicians/candidates`) });
  const types = useQuery({ queryKey: ["machine-types", makerspaceId, "technicians"],
    queryFn: () => staffRequest<{ id: number; name: string }[]>(`/admin/makerspace/${makerspaceId}/machine-types`).catch(() => []) });
  const rooms = useSubjectOptions(makerspaceId, "bookable_space").options;
  const coverageEditable = (technician?.kind ?? kind) === "external" || canSetCoverage;
  const has = (row: CoverageRow) => coverage.some(item => item.kind === row.kind && (item.id ?? null) === (row.id ?? null));
  const flip = (row: CoverageRow) => setCoverage(current => has(row)
    ? current.filter(item => !(item.kind === row.kind && (item.id ?? null) === (row.id ?? null))) : [...current, row]);
  const field = (name: keyof typeof form, label: string, type = "text") => <label className="eyebrow grid gap-1">{label}
    <input className="desk-input" type={type} value={form[name]} onChange={event => setForm(current => ({ ...current, [name]: event.target.value }))} /></label>;
  const ready = kind === "in_house" && !technician ? !!person : !!form.name.trim();
  return <Modal open title={technician ? technician.name : "Add technician"} onClose={onClose}>
    <form className="grid gap-3" onSubmit={event => {
      event.preventDefault();
      if (!ready) return;
      const body = { ...form, channels, ...(coverageEditable ? { coverage } : {}),
        ...(!technician && kind === "in_house" ? { person_id: Number(person) } : {}) };
      save.mutate({ id: technician?.id, body }, { onSuccess: onClose });
    }}>
      {!technician ? <fieldset className="flex flex-wrap gap-4 text-sm"><legend className="eyebrow mb-1">Who</legend>
        {(["external", "in_house"] as const).map(value => <label key={value} className="flex min-h-11 items-center gap-2">
          <input type="radio" name="kind" checked={kind === value} onChange={() => setKind(value)} />
          {value === "external" ? "Outside contractor (no account)" : "Someone on staff"}</label>)}
      </fieldset> : null}
      {!technician && kind === "in_house" ? <label className="eyebrow grid gap-1">Person<select className="desk-input" value={person}
        onChange={event => setPerson(event.target.value)}><option value="">Choose</option>
        {(candidates.data ?? []).map(row => <option key={row.person_id} value={row.person_id}>{row.name}{row.is_technician ? " (Technician)" : ""}</option>)}
      </select></label> : field("name", "Name")}
      <div className="grid gap-3 sm:grid-cols-2">{field("email", "Email", "email")}{field("phone", "Phone (for WhatsApp or SMS)", "tel")}</div>
      {field("telegram_handle", "Telegram handle (optional)")}
      <fieldset className="flex flex-wrap gap-4 text-sm"><legend className="eyebrow mb-1">Send repairs by</legend>
        {CHANNELS.map(channel => <label key={channel} className="flex min-h-11 items-center gap-2">
          <input type="checkbox" checked={channel === "email" || channels.includes(channel)} disabled={channel === "email"}
            onChange={() => setChannels(current => current.includes(channel) ? current.filter(item => item !== channel) : [...current, channel])} />
          {CHANNEL_LABELS[channel]}{channel !== "email" && technician && !technician.consent[channel] ? " (needs opt-in)" : ""}</label>)}
      </fieldset>
      {coverageEditable ? <fieldset className="grid gap-1 text-sm"><legend className="eyebrow mb-1">Covers</legend>
        <label className="flex min-h-11 items-center gap-2"><input type="checkbox" checked={has({ kind: "inventory", id: null })}
          onChange={() => flip({ kind: "inventory", id: null })} />All inventory items</label>
        {(types.data ?? []).map(row => <label key={`t${row.id}`} className="flex min-h-11 items-center gap-2"><input type="checkbox"
          checked={has({ kind: "machine_type", id: row.id })} onChange={() => flip({ kind: "machine_type", id: row.id })} />{row.name}</label>)}
        {rooms.map(row => <label key={`r${row.id}`} className="flex min-h-11 items-center gap-2"><input type="checkbox"
          checked={has({ kind: "room", id: row.id })} onChange={() => flip({ kind: "room", id: row.id })} />{row.label}</label>)}
      </fieldset> : <p className="text-sm text-muted">Only the Space Manager sets what an in-house technician covers.</p>}
      <label className="eyebrow grid gap-1">Notes<textarea className="desk-input min-h-20" value={form.notes}
        onChange={event => setForm(current => ({ ...current, notes: event.target.value }))} /></label>
      {technician ? <TechnicianExtras technician={technician} onArchived={onClose} /> : null}
      {save.error ? <p role="alert" className="text-sm text-danger">{save.error.message}</p> : null}
      <div className="flex flex-wrap justify-end gap-2 border-t border-line pt-3">
        <button type="button" className="desk-button-ghost" onClick={onClose}>Cancel</button>
        <button type="submit" className="desk-button-primary" disabled={!ready || save.isPending}>{save.isPending ? "Saving…" : "Save"}</button>
      </div>
    </form>
  </Modal>;
}

function TechnicianExtras({ technician, onArchived }: { technician: Technician; onArchived: () => void }) {
  const link = useOptInLink();
  const withdraw = useWithdrawConsent();
  const archive = useArchiveTechnician();
  const [sent, setSent] = useState<OptInLink | null>(null);
  return <div className="grid gap-2 rounded-xl border border-line p-3 text-sm">
    <div className="flex flex-wrap gap-2">
      <button type="button" className="desk-button-ghost" disabled={link.isPending}
        onClick={() => link.mutate(technician.id, { onSuccess: setSent })}>Send chat opt-in link</button>
      {(["telegram", "whatsapp", "sms"] as const).filter(channel => technician.consent[channel]).map(channel =>
        <button key={channel} type="button" className="desk-button-ghost" onClick={() => withdraw.mutate({ id: technician.id, channel })}>
          Stop {CHANNEL_LABELS[channel]}</button>)}
      {!technician.is_archived ? <button type="button" className="desk-button-danger"
        onClick={() => archive.mutate(technician.id, { onSuccess: onArchived })}>Archive</button> : null}
    </div>
    {sent ? <p className="break-words">{sent.emailed ? "Emailed. " : ""}Link: <span className="font-mono">{sent.url}</span>.
      For Telegram they send <span className="font-mono">{sent.telegram_start}</span> to your space's bot.</p> : null}
    {link.error || withdraw.error || archive.error ? <p role="alert" className="text-danger">
      {(link.error ?? withdraw.error ?? archive.error)?.message}</p> : null}
  </div>;
}
