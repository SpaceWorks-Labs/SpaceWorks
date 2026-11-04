import { PageImage } from "../publicPages/PageImage";

/** Card URLs use the owner's canonical host; credentials go only to our configured API. */
export function DiscoveryEventImage({ url, alt }: { url: string; alt: string }) {
  const path = new URL(url, window.location.origin).pathname;
  const asset = /^\/api\/v1\/public\/([a-z0-9_-]+)\/events\/[0-9a-f-]+\/website\/assets\/\d+\/$/i.exec(path);
  return <div className="w-13 shrink-0 [&_img]:h-13 [&_img]:rounded-md [&_img]:object-cover">
    <PageImage url={asset ? path : url} slug={asset?.[1]} alt={alt} token={url} />
  </div>;
}
