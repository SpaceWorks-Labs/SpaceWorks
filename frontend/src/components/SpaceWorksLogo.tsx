import { t } from "@lingui/core/macro";
import { useId, useSyncExternalStore, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { currentTheme, subscribeTheme, type Theme } from "../lib/theme";
import { LogoBoxOverlay } from "./brand/LogoBoxOverlay";
import { logoMasters } from "./spaceWorksLogoPaths";

export type SymbolSize = 48 | 52 | 64 | 72 | 96 | 128 | 192 | 256 | 512;
export type LockupSize = 180 | 240 | 288 | 320 | 480 | 600;
type SharedProps = {
  ground?: Theme;
  oneColour?: boolean;
  decorative?: boolean;
  /** Internal: set only by `AnimatedLogoMark`, which every product placement must use. Adds the hover/focus opening. */
  animated?: boolean;
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
  variant, ground, oneColour = false, decorative = false, animated = false,
  size, withWordmark = false, className,
}: SpaceWorksLogoProps) {
  const theme = useSyncExternalStore(subscribeTheme, currentTheme, () => "light");
  const titleId = useId();
  const surface = ground ?? theme;
  const requested = variant ?? (withWordmark && (size ?? 0) >= 48 ? "stacked" : "symbol");
  const shape = requested;
  const master = shape === "symbol" ? "symbol" : `lockup-${shape}` as const;
  const key = surface === "dark" ? `${master}-reversed` as const
    : oneColour ? `${master}-one-colour-ink` as const : master;
  const artwork: { viewBox: string; paths: readonly { fill: string; d: string }[]; clip?: { width: number; height: number; count: number } } = logoMasters[key];
  const [, , viewWidth, viewHeight] = artwork.viewBox.split(" ").map(Number);
  const ratio = viewWidth / viewHeight;
  const floor = shape === "symbol" ? 48 : Math.max(180, 48 * ratio);
  const requestedSize = size !== undefined && Number.isFinite(size) ? size : floor;
  const dimension = Math.max(floor, requestedSize);
  const width = shape === "symbol" ? dimension * ratio : dimension;
  const height = shape === "symbol" ? dimension : dimension / ratio;
  // The symbol's last four paths are its flaps (top-left, top-right, bottom-left, bottom-right) in
  // every master; lockups end with the wordmark. Classes only: delight's logo unfold moves them on
  // hover and click, and with no delight they render exactly as the master.
  const symbolPaths = artwork.clip?.count ?? (shape === "symbol" ? artwork.paths.length : artwork.paths.length - 1);

  return (
    <span className={className} style={{ display: "inline-flex", flexShrink: 0 }}>
      <span data-logo={key} style={{ display: "inline-flex", position: "relative", padding: height / 4, flexShrink: 0 }}>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox={artwork.viewBox}
          width={width}
          height={height}
          style={{ display: "block", width, height, minWidth: width, minHeight: height, maxWidth: "none" }}
          role={decorative ? undefined : "img"}
          aria-label={decorative ? undefined : t`Space Works`}
          aria-labelledby={decorative ? undefined : titleId}
          aria-hidden={decorative || undefined}
          focusable="false"
        >
          {!decorative && <title id={titleId}>{t`Space Works`}</title>}
          {artwork.clip ? <>
            <defs><clipPath id={`${titleId}-clip`}><rect width={artwork.clip.width} height={artwork.clip.height} /></clipPath></defs>
            <g clipPath={`url(#${titleId}-clip)`}>{artwork.paths.slice(0, artwork.clip.count - 4).map((path, index) => <path key={index} {...path} className={symClass(animated, true)} />)}</g>
            {artwork.paths.slice(artwork.clip.count - 4).map((path, index) => <path key={index} {...path} className={symClass(animated, index < 4, flapClass(index))} />)}
          </> : artwork.paths.map((path, index) => <path key={index} {...path} className={symClass(animated, index < symbolPaths, flapClass(index - symbolPaths + 4))} />)}
        </svg>
        {animated ? <LogoBoxOverlay shape={shape} width={width} height={height} offset={height / 4} surface={surface} oneColour={oneColour} /> : null}
      </span>
    </span>
  );
}

/** Symbol paths carry `sw-logo-sym` so the hover/focus opening can hide them while the overlay plays. */
function symClass(animated: boolean, symbol: boolean, base?: string) {
  const cls = [base, animated && symbol ? "sw-logo-sym" : undefined].filter(Boolean).join(" ");
  return cls || undefined;
}

const FLAPS = ["tl", "tr", "bl", "br"] as const;
function flapClass(flap: number) {
  return flap >= 0 && flap < 4 ? `sw-logo-flap sw-logo-flap-${FLAPS[flap]}` : undefined;
}

export function SpaceWorksHomeLink({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <Link
      aria-label={t`Space Works — Open makerspace listing`}
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
      <SpaceWorksLogo variant="symbol" size={48} decorative animated />
    </SpaceWorksHomeLink>
  );
}

export default SpaceWorksLogo;
