import { PageImage } from "../features/publicPages/PageImage";

/** Public artwork stays on storage; private website assets use the gated tenant API. */
export function PublicWebsiteImage({ makerspaceSlug, url, alt }: { makerspaceSlug: string; url: string; alt: string }) {
  return <PageImage slug={makerspaceSlug} url={url} alt={alt} token={url} />;
}
