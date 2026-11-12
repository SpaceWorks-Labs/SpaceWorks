import "./animatedLogo.css";
import SpaceWorksLogo, { type SpaceWorksLogoProps } from "../SpaceWorksLogo";

/**
 * THE way to draw the Space Works mark in the product. At rest it is the static master; on hover and
 * keyboard focus the box plays its one-shot opening (1600 ms, the shared `boxOpen` artwork), then the
 * still mark returns. Tenant (makerspace) logos are never drawn with this and never animate. Every logo
 * placement must use this component (`logoPlacements.test.ts` fails otherwise); it never takes focus and
 * never changes the mark's size.
 */
export function AnimatedLogoMark(props: SpaceWorksLogoProps) {
  return <SpaceWorksLogo {...props} className={`${props.className ?? ""} ${props.oneColour ? "sw-logo-mono" : "sw-logo-colour"}`} animated />;
}

export default AnimatedLogoMark;
