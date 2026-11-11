/**
 * The scan-a-tool panel lives in a ~300px column beside the catalogue at desktop widths. Check out
 * and Return used to sit side by side there, wrapping their labels one word per line. These pin the
 * stacked shape: one choice, one visible primary action, and photo evidence that survives a switch.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import type { Product } from "../../types/inventory";

const { publicToolCheckout, publicToolReturn, requestPublicEvidenceUpload, uploadPublicEvidenceFile } = vi.hoisted(() => ({
  publicToolCheckout: vi.fn(), publicToolReturn: vi.fn(),
  requestPublicEvidenceUpload: vi.fn(), uploadPublicEvidenceFile: vi.fn(),
}));
vi.mock("./api", async () => ({ ...(await vi.importActual<typeof import("./api")>("./api")), publicToolCheckout, publicToolReturn }));
vi.mock("./selfCheckoutApi", async () => ({ ...(await vi.importActual<typeof import("./selfCheckoutApi")>("./selfCheckoutApi")),
  requestPublicEvidenceUpload, uploadPublicEvidenceFile }));
vi.mock("../../components/ui/QrScanner", () => ({
  default: ({ onScan }: { onScan: (value: string) => void }) => <button type="button" onClick={() => onScan("tool-qr")}>Fake scan</button>,
}));

import { PublicToolScanPanel } from "./PublicToolScanPanel";
import { ProductCard } from "./ProductCard";

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><PublicToolScanPanel makerspaceSlug="lab" /></QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  requestPublicEvidenceUpload.mockResolvedValue({ evidence_id: 41 });
  uploadPublicEvidenceFile.mockResolvedValue(undefined);
  publicToolCheckout.mockResolvedValue({ status: "issued", public_token: "tok", items: [{ product_name: "Drill", quantity: 1 }] });
});

it("shows one action at a time instead of side-by-side check out and return forms", () => {
  renderPanel();
  expect(screen.getByRole("radio", { name: "Check out" })).toHaveAttribute("aria-checked", "true");
  expect(screen.getByRole("button", { name: "Check out" })).toHaveClass("desk-button-brand", "w-full");
  expect(screen.queryByRole("button", { name: "Return" })).toBeNull();
  expect(screen.getByLabelText("Return condition notes")).not.toBeVisible();

  fireEvent.click(screen.getByRole("radio", { name: "Return" }));
  expect(screen.getByRole("button", { name: "Return" })).toHaveClass("desk-button-brand", "w-full");
  expect(screen.queryByRole("button", { name: "Check out" })).toBeNull();
  expect(screen.getByLabelText("Return condition notes")).toBeVisible();
  expect(screen.getByLabelText("Report a problem with this tool")).toBeVisible();
});

it("keeps an uploaded photo across a mode switch and checks out after a scan", async () => {
  renderPanel();
  fireEvent.change(screen.getByLabelText("Issue photo"), { target: { files: [new File(["x"], "drill.jpg", { type: "image/jpeg" })] } });
  await screen.findByText("Photo uploaded");
  expect(screen.getByText("Scan the tool's QR label first.")).toBeVisible();

  fireEvent.click(screen.getByRole("radio", { name: "Return" }));
  fireEvent.click(screen.getByRole("radio", { name: "Check out" }));
  fireEvent.click(screen.getByRole("button", { name: "Scan QR with camera" }));
  fireEvent.click(screen.getByRole("button", { name: "Fake scan" }));
  expect(screen.getByText("Tool scanned")).toBeVisible();

  const checkout = screen.getByRole("button", { name: "Check out" });
  expect(checkout).toBeEnabled();
  fireEvent.click(checkout);
  await waitFor(() => expect(publicToolCheckout).toHaveBeenCalledWith("lab", { payload: "tool-qr", evidence_id: 41 }));
});

it("gives an item without a photo a short initials band, not a tall empty panel", () => {
  const product = { id: 3, name: "Soldering kit", description: "", availability: null, image_url: null } as Product;
  render(<MemoryRouter><ProductCard product={product} quantity={0} onIncrement={vi.fn()} onDecrement={vi.fn()} onOpenDetails={vi.fn()} /></MemoryRouter>);
  const frame = screen.getByRole("button", { name: "Open details for Soldering kit" });
  expect(frame).toHaveClass("h-24");
  expect(frame).not.toHaveClass("aspect-[4/3]");
});

it("offers only Return when account-less checkout is switched off, because returns always stay open", () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><PublicToolScanPanel makerspaceSlug="lab" borrowOff /></QueryClientProvider>);
  expect(screen.getByRole("heading", { name: "Return a tool" })).toBeVisible();
  expect(screen.queryByRole("radio", { name: "Check out" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Check out" })).toBeNull();
  expect(screen.getByRole("button", { name: "Return" })).toBeDisabled();
  expect(screen.getByLabelText("Return condition notes")).toBeVisible();
});

it("names a finished checkout in words rather than a raw status", async () => {
  publicToolCheckout.mockResolvedValue({ status: "checked_out", public_token: "tok", items: [{ product_name: "Drill", quantity: 1 }] });
  renderPanel();
  fireEvent.change(screen.getByLabelText("Issue photo"), { target: { files: [new File(["x"], "drill.jpg", { type: "image/jpeg" })] } });
  await screen.findByText("Photo uploaded");
  fireEvent.click(screen.getByRole("button", { name: "Scan QR with camera" }));
  fireEvent.click(screen.getByRole("button", { name: "Fake scan" }));
  fireEvent.click(screen.getByRole("button", { name: "Check out" }));
  expect(await screen.findByRole("heading", { name: "Checked out: Drill" })).toBeVisible();
});
