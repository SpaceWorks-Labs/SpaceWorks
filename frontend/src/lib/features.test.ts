import { expect, it } from "vitest";
import { FEATURE_DEFINITIONS } from "./features";
import { FEATURE_DEFINITIONS_1 } from "./featureDefinitions/part1";
import { FEATURE_DEFINITIONS_2 } from "./featureDefinitions/part2";
import { FEATURE_DEFINITIONS_3 } from "./featureDefinitions/part3";
import { FEATURE_DEFINITIONS_4 } from "./featureDefinitions/part4";
import { FEATURE_DEFINITIONS_5 } from "./featureDefinitions/part5";

it("concatenates the definition slices in registry order without losing or duplicating a key", () => {
  const slices = [FEATURE_DEFINITIONS_1, FEATURE_DEFINITIONS_2, FEATURE_DEFINITIONS_3, FEATURE_DEFINITIONS_4, FEATURE_DEFINITIONS_5];
  expect(FEATURE_DEFINITIONS.map(feature => feature.key)).toEqual(slices.flat().map(feature => feature.key));
  expect(FEATURE_DEFINITIONS).toHaveLength(264);
  expect(new Set(FEATURE_DEFINITIONS.map(feature => feature.key)).size).toBe(264);
  expect(FEATURE_DEFINITIONS[0].key).toBe("notifications.quiet_hours");
  expect(FEATURE_DEFINITIONS[FEATURE_DEFINITIONS.length - 1].key).toBe("display.anthias_push");
});
