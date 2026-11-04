import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Callout, Field, Modal, SegmentedControl } from "../../components/ui";
import { presenceApi, presenceKeys, usePresenceMutations, type PresenceStartInput } from "./api";
import { LOCATION_FAILURE_TEXT, locationPermission, readLocation, type LocationFailure } from "./location";
import { presenceErrorText, presetLabel, STAFF_ALTERNATIVE, STATUS_LABELS } from "./presenceCopy";

export type PresenceCheckInSheetProps = {
  slug: string; open: boolean; onClose: () => void; presets: number[];
  /** An active member here may work or visit; anyone else checks in as a guest (server-enforced). */
  member: boolean;
  /** A staff-issued claim session cannot read or edit durable display preferences. */
  claim?: boolean;
  /** The makerspace has a configured geofence; without one, self check-in is always refused. */
  selfCheckIn: boolean;
  /** undefined = not yet known (no session seen); the server still applies the real rule. */
  optOutAllowed?: boolean;
};

type Phase = { kind: "idle" } | { kind: "locating" } | { kind: "failed"; reason: LocationFailure };

export function PresenceCheckInSheet({ slug, open, onClose, presets, member, claim = false, selfCheckIn, optOutAllowed }: PresenceCheckInSheetProps) {
  const { start } = usePresenceMutations(slug);
  const [minutes, setMinutes] = useState(() => presets.includes(120) ? 120 : presets[0]);
  const [status, setStatus] = useState<"working" | "visiting">("visiting");
  const [projectId, setProjectId] = useState<number | null>(null);
  const [hide, setHide] = useState<boolean | null>(null);
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const [blocked, setBlocked] = useState(false);
  const projects = useQuery({ queryKey: presenceKeys.projects(slug), queryFn: () => presenceApi.projects(slug), enabled: open && member, retry: false });
  const preference = useQuery({ queryKey: presenceKeys.preference(slug), queryFn: () => presenceApi.preference(slug), enabled: open && !claim && optOutAllowed !== false, retry: false });
  useEffect(() => {
    if (!open) return;
    let live = true;
    void locationPermission().then((state) => { if (live) setBlocked(state === "denied"); });
    return () => { live = false; };
  }, [open]);
  const projectRows = projects.data?.results ?? [];
  const hideValue = hide ?? preference.data?.hide_on_display ?? false;
  const needsProject = member && status === "working" && projectId === null;
  const close = () => { setPhase({ kind: "idle" }); start.reset(); onClose(); };

  const submit = async () => {
    start.reset();
    setPhase({ kind: "locating" });
    const outcome = await readLocation();
    if (!outcome.ok) { setPhase({ kind: "failed", reason: outcome.reason }); return; }
    setPhase({ kind: "idle" });
    const input: PresenceStartInput = { duration_minutes: minutes, ...outcome.reading,
      status: member ? status : "guest", ...(member && status === "working" ? { project_id: projectId } : {}),
      ...(optOutAllowed !== false ? { hide_on_display: hideValue } : {}) };
    start.mutate(input, { onSuccess: close });
  };

  const failure = phase.kind === "failed" ? LOCATION_FAILURE_TEXT[phase.reason] : blocked && phase.kind === "idle" && !start.error ? LOCATION_FAILURE_TEXT.denied : null;
  const serverError = start.error ? presenceErrorText(start.error) : null;
  const busy = phase.kind === "locating" || start.isPending;
  const disabledReason = !selfCheckIn ? "Self check-in isn't set up here." : needsProject ? "Choose one of your projects." : undefined;

  return <Modal open={open} onClose={close} title="Check in" footer={<div className="flex flex-wrap justify-end gap-3">
    <button type="button" className="desk-button" onClick={close}>Cancel</button>
    <button type="button" className="desk-button-brand" disabled={busy || Boolean(disabledReason)} aria-describedby={disabledReason ? "presence-checkin-reason" : undefined} onClick={() => void submit()}>
      {phase.kind === "locating" ? "Finding your location…" : start.isPending ? "Checking in…" : "Check in"}</button>
  </div>}>
    <div className="grid gap-5">
      {!selfCheckIn ? <Callout size="inline" tone="warn" lead="Self check-in isn't set up here." body={STAFF_ALTERNATIVE} /> : <p className="text-sm text-muted">We use your location once to confirm you're inside the makerspace. It isn't stored.</p>}
      <div className="grid gap-2"><span className="text-sm font-semibold text-ink">How long are you staying?</span>
        <SegmentedControl fullWidth label="How long are you staying?" value={String(minutes)} onChange={(value) => setMinutes(Number(value))}
          options={presets.map((value) => ({ value: String(value), label: presetLabel(value) }))} /></div>
      {member ? <div className="grid gap-2"><span className="text-sm font-semibold text-ink">What are you here for?</span>
        <SegmentedControl fullWidth label="What are you here for?" value={status} onChange={(value) => setStatus(value as "working" | "visiting")}
          options={[{ value: "working", label: STATUS_LABELS.working }, { value: "visiting", label: STATUS_LABELS.visiting }]} /></div>
        : <p className="text-sm text-muted">You'll check in as a <strong className="text-ink">guest</strong>.</p>}
      {member && status === "working" ? <ProjectPicker loading={projects.isLoading} error={projects.isError} rows={projectRows} value={projectId} onChange={setProjectId} /> : null}
      {optOutAllowed === false ? <p className="text-sm text-muted">This space's “who's in” display shows names, and hiding yours isn't offered here.</p>
        : <label className="flex min-h-11 items-start gap-3 text-sm"><input type="checkbox" role="switch" className="mt-0.5 h-5 w-5 accent-accent" checked={hideValue} onChange={(event) => setHide(event.target.checked)} />
          <span><span className="font-semibold text-ink">Hide me on the display</span><span className="block text-muted">{optOutAllowed ? "You'll appear as “A member” or “A guest”." : "Applies if this space lets people hide their name; you'll see the outcome after checking in."}</span></span></label>}
      {disabledReason && selfCheckIn ? <p id="presence-checkin-reason" className="text-sm text-muted">{disabledReason}</p> : null}
      {failure ? <div role="alert"><Callout size="inline" tone="warn" lead={failure} body={STAFF_ALTERNATIVE} /></div> : null}
      {serverError ? <div role="alert"><Callout size="inline" tone="danger" lead={serverError.text} body={serverError.staffRoute ? STAFF_ALTERNATIVE : undefined} /></div> : null}
    </div>
  </Modal>;
}

function ProjectPicker({ loading, error, rows, value, onChange }: { loading: boolean; error: boolean;
  rows: { id: number; title: string; public_visible: boolean }[]; value: number | null; onChange: (id: number | null) => void }) {
  if (loading) return <p role="status" className="text-sm text-muted">Loading your projects…</p>;
  if (error) return <p role="alert" className="text-sm text-danger">Couldn't load your projects. Choose Visiting, or retry later.</p>;
  if (!rows.length) return <p className="text-sm text-muted">You have no projects on your profile yet. Add one to your profile, or check in as Visiting.</p>;
  return <Field label="Which project?" hint="Private projects are never named on the display.">
    <select className="desk-input max-w-full" value={value ?? ""} onChange={(event) => onChange(event.target.value ? Number(event.target.value) : null)}>
      <option value="">Choose a project</option>
      {rows.map((row) => <option key={row.id} value={row.id}>{row.public_visible ? row.title : `${row.title} (private)`}</option>)}
    </select>
  </Field>;
}
