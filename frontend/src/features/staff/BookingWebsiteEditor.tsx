import { useState } from "react";
import { API_URL } from "../../lib/api";
import { ErrorText, Field, SettingsSection, Skeleton, StatusPill } from "../../components/ui";
import type { BookingWebsite } from "../bookings/bookingWebsiteTypes";
import { useBookingWebsite, useBookingWebsiteMutation } from "../bookings/bookingWebsiteApi";
import { BookingWebsiteSectionCard } from "./BookingWebsiteSectionCard";
import type { BookableSpace } from "./bookingsApi";

export function BookingWebsiteEditor({ space }: { space: BookableSpace }) {
  const query = useBookingWebsite(space.makerspace_id, space.id);
  if (query.isLoading) return <div role="status" aria-label="Loading website…" className="grid gap-3"><span className="sr-only">Loading website…</span><Skeleton className="h-24 w-full" /><Skeleton className="h-48 w-full" /></div>;
  return <>
    {query.error ? <div role="alert" className="flex flex-wrap items-center gap-3 rounded-control border border-danger-line bg-panel px-3 py-2 text-sm text-danger">
      <p>{query.error.message}</p><button className="desk-button ml-auto" type="button" onClick={() => query.refetch()}>Retry website</button></div> : null}
    {query.data ? <WebsiteForm key={`${space.makerspace_id}:${space.id}`} space={space} saved={query.data} onReload={async () => {
      const result = await query.refetch();
      return result.isSuccess ? result.data : undefined;
    }} /> : null}
  </>;
}

