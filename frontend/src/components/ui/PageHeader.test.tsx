import { render, screen, fireEvent } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { PageHeader } from "./PageHeader";
import { expectNoA11yViolations } from "../../test/axe";

it("PageHeader renders its contract and remains accessible", async () => {
  const click=vi.fn();
  const { container } = render(<PageHeader eyebrow="Good morning, Meera" title="Requests" subtitle="Requests for this space." identity={{kind:"icon",icon:"Wrench",tone:"accent"}} back={{label:"All spaces",href:"/spaces"}} status={<span>Open</span>} meta="5 requests" primary={{label:"New request",onClick:click,icon:"Plus"}} secondary={{label:"Export",href:"/export"}} overflow={[{label:"Archive"}]} />);
  expect(screen.getByRole("heading",{level:1})).toHaveTextContent("Requests");
  fireEvent.click(screen.getByRole("button",{name:"New request"}));
  expect(click).toHaveBeenCalledOnce();
  await expectNoA11yViolations(container);
});
