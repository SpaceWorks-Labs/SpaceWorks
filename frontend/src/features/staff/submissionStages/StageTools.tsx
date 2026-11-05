import { useState } from "react";
import { CollapsibleSection, ErrorText, Field } from "../../../components/ui";
import { deadlineText } from "../../events/stageTime";
import { useStageCommands } from "./api";
import { fromInput, stageErrorMessage, toInput } from "./stageDraft";
import { StageShortlistPanel } from "./StageShortlistPanel";
import type { SavedStage } from "./types";

/** Per saved stage: its shortlist (when it ends with one) and per-team deadline extensions (S2). */
export function StageTools({ eventId, stage, timezone }: { eventId: number; stage: SavedStage; timezone: string }) {
  const [open, setOpen] = useState<"" | "shortlist" | "extensions">("");
  if (stage.id === null) return null;
  const saved = { ...stage, id: stage.id };
  const toggle = (name: "shortlist" | "extensions") => setOpen(open === name ? "" : name);
  return <div className="grid gap-3">
    {stage.shortlist_after ? <CollapsibleSection title={stage.shortlist_label || "Shortlist"} open={open === "shortlist"} onToggle={() => toggle("shortlist")}>
      {open === "shortlist" ? <StageShortlistPanel eventId={eventId} stage={saved} /> : null}</CollapsibleSection> : null}
    <CollapsibleSection title="Deadline extensions" count={stage.extensions?.length ?? 0} open={open === "extensions"} onToggle={() => toggle("extensions")}>
      {open === "extensions" ? <Extensions eventId={eventId} stage={saved} timezone={timezone} /> : null}</CollapsibleSection>
  </div>;
}

function Extensions({ eventId, stage, timezone }: { eventId: number; stage: SavedStage & { id: number }; timezone: string }) {
  const { extend } = useStageCommands(eventId, stage.id);
  const [team, setTeam] = useState(""); const [until, setUntil] = useState(""); const [reason, setReason] = useState("");
  return <div className="grid gap-3">
    <ul className="grid gap-1 text-sm">{(stage.extensions ?? []).map(row => <li key={row.id}>{`${row.team_name ?? `Team ${row.team_id}`}: until ${deadlineText(row.until, timezone)}. ${row.reason}`}</li>)}</ul>
    <form className="grid gap-3 md:grid-cols-3" onSubmit={event => { event.preventDefault();
      extend.mutate({ team_id: Number(team), until: fromInput(until)!, reason }, { onSuccess: () => { setTeam(""); setUntil(""); setReason(""); } }); }}>
      <Field label="Team ID"><input className="desk-input min-h-11" type="number" min={1} required value={team} onChange={e => setTeam(e.target.value)} /></Field>
      <Field label="New deadline (UTC)"><input className="desk-input min-h-11" type="datetime-local" required value={toInput(fromInput(until))} onChange={e => setUntil(e.target.value)} /></Field>
      <Field label="Reason"><input className="desk-input min-h-11" required maxLength={1000} value={reason} onChange={e => setReason(e.target.value)} /></Field>
      <button type="submit" className="desk-button min-h-11 justify-self-start" disabled={extend.isPending}>Extend this team's deadline</button>
    </form>
    <p className="text-sm text-muted">Work submitted after the stage deadline is still marked late.</p>
    {extend.error ? <ErrorText message={stageErrorMessage(extend.error)} /> : null}
  </div>;
}
