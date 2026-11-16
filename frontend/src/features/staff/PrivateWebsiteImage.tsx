import { LogoLoader } from "../../components/LogoLoader";
import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { staffRequestBlob } from "../../lib/api";

export function PrivateWebsiteImage({ url, alt }: { url: string; alt: string }) {
  const query = useQuery({ queryKey: ["website-private-image", url], gcTime: 0, staleTime: 0,
    queryFn: () => staffRequestBlob(url.replace(/^\/api\/v1/, "")),
  });
  const [src, setSrc] = useState("");
  useEffect(() => {
    if (!query.data) return;
    const objectUrl = URL.createObjectURL(query.data);
    setSrc(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [query.data]);
  if (query.isLoading) return <LogoLoader label={t`Loading image…`} size={48} className="min-h-16 py-3" />;
  if (query.error) return <p role="alert">{t`Unable to preview ${alt}.`}</p>;
  return src ? <img className="my-3 max-h-64 max-w-full rounded-lg object-contain" src={src} alt={alt} /> : null;
}
