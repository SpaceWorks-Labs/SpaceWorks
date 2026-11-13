import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { TicketCard } from "./TicketCard";
import { expectNoA11yViolations } from "../../test/axe";

it("TicketCard renders its contract and remains accessible", async () => {
  
  const { container } = render(<TicketCard organisation="Maker Space" title="Demo Summit" fields={[{label:"Guest",value:"Meera"}]} qr={<img src="/ticket-qr" alt="Private ticket QR" />} caption="Show this at the door. It only holds a private ticket link." />);
  expect(screen.getByRole("article",{name:"Demo Summit"})).toBeVisible();
  expect(screen.getByRole("img",{name:"Private ticket QR"})).toBeVisible();
  await expectNoA11yViolations(container);
});
