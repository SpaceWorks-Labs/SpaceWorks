import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { MyCard } from "./api";
import { CardFaceSvg, type CardFace } from "./CardFaces";
import { HolographicCard } from "./HolographicCard";
import { PhotoCleanup, waitForJob } from "./PhotoCleanup";

const api = vi.hoisted(() => ({ memberRequest: vi.fn(), memberRequestBlob: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...(await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api")), ...api }));

const card: MyCard = { kind: "programme_card", id: 9, makerspace_id: 2, issuer: "Makers Guild", title: "Student ID",
  name: "Priya Raman", number: "MKG-2026-0001", label: "Student ID", valid_until: "30 Jun 2027", status: "valid",
  has_back: true, check_url: "", photo_request_open: false, wallet_platforms: [], email_available: true, qr_image: null,
  photo_set: true, photo_cleanup_available: true, photo_aspect: 0.8 };
const side = (text: string) => ({ page_width_mm: 85.6, page_height_mm: 53.98, background: { kind: "colour", colour: "#FFF4E8" },
  layers: [{ id: text, kind: "text", name: text, x_mm: 4, y_mm: 4, w_mm: 60, h_mm: 8, rotation: 0, opacity: 100, locked: false,
    hidden: false, text, font_size_pt: 10, colour: "#142C2A" }] });
const face = { document: { version: 2, stock: "cr80-landscape", back_enabled: true, mono: false,
  watermark: { kind: "none", text: "", asset_id: null, opacity_pct: 10, angle_deg: 0, colour: "#000000" },
  front: side("{{name}}"), back: side("Back of {{name}}") }, values: { name: "Priya Raman" }, photo: null, logos: {}, assets: {},
  desk_qr: null, verify_qr: "data:image/svg+xml;base64,AA==" } as unknown as CardFace;

function wrap(element: React.JSX.Element) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{element}</QueryClientProvider>);
}

beforeEach(() => { api.memberRequest.mockReset(); api.memberRequestBlob.mockReset(); });

describe("printed card view (SPEC §8)", () => {
  it("draws the design's own layers with the holder's values", () => {
    render(<CardFaceSvg face={face} side="front" label="Student ID card for Priya Raman, front" />);
    expect(screen.getByRole("img", { name: "Student ID card for Priya Raman, front" })).toBeInTheDocument();
    expect(screen.getByText("Priya Raman")).toBeInTheDocument();
  });

  it("uses the drawn face and only falls back to the server PNG when the face cannot load", async () => {
    api.memberRequest.mockResolvedValue(face);
    wrap(<HolographicCard card={card} />);
    expect((await screen.findAllByText("Priya Raman")).length).toBeGreaterThan(0);
    expect(api.memberRequest).toHaveBeenCalledWith("/member/cards/programme_card/9/face");
    expect(api.memberRequestBlob.mock.calls.every(([path]) => !String(path).includes("/download"))).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Show back" }));
    expect(screen.getByRole("button", { name: "Show front" })).toHaveAttribute("aria-pressed", "true");
  });
});

describe("photo clean-up (Q-I3)", () => {
  it("is hidden when the server has no clean-up model or the card has no photo", () => {
    const { container } = wrap(<PhotoCleanup card={{ ...card, photo_cleanup_available: false }} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the candidate and lets the holder keep their original", async () => {
    api.memberRequest.mockImplementation((path: string) => Promise.resolve(
      path.endsWith("/photo/cleanup") ? { id: 5, state: "queued" }
        : path === "/member/card-jobs/5" ? { id: 5, state: "succeeded" }
          : path.endsWith("/result") ? { url: "https://storage.example/candidate.png" } : {}));
    wrap(<PhotoCleanup card={card} />);
    fireEvent.click(screen.getByRole("button", { name: "Clean up the background" }));
    expect(await screen.findByAltText("Your photo with a cleaned background")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Keep my original" }));
    await waitFor(() => expect(api.memberRequest).toHaveBeenCalledWith("/member/cards/programme_card/9/photo/discard",
      { method: "POST", body: JSON.stringify({ job_id: 5 }) }));
    expect(await screen.findByText("You kept your original photo.")).toBeVisible();
  });

  it("waits for a running job without real timers", async () => {
    api.memberRequest.mockResolvedValueOnce({ id: 1, state: "running" }).mockResolvedValueOnce({ id: 1, state: "succeeded" });
    const job = await waitForJob(1, () => Promise.resolve());
    expect(job.state).toBe("succeeded");
  });
});
