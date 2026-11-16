import { render } from "@testing-library/react";
import { expect, it } from "vitest";
import { Icon, type IconName } from "./icon";
import { expectNoA11yViolations } from "../../test/axe";

it("Icon renders its contract and remains accessible", async () => {
  
  const { container } = render(<Icon name="Wrench" />);
  expect(container.querySelector("svg")).toHaveAttribute("aria-hidden","true");
  expect(container.querySelector("svg")).toHaveAttribute("stroke-width","2");
  await expectNoA11yViolations(container);
});

it.each<IconName>(["Lock", "Mail", "KeyRound", "Building2", "ShieldCheck", "ShieldAlert", "Compass", "Eye", "EyeOff", "MapPin", "Cog", "Printer"])("registers the %s Lucide glyph", name => {
  const { container } = render(<Icon name={name} />);
  expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  expect(container.querySelector("svg")).toHaveAttribute("stroke-width", "2");
});
