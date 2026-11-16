import { t } from "@lingui/core/macro";
import { useEffect, useRef, useState, type MutableRefObject } from "react";

import type { IceServer, Signal } from "./adaptersApi";

/** How a viewer talks to the signaling relay: staff use the staff session, a job owner the member session. */
export type WatchTransport = {
  poll: (after: number) => Promise<{ signals: Signal[]; ice_servers: IceServer[] }>;
  signal: (body: { kind: Signal["kind"]; sdp?: string; candidate?: string }) => Promise<unknown>;
  frame: () => Promise<{ content_type: string | null; data: string | null }>;
};
type Mode = "connecting" | "live" | "stills" | "ended";
const POLL_MS = 1_000;
const LIVE_WAIT_MS = 10_000;
const FRAME_MS = 5_000;

const parseCandidate = (raw: string): RTCIceCandidateInit => {
  try { const value = JSON.parse(raw) as RTCIceCandidateInit; if (value && typeof value === "object") return value; } catch { /* a bare candidate line */ }
  return { candidate: raw, sdpMid: "0" };
};

/**
 * Live video of a camera while a watch is open: WebRTC (offer, answer and ICE relayed by the server, TURN
 * credentials when it provides them) with a fallback to refreshing stills. Nothing runs once the component unmounts.
 */
export type WatchAudioMode = "off" | "listen" | "talk";

/**
 * Audio (decision 321a) is receive-only unless `audio` is "talk": then a microphone track is added muted and `mic` hands it to
 * the push-to-talk button, which enables it only while the button is held. `muted` is the viewer's own mute.
 */
export function WatchViewer({ transport, label, audio = "off", muted = true, mic }: { transport: WatchTransport; label: string; audio?: WatchAudioMode; muted?: boolean; mic?: MutableRefObject<MediaStreamTrack | null> }) {
  const audioMode = useRef(audio);
  const micRef = useRef(mic);
  const video = useRef<HTMLVideoElement>(null);
  const [mode, setMode] = useState<Mode>("connecting");
  const [frame, setFrame] = useState<string | null>(null);
  const latest = useRef(transport);
  latest.current = transport;

  useEffect(() => {
    let stopped = false;
    let pc: RTCPeerConnection | null = null;
    const timers: number[] = [];
    const later = (fn: () => void, ms: number) => { timers.push(window.setTimeout(fn, ms)); };
    const fallBack = () => {
      if (stopped) return;
      pc?.close(); pc = null; setMode("stills");
      const refresh = async () => {
        if (stopped) return;
        try { const row = await latest.current.frame(); if (!stopped && row.data) setFrame(`data:${row.content_type ?? "image/jpeg"};base64,${row.data}`); }
        catch { if (!stopped) setMode("ended"); return; }
        later(() => { void refresh(); }, FRAME_MS);
      };
      void refresh();
    };
    const start = async () => {
      let first;
      try { first = await latest.current.poll(0); } catch { if (!stopped) setMode("ended"); return; }
      if (stopped) return;
      if (typeof RTCPeerConnection === "undefined") { fallBack(); return; }
      const connection = new RTCPeerConnection({ iceServers: first.ice_servers });
      pc = connection;
      let after = 0;
      connection.addTransceiver("video", { direction: "recvonly" });
      if (audioMode.current === "talk") {
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          const track = stream.getAudioTracks()[0];
          track.enabled = false;
          connection.addTrack(track, stream);
          if (micRef.current) micRef.current.current = track;
        } catch { connection.addTransceiver("audio", { direction: "recvonly" }); }
      } else if (audioMode.current === "listen") connection.addTransceiver("audio", { direction: "recvonly" });
      connection.onicecandidate = event => { if (event.candidate) void latest.current.signal({ kind: "candidate", candidate: JSON.stringify(event.candidate.toJSON()) }).catch(() => undefined); };
      connection.ontrack = event => { if (video.current) video.current.srcObject = event.streams[0] ?? new MediaStream([event.track]); setMode("live"); };
      connection.onconnectionstatechange = () => { if (connection.connectionState === "failed") fallBack(); };
      try {
        const offer = await connection.createOffer();
        await connection.setLocalDescription(offer);
        await latest.current.signal({ kind: "offer", sdp: offer.sdp ?? "" });
      } catch { fallBack(); return; }
      const poll = async () => {
        if (stopped || pc !== connection) return;
        try {
          const { signals } = await latest.current.poll(after);
          for (const message of signals) {
            after = Math.max(after, message.n);
            if (message.kind === "answer") await connection.setRemoteDescription({ type: "answer", sdp: message.sdp });
            else if (message.kind === "candidate") await connection.addIceCandidate(parseCandidate(message.candidate));
            else if (message.kind === "bye") { fallBack(); return; }
          }
        } catch { fallBack(); return; }
        later(() => { void poll(); }, POLL_MS);
      };
      void poll();
      later(() => { if (!stopped && pc === connection && connection.connectionState !== "connected") fallBack(); }, LIVE_WAIT_MS);
    };
    void start();
    return () => { stopped = true; timers.forEach(timer => window.clearTimeout(timer)); pc?.close(); // eslint-disable-next-line react-hooks/exhaustive-deps -- the ref holds a microphone track, not a DOM node
      if (micRef.current?.current) { micRef.current.current.stop(); micRef.current.current = null; } };
  }, []);

  return <figure className="grid gap-2" aria-label={label}>
    <div className="relative grid aspect-video place-items-center overflow-hidden rounded-xl border border-line bg-surface">
      <video ref={video} className={mode === "live" ? "size-full object-contain" : "hidden"} autoPlay playsInline muted={audio === "off" || muted} aria-label={label} />
      {mode === "stills" && frame ? <img src={frame} alt={label} className="size-full object-contain" /> : null}
      {mode === "connecting" || (mode === "stills" && !frame) || mode === "ended"
        ? <p className="p-4 text-center text-sm text-muted" role="status">{mode === "connecting" ? t`Connecting to the camera…`
          : mode === "ended" ? t`This watch has ended.` : t`Waiting for the camera to send a picture…`}</p> : null}
    </div>
    <figcaption className="text-xs text-muted" aria-live="polite">{mode === "live" ? t`Live` : mode === "stills" ? t`Live video is not available, so the picture refreshes every few seconds.` : ""}</figcaption>
  </figure>;
}
