import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { staffRequest } from "../../lib/api";
import { HANDLE_PATTERN } from "../profile/publicProfileApi";
import { editorBase, type PageOperation } from "./pageApi";
import { pageInput, pageLabel } from "./documentDefaults";
import type { EditorState, PageOwner } from "./pageTypes";

export function PageHandleForm({ state, owner, disabled, run }: { state: EditorState; owner: PageOwner; disabled: boolean; run: (input: PageOperation) => void }) {
  const [handle, setHandle] = useState(state.handle ?? "");
  const availability = useMutation({ mutationFn: (name: string) => staffRequest<import("../../generated/api").HandleAvailability>(`${editorBase(owner)}handle-availability/?handle=${encodeURIComponent(name)}`, { cache: "no-store" }) });
  return <section className="grid gap-3" aria-label="Public handle">
    <h3 className="title-section">Public handle</h3>
    <p className="text-sm text-muted">Current handle: {state.handle ? `/${state.handle}` : "Not claimed"}. Changes and retired-name reservations last 30 days. Releasing the handle also unpublishes the page.</p>
    <form className="grid gap-3" onSubmit={e => { e.preventDefault(); if (!disabled) run({ action: "handle", version: state.version, handle: handle.toLowerCase() }); }}>
      <label className={pageLabel}>Handle<input className={pageInput} required minLength={3} maxLength={30} pattern={HANDLE_PATTERN.source} disabled={disabled} value={handle} onChange={e => { setHandle(e.target.value.toLowerCase()); availability.reset(); }} autoCapitalize="none" autoCorrect="off" spellCheck={false} /></label>
      <div className="flex flex-wrap gap-2"><button className="desk-button" type="button" disabled={disabled || availability.isPending || !HANDLE_PATTERN.test(handle)} onClick={() => availability.mutate(handle)}>Check availability</button>
        <button className="desk-button" type="submit" disabled={disabled || !HANDLE_PATTERN.test(handle) || handle === state.handle}>{state.handle ? "Rename handle" : "Claim handle"}</button>
        {state.handle ? <button className="desk-button-danger-outline" type="button" disabled={disabled} onClick={() => run({ action: "release_handle", version: state.version })}>Release handle and unpublish</button> : null}
      </div>
    </form>
    {availability.data ? <p role="status" className="text-sm">/{availability.data.handle} is {availability.data.available ? "available. Claiming checks availability again." : "unavailable."}</p> : null}
    {availability.error ? <p role="alert" className="text-sm text-danger">{availability.error.message}</p> : null}
  </section>;
}
