/**
 * Shared presign upload for gallery photos. The server answers a presign with an upload
 * target (`{ object_key, upload: { url, method, fields, headers } }`) -- a staging key for
 * PUT, a size- and type-bound POST policy otherwise; the browser sends the bytes straight
 * to object storage, then the caller asks the API to finalize (size + image sniff) and
 * attach the object. Nothing is shown publicly until that attach succeeds.
 */
export type GalleryPresign = {
  object_key: string;
  upload: { url: string; method?: string; fields?: Record<string, string>; headers?: Record<string, string> };
};

export const GALLERY_ACCEPT = "image/jpeg,image/png,image/webp";

export async function sendToStorage(presigned: GalleryPresign, file: File, transport: typeof fetch = fetch) {
  const { upload } = presigned;
  let response: Response;
  if (upload.method === "PUT") {
    response = await transport(upload.url, { method: "PUT", body: file, headers: upload.headers });
  } else {
    const form = new FormData();
    Object.entries(upload.fields ?? {}).forEach(([key, value]) => form.append(key, value));
    form.append("file", file);
    response = await transport(upload.url, { method: "POST", body: form });
  }
  if (!response.ok) throw new Error(`Photo upload failed (${response.status}). Try again.`);
}

/** presign -> storage -> attach, as one awaited step so the UI shows a single pending state. */
export async function uploadGalleryPhoto(file: File, steps: {
  presign: (input: { filename: string; content_type: string }) => Promise<GalleryPresign>;
  attach: (objectKey: string) => Promise<unknown>;
  transport?: typeof fetch;
}) {
  if (!GALLERY_ACCEPT.split(",").includes(file.type)) {
    throw new Error("Use a JPEG, PNG or WebP photo.");
  }
  const presigned = await steps.presign({ filename: file.name, content_type: file.type });
  await sendToStorage(presigned, file, steps.transport);
  return steps.attach(presigned.object_key);
}
