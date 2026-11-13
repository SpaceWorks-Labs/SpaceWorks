import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { SkeletonRows } from "./Skeleton";
import { expectNoA11yViolations } from "../../test/axe";

it("SkeletonRows renders its contract and remains accessible", async () => {
  
  const { container } = render(<table role="table" aria-label="Loading items"><tbody role="rowgroup"><SkeletonRows rows={2} cols={3} /></tbody></table>);
  expect(screen.getAllByRole("row")).toHaveLength(2);
  expect(screen.getAllByRole("cell")).toHaveLength(6);
  await expectNoA11yViolations(container);
});
