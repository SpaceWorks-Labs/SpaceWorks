import { MapPin } from "lucide-react";

type MakerspaceLocation = {
  location?: string | null;
  map_url?: string | null;
};

type MakerspaceMapLinkProps = {
  makerspace?: MakerspaceLocation | null;
  className?: string;
  locationClassName?: string;
  linkClassName?: string;
};

// The default location line is capped and truncated (full text in `title`) so a long address
// cannot crowd the public header; cards pass their own wrapping class instead.
export function MakerspaceMapLink({
  makerspace,
  className = "",
  locationClassName = "min-w-0 max-w-[18rem] truncate text-sm text-muted",
  linkClassName = "inline-flex min-h-11 items-center gap-1 rounded-control text-xs font-semibold text-brand-ink hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
}: MakerspaceMapLinkProps) {
  const location = makerspace?.location?.trim() ?? "";
  const mapUrl = makerspace?.map_url?.trim() ?? "";

  if (!location && !mapUrl) {
    return null;
  }

  return (
    <div className={`flex min-w-0 flex-wrap items-center gap-x-2 gap-y-0.5 ${className}`}>
      {location ? <span className={locationClassName} title={location}>{location}</span> : null}
      {mapUrl ? (
        <a
          className={linkClassName}
          href={mapUrl}
          target="_blank"
          rel="noopener noreferrer"
        >
          <MapPin aria-hidden="true" size={16} className="shrink-0" />
          Open in Google Maps
        </a>
      ) : null}
    </div>
  );
}
