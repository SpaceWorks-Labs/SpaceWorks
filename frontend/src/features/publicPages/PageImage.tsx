import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { API_V1_URL, staffRequestBlob, tenantPublicRequestBlob } from "../../lib/api";
import { publicHeaders } from "../../lib/api/client";
import { apiError } from "../../lib/api/errors";
import { hostScope, pageApiPath, publicPagePolicy } from "./pageApi";
import { currentSessionContext } from "../../lib/api/sessionContext";
import { personalRecipientKey } from "../notifications/personalQueryKeys";

function legacyArtwork(value: string) {
  try {
    const url = new URL(value, window.location.origin);
    return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password
      && !["/api/", "/public/", "/admin/"].some(prefix => url.pathname.startsWith(prefix));
  } catch { return false; }
}

export function PageImage({ url, alt, slug, token, privatePreview = false }: {
  url: string; alt: string; slug?: string; token: string; privatePreview?: boolean;
}) {
  const artwork = legacyArtwork(url);
  const query = useQuery({ queryKey: ["page-image", hostScope(), privatePreview ? [currentSessionContext(), personalRecipientKey()] : "public", slug, token, url], ...publicPagePolicy, enabled: !artwork,
    retry: false, queryFn: async () => {
      if (privatePreview) {
        const base = new URL(API_V1_URL, window.location.origin); const address = new URL(url, base.origin);
        const prefix = base.pathname.replace(/\/$/, "");
        const path = address.pathname.startsWith(`${prefix}/`) ? address.pathname.slice(prefix.length) : address.pathname;
        if (address.origin !== base.origin || address.username || address.password || !path.startsWith("/admin/")) throw new Error("Unsupported preview address");
        return staffRequestBlob(path, { cache: "no-store" });
      }
      const path = pageApiPath(url);
      if (slug) return tenantPublicRequestBlob(slug, path);
      const response = await fetch(`${API_V1_URL}${path}`, { headers: await publicHeaders(), cache: "no-store" });
      if (!response.ok) throw apiError(response.status, await response.json().catch(() => ({})));
      return response.blob();
    },
  });
  const [src, setSrc] = useState<{ blob: Blob; url: string } | null>(null);
  useEffect(() => {
    if (!query.data || query.error) return;
    const value = URL.createObjectURL(query.data); setSrc({ blob: query.data, url: value });
    return () => URL.revokeObjectURL(value);
  }, [query.data, query.error]);
  if (artwork) return <img src={url} alt={alt} className="max-h-96 w-full rounded-xl object-contain" />;
  if (query.error) return <p className="text-sm text-muted">Image unavailable: {alt}</p>;
  return src && src.blob === query.data ? <img src={src.url} alt={alt} className="max-h-96 w-full rounded-xl object-contain" /> : <p role="status" className="text-sm text-muted">Loading image…</p>;
}
