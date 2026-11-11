import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { EventCheckInStationPage } from "./EventCheckInStationPage";
import { endStationSession, startStationSession } from "../staff/eventCheckInOfflineApi";
import { loadOfflineState, wipeOfflineState, type OfflineCheckInState } from "../staff/eventCheckInOfflineStore";

vi.mock("../staff/eventCheckInOfflineApi", () => ({ startStationSession: vi.fn(), endStationSession: vi.fn(), downloadStationRoster: vi.fn(), syncStationRoster: vi.fn() }));
vi.mock("../staff/eventCheckInOfflineStore", () => ({ loadOfflineState: vi.fn(), wipeOfflineState: vi.fn() }));
vi.mock("../staff/OfflineCheckInOperator", () => ({ OfflineCheckInOperator: () => <p>Offline operator ready</p> }));
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(startStationSession).mockResolvedValue(undefined);
  vi.mocked(wipeOfflineState).mockResolvedValue(undefined);
  vi.mocked(endStationSession).mockResolvedValue(undefined);
});
async function unlock() {
  render(<MemoryRouter initialEntries={["/event-check-in/token"]}><Routes><Route path="/event-check-in/:stationToken" element={<EventCheckInStationPage />} /></Routes></MemoryRouter>);
  fireEvent.change(screen.getByLabelText("Station PIN"), { target: { value: "12345678" } });
  fireEvent.click(screen.getByRole("button", { name: "Unlock station" }));
  await screen.findByText("Offline operator ready");
  expect(startStationSession).toHaveBeenCalledWith("token", "12345678");
}
it("keeps unsynced check-ins until explicit discard, then destroys local data before ending the session", async () => {
  vi.mocked(loadOfflineState).mockResolvedValue({ operations: [{ operation_id: "queued" }] } as unknown as OfflineCheckInState);
  await unlock();
  fireEvent.click(screen.getByRole("button", { name: "Lock station" }));
  await screen.findByRole("dialog", { name: "Discard check-ins and lock?" });
  expect(screen.getByText("1 unsynced check-ins will be permanently removed from this device before they reach the server.")).toBeVisible();
  expect(wipeOfflineState).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Keep working" }));
  expect(screen.getByText("Offline operator ready")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Lock station" }));
  fireEvent.click(await screen.findByRole("button", { name: "Discard and lock" }));
  await waitFor(() => expect(endStationSession).toHaveBeenCalledWith("token"));
  expect(wipeOfflineState).toHaveBeenCalledWith("station:token");
  expect(vi.mocked(wipeOfflineState).mock.invocationCallOrder[0]).toBeLessThan(vi.mocked(endStationSession).mock.invocationCallOrder[0]);
  expect(screen.getByLabelText("Station PIN")).toBeVisible();
});
it("keeps the station open if its local queue cannot be read", async () => {
  vi.mocked(loadOfflineState).mockRejectedValue(new Error("Storage unavailable"));
  await unlock();
  fireEvent.click(screen.getByRole("button", { name: "Lock station" }));
  await screen.findByText("Couldn't read local check-ins. Keep this station open and try again.");
  expect(wipeOfflineState).not.toHaveBeenCalled();
  expect(endStationSession).not.toHaveBeenCalled();
});
