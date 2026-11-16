import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

const printNodes = vi.fn();
vi.mock("../../../components/card-print", async (original) => ({ ...(await original<object>()), printNodes: (...args: unknown[]) => printNodes(...args) }));
vi.mock("./DeskBadgeFace", () => ({ deskSize: () => ({ widthMm: 100, heightMm: 150 }), DeskBadgeFace: () => <div data-testid="face"><span /></div> }));

import { DeskPrintSheet } from "./DeskPrintSheet";
import type { DeskBadge, DeskBundle } from "./deskBadgeApi";

const badge: DeskBadge = { registration_id: 7, card_id: null, name: "Priya Raman", role: "attendee", role_label: "Attendee", team: "", crew_kind: "",
  answers: {}, photo_card_id: null, provisional: false, status: "attended", checkin_payload: null };
const bundle: DeskBundle = { roles: { attendee: "attendee" }, logos: {}, designs: { attendee: { design_id: 1, revision: 1, stock: "4x6", settings: null,
  document: { front: { page_width_mm: 100, page_height_mm: 150, layers: [] } } } } };
beforeEach(() => { printNodes.mockReset(); printNodes.mockResolvedValue("printed"); });

it("prints on Enter and records the print with its stock and role", async () => {
  const onPrinted = vi.fn().mockResolvedValue("sent");
  render(<DeskPrintSheet badge={badge} bundle={bundle} onPrinted={onPrinted} onSkip={vi.fn()} />);
  fireEvent.keyDown(document.body, { key: "Enter" });
  await waitFor(() => expect(onPrinted).toHaveBeenCalledWith({ stock: "4x6", role: "attendee" }));
  expect(printNodes).toHaveBeenCalledWith(expect.anything(), { widthMm: 100, heightMm: 150 }, expect.anything());
  expect(await screen.findByRole("button", { name: "Print again" })).toBeInTheDocument();
});

it("tells the operator when the pop-up is blocked and records nothing", async () => {
  printNodes.mockResolvedValue("blocked");
  const onPrinted = vi.fn();
  render(<DeskPrintSheet badge={badge} bundle={bundle} onPrinted={onPrinted} onSkip={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: /Print badge/ }));
  expect(await screen.findByText(/blocked the print window/)).toBeInTheDocument();
  expect(onPrinted).not.toHaveBeenCalled();
});

it("offers Edit design only when an edit handler is given (never on a station)", () => {
  const { rerender } = render(<DeskPrintSheet badge={badge} bundle={bundle} onPrinted={vi.fn()} onSkip={vi.fn()} />);
  expect(screen.queryByRole("button", { name: "Edit design" })).toBeNull();
  rerender(<DeskPrintSheet badge={badge} bundle={bundle} onPrinted={vi.fn()} onSkip={vi.fn()} onEdit={vi.fn()} />);
  expect(screen.getByRole("button", { name: "Edit design" })).toBeInTheDocument();
});

it("falls back to the attendee design for a role without its own", () => {
  render(<DeskPrintSheet badge={{ ...badge, role: "speaker" }} bundle={bundle} onPrinted={vi.fn()} onSkip={vi.fn()} />);
  expect(screen.getAllByTestId("face").length).toBeGreaterThan(0);
});
