import { useState } from "react";
import { CollapsibleSection, EmptyState, ErrorText, ListRow, Pagination, RelativeTime, Skeleton, StatusPill } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { ActionDialog } from "../platformSpaces/ActionDialog";
import { ChatTemplateForm } from "./ChatTemplateForm";
import { useChatTemplates, useDeleteChatTemplate, type ChatTemplate, type ChatTemplateSurface } from "./chatTemplatesApi";
import { PAGE_SIZE } from "./parityRequest";
import { SingleSpaceSelect, type PickedSpace } from "./SingleSpaceSelect";

type Scope = { spaceId: number; surface: ChatTemplateSurface };

function DeleteDialog({ spaceId, surface, row, onClose }: Scope & { row: ChatTemplate; onClose: () => void }) {
  const remove = useDeleteChatTemplate(spaceId, surface);
  return <ActionDialog title="Delete this template" confirmLabel="Delete template" tone="danger" pending={remove.isPending}
    error={remove.error} onCancel={onClose} message={`${row.feature} · ${row.event}: this event goes back to the built-in text.`}
    onSubmit={() => remove.mutate(row.id, { onSuccess: () => { toast("Template deleted."); onClose(); } })} />;
}

/** One space's templates: list, add, edit, delete. Shared by the superadmin console and a Space Manager's settings. */
export function ChatTemplateList({ space, surface = "platform" }: { space: PickedSpace; surface?: ChatTemplateSurface }) {
  const [page, setPage] = useState(1);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  const [deleting, setDeleting] = useState<ChatTemplate | null>(null);
  const list = useChatTemplates(space.id, page, surface);
  const rows = list.data?.results ?? [];
  return <div className="grid gap-3">
    <CollapsibleSection title="New template" open={adding} onToggle={() => setAdding(!adding)}><ChatTemplateForm spaceId={space.id} surface={surface} /></CollapsibleSection>
    {list.isLoading ? <Skeleton className="h-24 w-full" />
      : list.isError ? <ErrorText resource="chat templates" onRetry={() => { void list.refetch(); }} />
      : !rows.length ? <EmptyState message={`${space.name} uses the built-in text for every event.`} />
      : <div className="grid gap-3">{rows.map(row => <div key={row.id} className="grid gap-2">
        <ListRow title={`${row.feature} · ${row.event}`}
          meta={<>changed <RelativeTime date={row.updated_at} exact /> · {row.text_body.length > 120 ? `${row.text_body.slice(0, 120)}…` : row.text_body}</>}
          right={<div className="flex flex-wrap items-center gap-2">
            <StatusPill label={row.is_active ? "In use" : "Not in use"} tone={row.is_active ? "success" : "neutral"} />
            <button type="button" className="desk-button" aria-label={`Edit the ${row.event} template`} aria-expanded={editing === row.id}
              onClick={() => setEditing(editing === row.id ? null : row.id)}>Edit</button>
            <button type="button" className="desk-button-danger-outline" aria-label={`Delete the ${row.event} template`}
              onClick={() => setDeleting(row)}>Delete…</button>
          </div>} />
        {editing === row.id ? <div className="rounded-xl border border-line bg-panel">
          <ChatTemplateForm spaceId={space.id} surface={surface} row={row} onDone={() => setEditing(null)} />
        </div> : null}
      </div>)}</div>}
    <Pagination page={page} totalPages={Math.max(1, Math.ceil((list.data?.count ?? 0) / PAGE_SIZE))} onChange={setPage}
      count={list.data?.count} pageSize={PAGE_SIZE} disabled={list.isFetching} />
    {deleting ? <DeleteDialog spaceId={space.id} surface={surface} row={deleting} onClose={() => setDeleting(null)} /> : null}
  </div>;
}

/** Per-space chat message templates, one body per event, used by every chat channel. */
export function ChatTemplatesSection() {
  const [space, setSpace] = useState<PickedSpace | null>(null);
  return <div className="grid gap-4">
    <p className="text-sm text-muted">
      One message per event, shared by every chat channel (Telegram, Slack, Mattermost, Discord). Chat is a staff room, so never put
      member-facing details in it. Messages use Django template syntax.
    </p>
    <SingleSpaceSelect value={space} onChange={setSpace} />
    {space ? <ChatTemplateList key={space.id} space={space} /> : <EmptyState message="Choose a space to see its chat templates." />}
  </div>;
}
