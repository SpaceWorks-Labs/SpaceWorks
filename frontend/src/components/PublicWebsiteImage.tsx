import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { tenantPublicRequestBlob } from "../lib/api";

/** The tenant transport supplies browser credentials and the configured API origin. */
export function PublicWebsiteImage({ makerspaceSlug, url, alt }: { makerspaceSlug: string; url: string; alt: string }) {
  const query = useQuery({ queryKey: ["public-website-image", makerspaceSlug, url], staleTime: 0, gcTime: 0,
    queryFn: () => tenantPublicRequestBlob(makerspaceSlug, url.replace(/^\/api\/v1/, "")), retry: false,
  });
  const [src, setSrc] = useState("");
  useEffect(() => {
    if (!query.data) return;
    const objectUrl = URL.createObjectURL(query.data);
    setSrc(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [query.data]);
  if (query.error) return <p className="text-sm text-muted">Image unavailable: {alt}</p>;
  if (!src) return <p role="status" className="text-sm text-muted">Loading {alt}…</p>;
  return <img className="my-3 max-h-64 max-w-full rounded-lg object-contain" src={src} alt={alt} />;
}
