import { render } from "@testing-library/react";
import { expect, it } from "vitest";
import { Skeleton } from "./Skeleton";
import { expectNoA11yViolations } from "../../test/axe";

it("Skeleton renders its contract and remains accessible", async () => {
  
  const { container } = render(<Skeleton className="h-4 w-20" />);
  expect(container.firstChild).toHaveAttribute("aria-hidden","true");
  await expectNoA11yViolations(container);
});
