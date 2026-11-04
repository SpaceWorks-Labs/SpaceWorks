import { SpaceWorksLogo } from "./SpaceWorksLogo";
import { Avatar } from "./ui/Avatar";

type MakerspaceBrandProps = {
  name: string;
  logoUrl?: string | null;
  /** Visual size of the mark. */
  size?: "sm" | "md" | "lg" | "xl";
  /** Hide the text name beside the logo (logo-only lockup). */
  hideName?: boolean;
  /** Without tenant artwork: the Space Works symbol (page headers) or initials (cards and lists). */
  fallback?: "logo" | "avatar";
  /** Let a long name wrap onto two lines (clamped) instead of truncating to one. */
  wrap?: boolean;
  className?: string;
};

const LOGO_SIZE: Record<NonNullable<MakerspaceBrandProps["size"]>, string> = {
  sm: "h-8 w-8",
  md: "h-10 w-10",
  lg: "h-14 w-14",
  xl: "h-16 w-16",
};

const NAME_SIZE: Record<NonNullable<MakerspaceBrandProps["size"]>, string> = {
  sm: "text-base",
  md: "text-xl",
  lg: "text-2xl",
  xl: "text-3xl sm:text-4xl",
};

/**
 * Renders a makerspace's brand: its uploaded logo when present, otherwise the
 * Space Works symbol (brand master, 48 px floor) in page headers, or initials in
 * cards and lists, beside the name. Names stay on one line (or two with `wrap`) so long tenant
 * identities cannot push public navigation out of alignment; the full name is always in `title`.
 */
export function MakerspaceBrand({
  name,
  logoUrl,
  size = "md",
  hideName = false,
  fallback = "avatar",
  wrap = false,
  className = "",
}: MakerspaceBrandProps) {
  return (
    <span className={`inline-flex min-w-0 max-w-full items-center gap-3 ${className}`}>
      {logoUrl ? (
        <img
          src={logoUrl}
          alt={`${name} logo`}
          className={`${LOGO_SIZE[size]} shrink-0 rounded-lg border border-line object-contain bg-panel`}
        />
      ) : fallback === "logo" ? <SpaceWorksLogo variant="symbol" size={48} decorative className="-m-3" />
        : <Avatar name={name} size={size === "sm" ? "sm" : size === "md" ? "md" : "lg"} />}
      {!hideName || !logoUrl ? (
        <span
          className={`min-w-0 ${wrap ? "line-clamp-2 break-words" : "truncate"} font-display font-semibold leading-tight text-ink ${NAME_SIZE[size]}`}
          title={name}
        >
          {name}
        </span>
      ) : null}
    </span>
  );
}
