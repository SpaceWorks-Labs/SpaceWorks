// Import source picker shared by the member import and the ID-programme import (L13):
// upload a file, or paste the link of a Google Sheet shared as "anyone with the link".
// The server fetches the sheet's CSV export and runs the same preview as for a file.
import { useId, useState } from "react";
import { Link, Sheet } from "lucide-react";

import { SegmentedControl } from "../../../components/ui";

export type ImportSource = "file" | "google_sheet";

const SHEET_LINK = /^https:\/\/docs\.google\.com\/spreadsheets\/(?:u\/\d{1,2}\/)?d\/(?:e\/)?[A-Za-z0-9_-]{20,200}(?:[/?#]\S*)?$/i;

/** "" when the link looks like a Google Sheet; otherwise what to fix. The server checks it again. */
export function sheetLinkProblem(url: string) {
  const value = url.trim();
  if (!value) return "Paste the sheet's link.";
  return SHEET_LINK.test(value) ? "" : "Use a Google Sheets link that starts with https://docs.google.com/spreadsheets/.";
}

export function SourcePicker({ value, onChange }: { value: ImportSource; onChange: (value: ImportSource) => void }) {
  return <SegmentedControl label="Import from" value={value} onChange={(next) => onChange(next as ImportSource)}
    options={[{ value: "file", label: "Upload a file" }, { value: "google_sheet", label: "Google Sheets link" }]} />;
}

export function SheetLinkField({ url, onUrl }: { url: string; onUrl: (url: string) => void }) {
  const id = useId();
  const [touched, setTouched] = useState(false);
  const problem = sheetLinkProblem(url);
  const showProblem = touched && Boolean(problem);
  return <div className="grid gap-3">
    <div className="flex items-start gap-3 rounded-control border border-line bg-surface p-3 text-sm text-muted">
      <Sheet aria-hidden className="mt-0.5 h-5 w-5 shrink-0 text-ink" />
      <p>In Google Sheets choose <strong className="text-ink">Share</strong> and set General access to
        {" "}<strong className="text-ink">Anyone with the link · Viewer</strong>. SpaceWorks reads the first tab (or the tab in the
        link) straight from Google when you preview and again when you import, and keeps no copy. Private sheets cannot be read.</p>
    </div>
    <div className="grid gap-2">
      <label htmlFor={`${id}-input`} className="text-sm font-semibold text-ink">Sheet link</label>
      <span className="relative">
        <Link aria-hidden className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <input id={`${id}-input`} className="desk-input min-h-11 w-full pl-9" type="url" inputMode="url" autoComplete="off"
          spellCheck={false} placeholder="https://docs.google.com/spreadsheets/d/…" value={url} aria-invalid={showProblem}
          aria-describedby={`${id}-${showProblem ? "error" : "hint"}`}
          onBlur={() => setTouched(true)} onChange={(event) => onUrl(event.target.value)} />
      </span>
      {showProblem ? <span id={`${id}-error`} className="text-xs text-danger">{problem}</span>
        : <span id={`${id}-hint`} className="text-xs text-muted">The first row holds the column names, as in a file.</span>}
    </div>
  </div>;
}
