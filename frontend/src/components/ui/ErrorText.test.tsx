import { render, screen, fireEvent } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ErrorText } from "./ErrorText";
import { expectNoA11yViolations } from "../../test/axe";

it("ErrorText renders its contract and remains accessible", async () => {
  const click=vi.fn();
  const { container } = render(<ErrorText message="Request failed" resource="requests" onRetry={click} />);
  expect(screen.getByRole("alert")).toHaveTextContent("Couldn't load requests. Try again.");
  fireEvent.click(screen.getByRole("button",{name:"Retry"}));
  expect(click).toHaveBeenCalledOnce();
  await expectNoA11yViolations(container);
});
