import { Card, EmptyState } from "../../components/ui";
import { useState } from "react";

import {
  useEventCollaborators,
  useRemoveEventCollaborator,
  useReplaceEventCollaborators,
} from "./eventCollaborationsApi";
import { panelField, panelInput, panelRow } from "./eventPanelStyles";

const STATUS_LABEL: Record<string, string> = {
  invited: "Invited — waiting for them to accept",
  accepted: "Accepted — their members can register",
  declined: "Declined",
};

/** Host-side collaborator management for one event.
 *
 * Invitation is by SLUG, not a picker, and that is deliberate rather than lazy: a host has
 * no authority to enumerate other makerspaces, so offering a browsable list would leak the
 * existence and names of spaces it does not administer. The partner then has to accept
 * before any of its members become eligible, so one space cannot attach itself — or be
 * attached — to another's event unilaterally.
 */
export function EventCollaborators({ visible = true,
  makerspaceId,
  eventId,
}: { visible?: boolean;
  makerspaceId: number;
  eventId: number;
}) {
  const [slug, setSlug] = useState("");
  const collaborators = useEventCollaborators(eventId);
  const replace = useReplaceEventCollaborators(makerspaceId, eventId);
  const remove = useRemoveEventCollaborator(makerspaceId, eventId);
  const rows = collaborators.data ?? [];
  const error = replace.error || remove.error || collaborators.error;

  const invite = () => {
    const wanted = slug.trim().toLowerCase();
    if (!wanted) return;
    // The endpoint REPLACES the set, so send every slug that should remain plus the new
    // one; sending only the addition would silently remove every existing partner. Declined
    // rows are included so they are NOT deleted -- the service preserves their answer, so
    // adding one partner cannot reopen somebody else's refusal.
    const slugs = Array.from(
      new Set([...rows.map((row) => row.makerspace_slug), wanted]),
    );
    replace.mutate(slugs, { onSuccess: () => setSlug("") });
  };

  if (!visible) return null;
  return (
    <section aria-labelledby="collaborators-title" className="grid gap-4">
      <div>
        <h3 id="collaborators-title" className="title-section">Partner makerspaces</h3>
        <p className="mt-1 text-sm text-muted">
          Invite another makerspace by its slug and its members can register for this event,
          even when the event is not public. They must accept the invitation first. You invite
          by slug because makerspaces are not browsable from here.
        </p>
      </div>

      {rows.length ? (
        <ul className="grid gap-3">
          {rows.map((row) => (
            <li key={row.id} className={panelRow}>
              <div className="min-w-0">
                <p className="title-section break-words">
                  {row.makerspace_name}{" "}
                  <span className="text-sm font-normal text-muted">({row.makerspace_slug})</span>
                </p>
                <p className="mt-1 text-sm text-muted">{STATUS_LABEL[row.status] ?? row.status}</p>
              </div>
              <button
                type="button"
                className="desk-button-danger-outline"
                disabled={remove.isPending}
                onClick={() => remove.mutate(row.id)}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState message="No partner makerspaces yet." />
      )}

      <Card>
        <form className="flex flex-wrap items-end gap-3" onSubmit={(event) => { event.preventDefault(); invite(); }}>
          <label className={`${panelField} min-w-0 flex-1 basis-56`}>
            Makerspace slug
            <input
              className={panelInput}
              value={slug}
              onChange={(event) => setSlug(event.target.value)}
              placeholder="partner-space"
            />
          </label>
          <button
            type="submit"
            className="desk-button-primary"
            disabled={!slug.trim() || replace.isPending}
          >
            {replace.isPending ? "Inviting…" : "Invite"}
          </button>
        </form>
      </Card>

      {error ? (
        <p className="text-sm text-danger" role="alert">
          {error instanceof Error ? error.message : "Could not update partners."}
        </p>
      ) : null}
    </section>
  );
}
