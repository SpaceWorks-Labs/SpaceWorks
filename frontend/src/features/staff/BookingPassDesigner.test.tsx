import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { expectNoA11yViolations } from "../../test/axe";
import { BookingPassDesigner } from "./BookingPassDesigner";

const { designer } = vi.hoisted(() => ({ designer: vi.fn() }));
vi.mock("./bookingPassApi", () => ({ useBookingPassDesigner: designer, downloadPass: vi.fn() }));
const template = {
  version: 2, paper_size: "A4", orientation: "portrait", grid_mm: 1,
  card_width_mm: 90, card_height_mm: 60, margin_mm: 10, gap_mm: 5,
  elements: ["name", "resource", "booking_window", "reference"].map((field, i) => ({
    field, x_mm: 4, y_mm: 4 + i * 12, width_mm: 82, height_mm: 10,
    font: "sans", font_size_pt: 10, bold: false, align: "left", colour: "#111111",
  })),
};
const save = vi.fn();
const preview = vi.fn();
beforeEach(() => {
  save.mockReset(); preview.mockReset();
  designer.mockReturnValue({ query: { isPending: false, data: structuredClone(template), error: null },
    save: { mutate: save, isPending: false, error: null }, preview: { mutate: preview, isPending: false, error: null } });
});

it("offers only four safe fields, edits geometry and previews fictional data", async () => {
  const { container } = render(<BookingPassDesigner makerspaceId={3} spaceId={9} />);
  expect(designer).toHaveBeenCalledWith(3, 9);
  for (const field of ["Display name", "Resource", "Booking window", "Booking reference"]) {
    expect(screen.getByRole("checkbox", { name: field })).toBeChecked();
  }
  expect(screen.queryByText(/custom answer/i)).not.toBeInTheDocument();
  expect(screen.queryByRole("checkbox", { name: /email|phone|notes|qr/i })).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Card width (mm)"), { target: { value: "100" } });
  fireEvent.click(screen.getByRole("checkbox", { name: "Booking reference" }));
  fireEvent.click(screen.getByRole("button", { name: "Save pass layout" }));
  expect(save.mock.calls[0][0].card_width_mm).toBe(100);
  expect(save.mock.calls[0][0].elements.map((e: { field: string }) => e.field)).not.toContain("reference");
  fireEvent.click(screen.getByRole("button", { name: "Download sample PDF" }));
  expect(preview.mock.calls[0][0]).not.toHaveProperty("booking_id");
  await expectNoA11yViolations(container);
});

it("shows loading, failure, pending rendering and overflow states", () => {
  const state = { save: { mutate: save, isPending: false, error: null }, preview: { mutate: preview, isPending: false, error: null } };
  designer.mockReturnValue({ ...state, query: { isPending: true } });
  const { rerender } = render(<BookingPassDesigner makerspaceId={3} spaceId={9} />);
  expect(screen.getByRole("status")).toHaveTextContent("Loading pass layout");
  designer.mockReturnValue({ ...state, query: { isPending: false, error: new Error("Permission revoked") } });
  rerender(<BookingPassDesigner makerspaceId={3} spaceId={9} />);
  expect(screen.getByRole("alert")).toHaveTextContent("Permission revoked");
  const overflow = structuredClone(template);
  overflow.elements[0].x_mm = 89;
  designer.mockReturnValue({ query: { isPending: false, data: overflow },
    save: { mutate: save, isPending: false }, preview: { mutate: preview, isPending: false } });
  rerender(<BookingPassDesigner makerspaceId={3} spaceId={9} />);
  expect(screen.getByRole("button", { name: "Save pass layout" })).toBeDisabled();
  expect(screen.getByRole("alert")).toHaveTextContent("outside the printable area");
});
