// The printed card (server PNG, the source of truth) with tilt, sheen and flip. Tilt and sheen
// run only with interface effects on and motion allowed; otherwise flip is an instant swap.
import { useEffect, useRef, useState, type PointerEvent } from "react";

import { useDelight, useReducedMotion } from "../../../components/delight/DelightProvider";
import { useCardImage, type MyCard } from "./api";

type OrientationRequest = { requestPermission?: () => Promise<"granted" | "denied"> };

export function HolographicCard({ card }: { card: MyCard }) {
  const delight = useDelight();
  const reduced = useReducedMotion();
  const motion = delight.enabled && !reduced;
  const [flipped, setFlipped] = useState(false);
  const [tilt, setTilt] = useState({ x: 0, y: 0 });
  const [needsPermission, setNeedsPermission] = useState(false);
  const frame = useRef(0);
  const front = useCardImage(card, "front", true);
  const back = useCardImage(card, "back", card.has_back);
  const name = `${card.title} for ${card.name}, ${flipped ? "back" : "front"}`;

  const schedule = (next: { x: number; y: number }) => {
    cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(() => setTilt(next));
  };
  useEffect(() => () => cancelAnimationFrame(frame.current), []);
  useEffect(() => {
    if (!motion || !window.matchMedia?.("(pointer: coarse)").matches) return;
    const request = (window.DeviceOrientationEvent as unknown as OrientationRequest | undefined)?.requestPermission;
    if (typeof request === "function") { setNeedsPermission(true); return; }
    const onOrientation = (event: DeviceOrientationEvent) => {
      const clampUnit = (value: number) => Math.max(-1, Math.min(1, value));
      schedule({ x: clampUnit((event.gamma ?? 0) / 30), y: clampUnit(((event.beta ?? 45) - 45) / 30) });
    };
    window.addEventListener("deviceorientation", onOrientation);
    return () => window.removeEventListener("deviceorientation", onOrientation);
  }, [motion]);

  function onPointerMove(event: PointerEvent<HTMLButtonElement>) {
    if (!motion || event.pointerType === "touch") return;
    const box = event.currentTarget.getBoundingClientRect();
    schedule({ x: ((event.clientX - box.left) / box.width) * 2 - 1, y: ((event.clientY - box.top) / box.height) * 2 - 1 });
  }

  const transform = motion
    ? `perspective(1200px) rotateX(${-tilt.y * 9}deg) rotateY(${(flipped ? 180 : 0) + tilt.x * 9}deg)`
    : undefined;
  const face = "absolute inset-0 grid place-items-center overflow-hidden rounded-[4%] [backface-visibility:hidden]";
  const image = (url: string | undefined, label: string) => url
    ? <img src={url} alt="" className="h-full w-full object-contain" draggable={false} />
    : <span className="text-sm text-muted">{label}</span>;

  return <div className="grid justify-items-center gap-3">
    <button type="button" aria-label={name} onPointerMove={onPointerMove} onPointerLeave={() => schedule({ x: 0, y: 0 })}
      onClick={() => card.has_back && setFlipped((value) => !value)}
      className="relative aspect-[85.6/53.98] w-full max-w-md rounded-[4%] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-focus">
      <div className="relative h-full w-full [transform-style:preserve-3d]" style={{ transform,
        transition: motion ? "transform 650ms cubic-bezier(0.32,0.72,0,1)" : undefined }}>
        <div className={face} aria-hidden={flipped} style={motion ? undefined : { visibility: flipped ? "hidden" : "visible" }}>
          {image(front.data, front.isError ? "The card image couldn't load." : "Loading the card…")}
        </div>
        {card.has_back ? <div className={face} aria-hidden={!flipped}
          style={motion ? { transform: "rotateY(180deg)" } : { visibility: flipped ? "visible" : "hidden" }}>
          {image(back.data, back.isError ? "The card image couldn't load." : "Loading the back…")}
        </div> : null}
        {motion ? <span aria-hidden="true" className="pointer-events-none absolute inset-0 rounded-[4%] mix-blend-soft-light" style={{
          opacity: 0.18, background: `linear-gradient(${115 + tilt.x * 40}deg, rgba(232,255,113,0) 20%, #E8FF71 ${45 + tilt.y * 15}%, #B7E4F9 ${55 + tilt.y * 15}%, #FFF4E8 70%, rgba(255,244,232,0) 85%)` }} /> : null}
      </div>
    </button>
    <div className="flex flex-wrap justify-center gap-2">
      {card.has_back ? <button type="button" className="desk-button min-h-11" aria-pressed={flipped}
        onClick={() => setFlipped((value) => !value)}>{flipped ? "Show front" : "Show back"}</button> : null}
      {needsPermission ? <button type="button" className="desk-button-ghost min-h-11" onClick={async () => {
        const request = (window.DeviceOrientationEvent as unknown as OrientationRequest).requestPermission;
        if (request && (await request().catch(() => "denied")) === "granted") {
          setNeedsPermission(false);
          window.addEventListener("deviceorientation", (event) => schedule({
            x: Math.max(-1, Math.min(1, (event.gamma ?? 0) / 30)), y: Math.max(-1, Math.min(1, ((event.beta ?? 45) - 45) / 30)) }));
        }
      }}>Tilt with your phone</button> : null}
    </div>
  </div>;
}
