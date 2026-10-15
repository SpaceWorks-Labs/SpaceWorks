import { useEffect, useState } from "react";
import type { WebsiteTarget } from "../events/websiteTypes";
import { useEventWebsite } from "./eventWebsiteApi";

export function EventWebsitePublication({ target, onChange }: {
  target: WebsiteTarget;
  onChange: (value: { publish_website: boolean; website_revision?: number } | undefined) => void;
}) {
  const query = useEventWebsite(target);
  const [checked, setChecked] = useState(false);
  const available = Boolean(query.data?.revision && !query.data.inherited && !query.error);
  useEffect(() => {
    if (!available) setChecked(false);
    onChange(checked && available ? { publish_website: true, website_revision: query.data?.revision } : undefined);
  }, [checked, available, query.data?.revision, onChange]);
  return <label className="flex gap-2"><input type="checkbox" checked={checked && available} disabled={!available} onChange={(e) => setChecked(e.target.checked)} />Publish website with event</label>;
}
