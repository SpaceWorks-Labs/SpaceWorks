import { useId, useSyncExternalStore, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { currentTheme, subscribeTheme, type Theme } from "../lib/theme";
import { logoMasters } from "./spaceWorksLogoPaths";

export type SymbolSize = 48 | 52 | 64 | 72 | 96 | 128 | 192 | 256 | 512;
export type LockupSize = 180 | 240 | 288 | 320 | 480 | 600;
type SharedProps = {
  ground?: Theme;
  oneColour?: boolean;
  decorative?: boolean;
  /** Compatibility only: classes apply to the outside spacing wrapper, never SVG paths. */
  className?: string;
};
export type SpaceWorksLogoProps = SharedProps & (
  | { variant: "symbol"; size?: SymbolSize; withWordmark?: never }
  | { variant: "stacked" | "horizontal"; size?: LockupSize; withWordmark?: never }
  // Legacy callers used arbitrary symbol heights. Clamp these at the boundary.
  | { variant?: never; size?: number; withWordmark?: boolean }
);

export function SpaceWorksLogo({
  variant, ground, oneColour = false, decorative = false,
  size, withWordmark = false, className,
}: SpaceWorksLogoProps) {
  const theme = useSyncExternalStore(subscribeTheme, currentTheme, () => "light");
  const titleId = useId();
  const surface = ground ?? theme;
  const requested = variant ?? (withWordmark && (size ?? 0) >= 48 ? "stacked" : "symbol");
  // There is no reversed or one-colour horizontal master. Use the stacked drawing.
  const shape = requested === "horizontal" && (surface === "dark" || oneColour)
    ? "stacked" : requested;
  const master = shape === "symbol" ? "symbol" : `lockup-${shape}` as const;
  const key = surface === "dark" ? `${master}-reversed` as const
    : oneColour ? `${master}-one-colour-ink` as const : master;
  // Narrow the keys after resolving the horizontal fallback above.
  const artwork = logoMasters[key as keyof typeof logoMasters];
  const [, , viewWidth, viewHeight] = artwork.viewBox.split(" ").map(Number);
  const ratio = viewWidth / viewHeight;
  const floor = shape === "symbol" ? 48 : Math.max(180, 48 * ratio);
  const requestedSize = size !== undefined && Number.isFinite(size) ? size : floor;
  const dimension = Math.max(floor, requestedSize);
  const width = shape === "symbol" ? dimension * ratio : dimension;
  const height = shape === "symbol" ? dimension : dimension / ratio;

  return (
    <span className={className} style={{ display: "inline-flex", flexShrink: 0 }}>
      <span data-logo={key} style={{ display: "inline-flex", padding: height / 4, flexShrink: 0 }}>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox={artwork.viewBox}
          width={width}
          height={height}
          style={{ display: "block", width, height, minWidth: width, minHeight: height, maxWidth: "none" }}
          role={decorative ? undefined : "img"}
          aria-label={decorative ? undefined : "Space Works"}
          aria-labelledby={decorative ? undefined : titleId}
          aria-hidden={decorative || undefined}
          focusable="false"
        >
          {!decorative && <title id={titleId}>Space Works</title>}
          {artwork.paths.map((path, index) => <path key={index} {...path} />)}
        </svg>
      </span>
    </span>
  );
}

export function SpaceWorksHomeLink({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <Link
      aria-label="Open makerspace listing"
      className={[
        "inline-flex text-left transition hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
        className,
      ].filter(Boolean).join(" ")}
      to="/"
    >
      {children}
    </Link>
  );
}

export function SpaceWorksBadge({ className }: { className?: string }) {
  return (
    <SpaceWorksHomeLink className={className}>
      <SpaceWorksLogo variant="symbol" size={48} decorative />
    </SpaceWorksHomeLink>
  );
}

export default SpaceWorksLogo;
