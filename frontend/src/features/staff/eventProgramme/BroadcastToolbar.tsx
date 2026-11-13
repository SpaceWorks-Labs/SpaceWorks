import { t } from "@lingui/core/macro";
import { useState, type ReactNode, type RefObject } from "react";
import { Bold, Heading2, Heading3, Italic, Link, List, ListOrdered, Quote } from "lucide-react";
import { insertAt, LINK_PLACEHOLDERS, linkMarkdown, linkTargetOk, prefixLines, TEXT_PLACEHOLDERS, wrapSelection, type TextEdit } from "./markdownEdit";

const PLACEHOLDER_LABEL = (key: string) => ({
  name: t`Guest name`, event_title: t`Event title`, event_date: t`Event date`, event_location: t`Event location`, organization: t`Organiser`,
  event_url: t`Event page`, ticket_url: t`Their ticket`, schedule_url: t`Schedule`, feedback_url: t`Feedback form`,
})[key] ?? key;

function Tool({ label, onClick, children, pressed }: { label: string; onClick: () => void; children: ReactNode; pressed?: boolean }) {
  return <button type="button" className="desk-button min-h-11 min-w-11 px-2" aria-label={label} title={label} aria-pressed={pressed}
    onMouseDown={event => event.preventDefault()} onClick={onClick}>{children}</button>;
}

/**
 * Formatting for the broadcast message (B21): bold, italic, headings, quotes, lists, links and placeholders.
 * It edits the Markdown text in place; the server renders the same safe subset and refuses anything else.
 */
export function BroadcastToolbar({ field, value, onChange, disabled }: {
  field: RefObject<HTMLTextAreaElement | null>; value: string; onChange: (value: string) => void; disabled?: boolean;
}) {
  const [linking, setLinking] = useState<{ start: number; end: number } | null>(null);
  const [label, setLabel] = useState("");
  const [target, setTarget] = useState("https://");
  const apply = (edit: (text: string, start: number, end: number) => TextEdit) => {
    const node = field.current;
    const start = node?.selectionStart ?? value.length, end = node?.selectionEnd ?? value.length;
    const next = edit(value, start, end);
    onChange(next.text);
    requestAnimationFrame(() => { node?.focus(); node?.setSelectionRange(next.start, next.end); });
  };
  const openLink = () => {
    const node = field.current;
    const start = node?.selectionStart ?? value.length, end = node?.selectionEnd ?? value.length;
    setLinking({ start, end }); setLabel(value.slice(start, end).slice(0, 80)); setTarget("https://");
  };
  const valid = label.trim().length > 0 && linkTargetOk(target.trim());
  if (disabled) return null;
  return <div className="grid gap-2">
    <div role="toolbar" aria-label={t`Formatting`} className="flex flex-wrap items-center gap-1">
      <Tool label={t`Bold`} onClick={() => apply((text, s, e) => wrapSelection(text, s, e, "**", t`bold text`))}><Bold size={18} aria-hidden="true" /></Tool>
      <Tool label={t`Italic`} onClick={() => apply((text, s, e) => wrapSelection(text, s, e, "*", t`italic text`))}><Italic size={18} aria-hidden="true" /></Tool>
      <Tool label={t`Heading`} onClick={() => apply((text, s, e) => prefixLines(text, s, e, "## "))}><Heading2 size={18} aria-hidden="true" /></Tool>
      <Tool label={t`Subheading`} onClick={() => apply((text, s, e) => prefixLines(text, s, e, "### "))}><Heading3 size={18} aria-hidden="true" /></Tool>
      <Tool label={t`Quote`} onClick={() => apply((text, s, e) => prefixLines(text, s, e, "> "))}><Quote size={18} aria-hidden="true" /></Tool>
      <Tool label={t`Bulleted list`} onClick={() => apply((text, s, e) => prefixLines(text, s, e, "- "))}><List size={18} aria-hidden="true" /></Tool>
      <Tool label={t`Numbered list`} onClick={() => apply((text, s, e) => prefixLines(text, s, e, "1. "))}><ListOrdered size={18} aria-hidden="true" /></Tool>
      <Tool label={t`Link`} pressed={Boolean(linking)} onClick={openLink}><Link size={18} aria-hidden="true" /></Tool>
      <label className="ml-auto flex items-center gap-2 text-sm"><span className="sr-only">{t`Insert a placeholder`}</span>
        <select className="desk-input min-h-11" value="" onChange={event => { const key = event.target.value; if (key) apply((text, s, e) => insertAt(text, s, e, `{{ ${key} }}`)); }}>
          <option value="">{t`Insert placeholder…`}</option>
          {TEXT_PLACEHOLDERS.map(key => <option key={key} value={key}>{PLACEHOLDER_LABEL(key)}</option>)}
        </select></label>
    </div>
    {linking ? <div className="grid gap-3 rounded-xl border border-line bg-surface p-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end" role="group" aria-label={t`Add a link`}>
      <label className="grid gap-1 text-sm">{t`Link text`}<input className="desk-input" maxLength={80} value={label} onChange={event => setLabel(event.target.value)} /></label>
      <label className="grid gap-1 text-sm">{t`Goes to`}<span className="flex gap-2">
        <select className="desk-input" aria-label={t`Link destination`} value={target.startsWith("{{") ? target : ""}
          onChange={event => setTarget(event.target.value || "https://")}>
          <option value="">{t`A web address`}</option>
          {LINK_PLACEHOLDERS.map(key => <option key={key} value={`{{ ${key} }}`}>{PLACEHOLDER_LABEL(key)}</option>)}
        </select>
        {target.startsWith("{{") ? null : <input className="desk-input min-w-0 flex-1" aria-label={t`Web address`} inputMode="url" value={target}
          onChange={event => setTarget(event.target.value)} placeholder="https://" />}
      </span></label>
      <div className="flex gap-2">
        <button type="button" className="desk-button" onClick={() => setLinking(null)}>{t`Cancel`}</button>
        <button type="button" className="desk-button-primary" disabled={!valid} onClick={() => {
          const { start, end } = linking;
          const next = insertAt(value, start, end, linkMarkdown(label.trim(), target.trim()));
          onChange(next.text); setLinking(null);
          requestAnimationFrame(() => { field.current?.focus(); field.current?.setSelectionRange(next.start, next.end); });
        }}>{t`Add link`}</button>
      </div>
      {target.trim() && !linkTargetOk(target.trim()) && target !== "https://" ? <p role="alert" className="text-sm text-danger sm:col-span-3">{t`Use an https:// or mailto: address.`}</p> : null}
    </div> : null}
  </div>;
}
