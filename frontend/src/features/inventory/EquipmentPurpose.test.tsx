import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { EquipmentPurpose } from "./EquipmentPurpose";

it("allows independently selected event and booking while excluding a disabled domain", () => {
  const change = vi.fn();
  const view = render(<EquipmentPurpose value={{ eventRegistrationId: null, bookingToken: null }} onChange={change}
    events={[{ registrationId: 3, label: "Workshop" }]} bookings={[{ token: "11111111-1111-4111-8111-111111111111", label: "Room" }]} eventsEnabled bookingsEnabled />);
  fireEvent.change(screen.getByLabelText("Your event"), { target: { value: "3" } });
  expect(change).toHaveBeenCalledWith({ eventRegistrationId: 3, bookingToken: null });
  view.rerender(<EquipmentPurpose value={{ eventRegistrationId: 3, bookingToken: null }} onChange={change}
    events={[]} bookings={[]} eventsEnabled={false} bookingsEnabled />);
  expect(screen.queryByLabelText("Your event")).toBeNull();
  expect(screen.getByLabelText("Your booking")).toBeTruthy();
});
