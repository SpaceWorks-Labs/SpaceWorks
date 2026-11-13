import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { PawPrint } from "lucide-react";
import { currentTheme, subscribeTheme } from "../../lib/theme";
import { useReducedMotion } from "./DelightProvider";
import "./patch.css";

// Patch, the mascot, appears only here. Walk sheets: eight 256x176 frames side by side, built from
// SpaceWorks-Design mascot/walk*/ (light) and mascot/dark/walk*/ (the dark theme's sticker border).
// Frame 6 (index 5) has the eyes closed, so it doubles as the nap. Never recolour or flip them.
const sheet = (name: string) => ({ light: `/brand/patch/${name}.webp`, dark: `/brand/patch/${name}-dark.webp` });
export const PATCH = { walkRight: sheet("patch-walk-right"), walkLeft: sheet("patch-walk-left") } as const;
const PATCH_WALK = { frames: 8, frameMs: 120, napFrame: 5 } as const;

type Facing = "left" | "right";
type Print = { id: number; x: number; facing: Facing };
const WIDTH = 128; // half the 256 px frame: crisp on 2x screens, never upscaled
const SPEED = 0.18; // px per ms, a trot
const WANDER_AFTER = 4000; // idle ms before Patch strolls off on its own
const NAP_AFTER = 15000; // idle ms before Patch naps on walk frame 6 (eyes closed, as drawn)
const PRINT_EVERY = 40; // px walked between paw prints
const MAX_PRINTS = 6;

/**
 * The 404 page's pet. Patch trots along the bottom of the screen towards the pointer or a tap,
 * using the approved left-facing sheet when heading left (never a CSS flip), wanders when left
 * alone and then naps. Decorative only: hidden from assistive tech, no pointer events, and still
 * under reduced motion. The behaviour is adapted from AGPL-3.0 code; the attribution is in NOTICE.
 */
export function NotFoundPatch() {
  const reduced = useReducedMotion();
  // Only the current theme's sheet is set, so only it downloads.
  const theme = useSyncExternalStore(subscribeTheme, currentTheme, () => "light" as const);
  const body = useRef<HTMLDivElement>(null);
  const [facing, setFacing] = useState<Facing>("right");
  const [napping, setNapping] = useState(false);
  const [prints, setPrints] = useState<Print[]>([]);

  useEffect(() => {
    if (reduced) return;
    const limit = () => Math.max(0, window.innerWidth - WIDTH);
    let x = Math.min(limit(), window.innerWidth * 0.15), target = x;
    let last: number | null = null, lastInput = 0, stride = 0, travelled = 0, nextPrint = 0, raf = 0;
    let face: Facing = "right", asleep = false;
    // Positions and frames are written straight to the DOM each frame; React state changes
    // only when the facing, the nap or the paw prints change.
    const aim = (centre: number) => {
      target = Math.max(0, Math.min(limit(), centre - WIDTH / 2));
      if (Math.abs(target - x) < 2) return;
      const next: Facing = target < x ? "left" : "right";
      if (next !== face) { face = next; setFacing(next); }
    };
    const follow = (event: PointerEvent) => {
      lastInput = last ?? 0;
      if (asleep) { asleep = false; setNapping(false); }
      aim(event.clientX);
    };
    const tick = (now: number) => {
      const dt = last === null ? 0 : Math.min(64, now - last);
      if (last === null) lastInput = now;
      last = now;
      const idle = now - lastInput, arrived = Math.abs(target - x) < 0.5;
      if (arrived && !asleep && idle > NAP_AFTER) { asleep = true; setNapping(true); }
      else if (arrived && !asleep && idle > WANDER_AFTER && Math.random() < dt / 2000) aim(Math.random() * window.innerWidth);
      const step = Math.sign(target - x) * Math.min(Math.abs(target - x), SPEED * dt);
      x += step;
      let frame = asleep ? PATCH_WALK.napFrame : 0;
      if (step !== 0) {
        stride += dt; travelled += Math.abs(step);
        frame = Math.floor(stride / PATCH_WALK.frameMs) % PATCH_WALK.frames;
        if (travelled >= PRINT_EVERY) {
          travelled = 0;
          const print = { id: nextPrint++, x: x + WIDTH / 2, facing: face };
          setPrints(list => [...list.slice(1 - MAX_PRINTS), print]);
        }
      }
      if (body.current) {
        body.current.style.transform = `translateX(${x}px)`;
        body.current.style.setProperty("--sw-patch-frame", `${-frame * WIDTH}px`);
      }
      raf = requestAnimationFrame(tick);
    };
    window.addEventListener("pointermove", follow, { passive: true });
    window.addEventListener("pointerdown", follow, { passive: true });
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", follow);
      window.removeEventListener("pointerdown", follow);
    };
  }, [reduced]);

  const walkSheet = (facing === "left" ? PATCH.walkLeft : PATCH.walkRight)[theme];
  return <div aria-hidden="true" className="sw-patch-pet" data-patch-pet="">
    {prints.map(print => <PawPrint key={print.id} size={14} className="sw-patch-print"
      style={{ left: print.x - 7, rotate: print.facing === "left" ? "-90deg" : "90deg" }} />)}
    <div ref={body} className="sw-patch-pet-body" data-facing={facing} data-napping={napping ? "" : undefined}
      style={reduced ? { left: "50%", transform: "translateX(-50%)" } : undefined}>
      <span className="sw-patch-pet-sprite" style={{ backgroundImage: `url(${walkSheet})` }} />
      {napping ? <span className="sw-patch-z">z</span> : null}
    </div>
  </div>;
}