function WebsiteForm({ space, saved, onReload }: { space: BookableSpace; saved: BookingWebsite; onReload: () => Promise<BookingWebsite | undefined> }) {
  const [page, setPage] = useState(saved);
  // Refetches update server state; the draft keeps the snapshot it was based on.
  const [baseline, setBaseline] = useState(saved);
  const [reloading, setReloading] = useState(false);
  const [preview, setPreview] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [alt, setAlt] = useState("");
  const [replace, setReplace] = useState("");
  const mutation = useBookingWebsiteMutation(space.makerspace_id, space.id);
  const manager = Boolean(space.can_manage_grants);
  const edit = manager || space.staff_permissions?.includes("edit_details");
  const publish = manager || space.staff_permissions?.includes("publish_page");
  const dirty = JSON.stringify(page.sections) !== JSON.stringify(baseline.sections);
  const reload = async () => {
    setReloading(true);
    try {
      const latest = await onReload();
      if (latest) { setPage(latest); setBaseline(latest); }
    } finally { setReloading(false); }
  };
  const mutate = (input: Parameters<typeof mutation.mutate>[0]) => mutation.mutate(input, { onSuccess: reload });
  const embedUrl = saved.embed_path ? new URL(saved.embed_path, new URL(API_URL || "/", window.location.origin)).href : "";
  const update = (index: number, values: Partial<BookingWebsite["sections"][number]>) => setPage({ ...page,
    sections: page.sections.map((row, n) => n === index ? { ...row, ...values } : row),
  });
  return <section className="grid min-w-0 gap-6" aria-label="Resource website editor">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0 flex-1 basis-64"><div className="flex flex-wrap items-center gap-2"><h2 className="title-panel">Resource website</h2>
        <StatusPill label={saved.released ? "Released" : "Unreleased"} tone={saved.released ? "success" : "neutral"} /></div>
        <p className="mt-1 text-sm text-muted">{saved.released ? "Website released" : "Website unreleased"}. Only published sections appear after release. Rules are still enforced by the booking service.</p></div>
      <div className="flex flex-wrap gap-2">
        <button className="desk-button" type="button" onClick={() => setPreview(!preview)}>{preview ? "Edit sections" : "Private preview"}</button>
        <button className="desk-button" type="button" disabled={mutation.isPending || reloading} onClick={() => { void reload(); }}>Reload website (discard draft)</button>
      </div>
    </div>
    {mutation.error ? <ErrorText message={mutation.error.message} /> : null}
    {mutation.isSuccess ? <p role="status" className="text-sm text-success-ink">Website updated.</p> : null}
    {saved.revision !== page.revision ? <p role="status" className="text-sm text-warn-ink">The website has changed. Your draft is preserved. Reload to discard it and load the latest website.</p> : null}
    <fieldset disabled={mutation.isPending || reloading} className="grid min-w-0 gap-6">
      <legend className="sr-only">Website sections</legend>
      <div className="grid gap-4">{page.sections.map((section, index) => <BookingWebsiteSectionCard key={index} section={section} assets={page.assets}
        spaceId={space.id} preview={preview} edit={Boolean(edit)} onChange={(values) => update(index, values)}
        onRemove={() => setPage({ ...page, sections: page.sections.filter((_, n) => n !== index) })} />)}</div>
      {edit || publish ? <div className="flex flex-wrap items-center justify-end gap-2 border-t border-line pt-4">
        {dirty ? <p role="status" className="mr-auto text-sm text-muted">Save content before releasing or changing images.</p> : null}
        {edit ? <button className="desk-button" type="button" disabled={page.sections.length >= 100} onClick={() => setPage({ ...page, sections: [...page.sections, {
          kind: "rules", slug: `section-${page.sections.length + 1}`, title: "New section", body: "", url: "", visibility: "draft", position: page.sections.length, asset_id: null,
        }] })}>Add section</button> : null}
        {publish ? <button className="desk-button" type="button" disabled={!page.revision || dirty || (!page.released && (!space.is_public || !space.is_active))} onClick={() => mutate({ revision: page.revision, released: !page.released })}>{page.released ? "Unrelease website" : "Release website"}</button> : null}
        {edit ? <button className="desk-button-primary" type="button" onClick={() => mutate({ page })}>Save content</button> : null}
      </div> : null}
      {edit ? <SettingsSection title="Private gallery">
        <div className="grid gap-4 py-5 sm:grid-cols-2">
          <Field label="Image (JPEG, PNG or WebP, up to 5 MB)" className="sm:col-span-2"><input className="desk-input w-full" type="file" accept="image/jpeg,image/png,image/webp" disabled={dirty} onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></Field>
          <Field label="Image description"><input className="desk-input w-full" value={alt} maxLength={200} onChange={(e) => setAlt(e.target.value)} /></Field>
          <Field label="Replace image"><select className="desk-input w-full" value={replace} onChange={(e) => setReplace(e.target.value)}><option value="">New image</option>{page.assets?.map((asset) => <option key={asset.id} value={asset.id}>{asset.alt_text}</option>)}</select></Field>
          <button className="desk-button w-fit" type="button" disabled={dirty || !file || !alt.trim()} onClick={() => {
            const asset = new FormData(); asset.set("file", file!); asset.set("alt_text", alt); if (replace) asset.set("replace_id", replace);
            mutate({ asset });
          }}>Upload private image</button>
        </div>
        {page.assets?.length ? <ul className="divide-y divide-line">{page.assets.map((asset) => <li key={asset.id} className="flex min-w-0 flex-wrap items-center justify-between gap-3 py-3">
          <span className="min-w-0 break-words text-sm">{asset.alt_text} <span className="text-muted">({asset.size_bytes} bytes)</span></span>
          <button className="desk-button-danger-outline" type="button" disabled={dirty} onClick={() => mutate({ remove: asset.id })}>Delete {asset.alt_text}</button></li>)}</ul> : null}
      </SettingsSection> : null}
    </fieldset>
    {saved.public_url || (space.embed_enabled && embedUrl) ? <SettingsSection title="Sharing">
      {saved.public_url ? <div className="py-4"><a className="inline-flex min-h-11 items-center text-accent-ink underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus" href={saved.public_url} target="_blank" rel="noopener noreferrer">Open public resource page</a></div> : null}
      {space.embed_enabled && embedUrl ? <div className="py-4"><Field label="Embed card" hint="Release the website first. A makerspace manager must allow your website's exact HTTPS origin in website settings.">
        <textarea className="desk-input w-full font-mono text-xs" readOnly rows={3} value={`<iframe src="${embedUrl}" title="Resource booking" loading="lazy"></iframe>`} /></Field></div> : null}
    </SettingsSection> : null}
  </section>;
}
