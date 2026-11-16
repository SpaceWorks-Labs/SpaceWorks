import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";
import { expectNoA11yViolations } from "../../test/axe";
import { SavedDetailEditor } from "./SavedDetailEditor";
import { SaveDetailChoice, SaveIntentNotice } from "./RegistrationSavedDetails";
import { fields } from "./fieldPresentation";
import { deleteDetail, saveDetail, saveIntentStatus } from "./api";
import type { SavedField } from "./types";

vi.mock("./api", () => ({ deleteDetail: vi.fn(), saveDetail: vi.fn(), saveIntentStatus: vi.fn() }));
beforeEach(() => vi.resetAllMocks());
function wrapper(children: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
const institution = fields.find(f => f.key === "institution")!;
const initial: SavedField = { field_key: "institution", value: "Saved college", version: 1, sensitive: false, default_save: true };

it("keeps sensitive save choices off and other choices on", () => {
  const result = render(wrapper(<SavedDetailEditor actorId={17} presentation={fields.find(f => f.key === "date_of_birth")!} version={0} />));
  expect(screen.getByRole("checkbox")).not.toBeChecked();
  expect(screen.getByRole("button", { name: "Save date of birth" })).toBeDisabled();
  result.unmount();
  render(wrapper(<SavedDetailEditor actorId={17} presentation={institution} version={0} />));
  expect(screen.getByRole("checkbox")).toBeChecked();
});

it("preserves a draft and its old base version after conflict until explicit review", async () => {
  vi.mocked(saveDetail).mockRejectedValue(new Error("This saved detail changed."));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const ui = (saved: SavedField) => <QueryClientProvider client={client}><SavedDetailEditor actorId={17} presentation={institution} saved={saved} version={saved.version} /></QueryClientProvider>;
  const result = render(ui(initial));
  fireEvent.change(screen.getByRole("textbox", { name: "School or college" }), { target: { value: "My unsaved draft" } });
  fireEvent.click(screen.getByRole("button", { name: "Save school or college" }));
  await screen.findByRole("alert");
  result.rerender(ui({ ...initial, value: "New server value", version: 2 }));
  expect(screen.getByRole("textbox", { name: "School or college" })).toHaveValue("My unsaved draft");
  expect(vi.mocked(saveDetail).mock.calls[0][2].expected_version).toBe(1);
  fireEvent.click(screen.getByRole("button", { name: "Review current saved value" }));
  expect(screen.getByRole("textbox", { name: "School or college" })).toHaveValue("New server value");
  expect(localStorage.length).toBe(0);
});

it("retries a lost delete response with the same operation ID", async () => {
  vi.mocked(deleteDetail).mockRejectedValueOnce(new Error("Connection lost")).mockResolvedValueOnce({ field_key: "institution", version: 2 });
  render(wrapper(<SavedDetailEditor actorId={17} presentation={institution} saved={initial} version={1} />));
  fireEvent.click(screen.getByRole("button", { name: "Delete school or college" }));
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "Delete school or college" }));
  await waitFor(() => expect(deleteDetail).toHaveBeenCalledTimes(2));
  expect(vi.mocked(deleteDetail).mock.calls[0][1].operation_id).toBe(vi.mocked(deleteDetail).mock.calls[1][1].operation_id);
});

it("uses accessible compound contact controls and labelled sensitive choice", async () => {
  const result = render(wrapper(<SavedDetailEditor actorId={17} presentation={fields.find(f => f.key === "emergency_contact")!} version={0} />));
  expect(screen.getByRole("textbox", { name: "Contact name" })).toBeVisible();
  expect(screen.getByRole("textbox", { name: "Relationship" })).toBeVisible();
  expect(screen.getByRole("textbox", { name: "Contact phone" })).toBeVisible();
  await expectNoA11yViolations(result.container);
});

it("keeps event success separate from failed private save application", async () => {
  vi.mocked(saveIntentStatus).mockResolvedValue({ operation_id: "11111111-1111-4111-8111-111111111111", state: "conflict", fields: {}, retryable: false });
  render(wrapper(<SaveIntentNotice actorId={17} operationId="11111111-1111-4111-8111-111111111111" />));
  expect(await screen.findByRole("link", { name: "Review saved details" })).toBeVisible();
  expect(screen.getByRole("status")).toHaveTextContent("Your event submission succeeded.");
});

it("renders a sensitive choice as an explicit controlled checkbox", () => {
  const change = vi.fn();
  render(<SaveDetailChoice fieldKey="date_of_birth" sensitive checked={false} onChange={change} />);
  fireEvent.click(screen.getByRole("checkbox"));
  expect(change).toHaveBeenCalledWith(true);
});
