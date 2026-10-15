import { useState } from "react";
import { API_URL } from "../../lib/api";
import { RestrictedMarkdown } from "../../components/RestrictedMarkdown";
import { sectionKinds, type BookingWebsite } from "../bookings/bookingWebsiteTypes";
import { useBookingWebsite, useBookingWebsiteMutation } from "../bookings/bookingWebsiteApi";
import { PrivateWebsiteImage } from "./PrivateWebsiteImage";
import type { BookableSpace } from "./bookingsApi";

export function BookingWebsiteEditor({ space }: { space: BookableSpace }) {
  const query = useBookingWebsite(space.makerspace_id, space.id);
  if (query.isLoading) return <p role="status">Loading website…</p>;
  if (query.error) return <div role="alert"><p>{query.error.message}</p><button className="desk-button" onClick={() => query.refetch()}>Reload website</button></div>;
  return query.data ? <WebsiteForm key={query.data.revision} space={space} saved={query.data} /> : null;
}

function WebsiteForm({ space, saved }: { space: BookableSpace; saved: BookingWebsite }) {
  const [page, setPage] = useState(saved);
  const [preview, setPreview] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [alt, setAlt] = useState("");
  const [replace, setReplace] = useState("");
  const mutation = useBookingWebsiteMutation(space.makerspace_id, space.id);
  const manager = Boolean(space.can_manage_grants);
  const edit = manager || space.staff_permissions?.includes("edit_details");
  const publish = manager || space.staff_permissions?.includes("publish_page");
  const dirty = JSON.stringify(page.sections) !== JSON.stringify(saved.sections);
  const embedUrl = saved.embed_path ? new URL(saved.embed_path, new URL(API_URL || "/", window.location.origin)).href : "";
  const update = (index: number, values: Partial<BookingWebsite["sections"][number]>) => setPage({ ...page,
    sections: page.sections.map((row, n) => n === index ? { ...row, ...values } : row),
  });
  return <section className="grid gap-4" aria-label="Resource website editor">
    <h3 className="title-section">Resource website</h3>
    <p className="text-sm text-muted">{saved.released ? "Website released" : "Website unreleased"}. Only published sections appear after release. Rules are still enforced by the booking service.</p>
    {mutation.error ? <p role="alert" className="text-danger">{mutation.error.message}</p> : null}
    {mutation.isSuccess ? <p role="status">Website updated.</p> : null}
    <button className="desk-button w-fit" type="button" onClick={() => setPreview(!preview)}>{preview ? "Edit sections" : "Private preview"}</button>
    <fieldset disabled={mutation.isPending} className="grid gap-4">
      {page.sections.map((section, index) => <article className="desk-panel grid gap-3 p-4" key={index}>
        {preview ? <><h4 className="title-section">{section.title} ({section.visibility})</h4><RestrictedMarkdown text={section.body} />
          {edit && section.asset_id ? <PrivateWebsiteImage url={`/api/v1/admin/spaces/${space.id}/website/assets/${section.asset_id}/`} alt={page.assets?.find((asset) => asset.id === section.asset_id)?.alt_text || section.title} /> : null}</> : <>
          <label>Section kind<select className="desk-input" disabled={!edit} value={section.kind} onChange={(e) => update(index, { kind: e.target.value as typeof section.kind })}>{sectionKinds.map((kind) => <option key={kind}>{kind}</option>)}</select></label>
          <label>Section slug<input className="desk-input" disabled={!edit} maxLength={80} value={section.slug} onChange={(e) => update(index, { slug: e.target.value })} /></label>
          <label>Section title<input className="desk-input" disabled={!edit} maxLength={200} value={section.title} onChange={(e) => update(index, { title: e.target.value })} /></label>
          <label>Text (restricted Markdown)<textarea className="desk-input" disabled={!edit} rows={4} maxLength={10000} value={section.body} onChange={(e) => update(index, { body: e.target.value })} /></label>
          <label>HTTP(S) link<input className="desk-input" disabled={!edit} type="url" maxLength={500} value={section.url} onChange={(e) => update(index, { url: e.target.value })} /></label>
          <label>Gallery image<select className="desk-input" disabled={!edit} value={section.asset_id ?? ""} onChange={(e) => update(index, { asset_id: Number(e.target.value) || null })}><option value="">None</option>{page.assets?.map((asset) => <option value={asset.id} key={asset.id}>{asset.alt_text}</option>)}</select></label>
          <label>Section visibility<select className="desk-input" disabled={!edit} value={section.visibility} onChange={(e) => update(index, { visibility: e.target.value as typeof section.visibility })}><option value="draft">Draft</option><option value="published">Published</option></select></label>
          <label>Position<input type="number" min={0} max={1000} className="desk-input" disabled={!edit} value={section.position} onChange={(e) => update(index, { position: Number(e.target.value) })} /></label>
          {edit ? <button className="desk-button-danger w-fit" onClick={() => setPage({ ...page, sections: page.sections.filter((_, n) => n !== index) })}>Remove section</button> : null}
        </>}
      </article>)}
      {edit ? <div className="flex flex-wrap gap-3"><button className="desk-button" disabled={page.sections.length >= 100} onClick={() => setPage({ ...page, sections: [...page.sections, {
        kind: "rules", slug: `section-${page.sections.length + 1}`, title: "New section", body: "", url: "", visibility: "draft", position: page.sections.length, asset_id: null,
      }] })}>Add section</button><button className="desk-button-primary" onClick={() => mutation.mutate({ page })}>Save content</button></div> : null}
      {publish ? <button className="desk-button-secondary w-fit" disabled={!saved.revision || dirty || (!saved.released && (!space.is_public || !space.is_active))} onClick={() => mutation.mutate({ revision: saved.revision, released: !saved.released })}>{saved.released ? "Unrelease website" : "Release website"}</button> : null}
      {dirty ? <p role="status">Save content before releasing or changing images.</p> : null}
      {edit ? <div className="grid gap-3 border-t border-line pt-4"><h4 className="title-section">Private gallery</h4>
        <label>Image (JPEG, PNG or WebP, up to 5 MB)<input className="desk-input" type="file" accept="image/jpeg,image/png,image/webp" disabled={dirty} onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></label>
        <label>Image description<input className="desk-input" value={alt} maxLength={200} onChange={(e) => setAlt(e.target.value)} /></label>
        <label>Replace image<select className="desk-input" value={replace} onChange={(e) => setReplace(e.target.value)}><option value="">New image</option>{page.assets?.map((asset) => <option key={asset.id} value={asset.id}>{asset.alt_text}</option>)}</select></label>
        <button className="desk-button w-fit" disabled={dirty || !file || !alt.trim()} onClick={() => {
          const asset = new FormData(); asset.set("file", file!); asset.set("alt_text", alt); if (replace) asset.set("replace_id", replace);
          mutation.mutate({ asset });
        }}>Upload private image</button>
        {page.assets?.map((asset) => <div key={asset.id} className="flex items-center gap-3"><span>{asset.alt_text} ({asset.size_bytes} bytes)</span><button className="desk-button-danger" disabled={dirty} onClick={() => mutation.mutate({ remove: asset.id })}>Delete {asset.alt_text}</button></div>)}
      </div> : null}
    </fieldset>
    {saved.public_url ? <a className="underline" href={saved.public_url} target="_blank" rel="noopener noreferrer">Open public resource page</a> : null}
    {space.embed_enabled && embedUrl ? <label>Embed card<textarea className="desk-input" readOnly rows={3} value={`<iframe src="${embedUrl}" title="Resource booking" loading="lazy"></iframe>`} /><span className="text-sm text-muted">Release the website first. A makerspace manager must allow your website's exact HTTPS origin in website settings.</span></label> : null}
  </section>;
}
