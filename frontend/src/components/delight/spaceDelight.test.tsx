import { render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { DelightProvider, useDelight } from "./DelightProvider";
import { spaceAllows } from "./spaceDelight";

function Probe() {
  const policy = useDelight();
  return <p>{`effects:${policy.enabled} eggs:${policy.eggsEnabled}`}</p>;
}

afterEach(() => { delete window.__TENANT__; });

it("is on by default when the deployment says nothing", () => {
  render(<DelightProvider><Probe /></DelightProvider>);
  expect(screen.getByText("effects:true eggs:true")).toBeInTheDocument();
});

it("a space that turned effects off wins over the deployment default", () => {
  window.__TENANT__ = { uiDelightEnabled: true, uiEasterEggsEnabled: true };
  render(<DelightProvider spaceFeatures={["ui.easter_eggs"]}><Probe /></DelightProvider>);
  expect(screen.getByText("effects:false eggs:true")).toBeInTheDocument();
});

it("the deployment kill switch still turns everything off", () => {
  window.__TENANT__ = { uiDelightEnabled: false, uiEasterEggsEnabled: false };
  render(<DelightProvider spaceFeatures={["ui.delight", "ui.easter_eggs"]}><Probe /></DelightProvider>);
  expect(screen.getByText("effects:false eggs:false")).toBeInTheDocument();
});

it("an unknown space allows both", () => {
  expect(spaceAllows(null, "ui.delight")).toBe(true);
  expect(spaceAllows([], "ui.easter_eggs")).toBe(false);
});
