/** The optional "When will you collect?" window (`loans.reservations`). Values are datetime-local strings. */
export type PickupWindow = { from: string; until: string };

export function pickupWindowProblem(window: PickupWindow, now = Date.now()) {
  const from = window.from ? new Date(window.from).getTime() : null;
  const until = window.until ? new Date(window.until).getTime() : null;
  if (from !== null && from < now - 5 * 60_000) return "Pick a collection time that hasn't passed.";
  if (until !== null && until <= (from ?? now)) return "The window must end after it starts.";
  return "";
}

/** ISO datetimes for the request body; empty fields are left out so the server applies its own default. */
export function pickupWindowPayload(window: PickupWindow) {
  return {
    ...(window.from ? { pickup_from: new Date(window.from).toISOString() } : {}),
    ...(window.until ? { pickup_until: new Date(window.until).toISOString() } : {}),
  };
}

export function PickupWindowFields({ value, onChange }: { value: PickupWindow; onChange: (next: PickupWindow) => void }) {
  const problem = pickupWindowProblem(value);
  return <fieldset className="grid gap-2">
    <legend className="mb-1 text-sm font-semibold text-ink">When will you collect? (optional)</legend>
    <div className="grid gap-2 sm:grid-cols-2">
      <label className="block text-sm text-muted">From
        <input className="desk-input mt-1 w-full" type="datetime-local" value={value.from} onChange={event => onChange({ ...value, from: event.target.value })} />
      </label>
      <label className="block text-sm text-muted">Until
        <input className="desk-input mt-1 w-full" type="datetime-local" value={value.until} onChange={event => onChange({ ...value, until: event.target.value })} />
      </label>
    </div>
    {problem ? <p role="alert" className="text-sm text-danger">{problem}</p>
      : <p className="text-sm text-muted">Staff hold the items for you from when they accept. An uncollected request may expire.</p>}
  </fieldset>;
}
