import { t } from "@lingui/core/macro";
import type { Side } from "../../components/card-designer/cardTypes";
import { renderPattern } from "../../components/card-designer/numberPattern";
import sampleCard from "./sampleCard.generated.json";

// The sample staff ID card is NOT hand-drawn: sampleCard.generated.json is written by the real card
// generator (scripts/export_sample_card.py: the Aurora look through default_templates + staff_document,
// plus a logo tile in the header). Regenerate it with `python scripts/export_sample_card.py`; the guard
// test backend/tests/parity_0120/sample_card fails when it drifts from the generator.
export const CARD_W = 85.6, CARD_H = 53.98;
export const SAMPLE_LOOK = "aurora";
// The backend renderer resolves a data field from `field`; the browser renderer (like the designer, which
// writes `{{field}}` into `text` when it adds one) merges `text`, so the same document gets that one line.
const front = sampleCard.front as unknown as Side;
const withText: Side = { ...front, layers: front.layers.map(layer =>
  layer.kind === "data_field" && layer.field && !layer.text ? { ...layer, text: `{{${layer.field}}}` } : layer) };
export const sampleIdCardFront = (): Side => withText;

// The sample number comes from the card engine's numbering generator (apps/card_designs/numbering.py), with the
// scheme the owner chose for the sample (decision 306 addendum 2): Tinkerspace's prefix plus a staff segment.
export const SAMPLE_NUMBER_PREFIX = "TNK";
export const SAMPLE_NUMBER_PATTERN = "{PREFIX}-STF-{SEQ:4}";
export const SAMPLE_NUMBER_SEQ = 7;
export const sampleCardNumber = () => renderPattern(SAMPLE_NUMBER_PATTERN, SAMPLE_NUMBER_PREFIX, SAMPLE_NUMBER_SEQ);

/** The owner's chosen sample holder (decision 306 addendum): his own name and public avatar. */
export function sampleHolder(): Record<string, string> {
  return {
    name: "Shaan Shoukath", // i18n-ignore: a person's name
    number: sampleCardNumber(), valid_until: t`While staff access lasts`, // holders_staff.py's own wording
    roles: t`Systems Engineer`, space: t`Tinkerspace`, organisation: t`SpaceWorks Labs`,
  };
}
export const SAMPLE_PHOTO = "/brand/sample/shaan-shoukath.webp";
/** The sample card's check QR (owner's choice): a well-known music video, not a real verify page. */
export const SAMPLE_QR_TARGET = "https://www.youtube.com/watch?v=dQw4w9WgXcQ";
/** Corner radius of the logo tile, in card millimetres. */
export const SAMPLE_LOGO_RADIUS_MM = 1.6;
