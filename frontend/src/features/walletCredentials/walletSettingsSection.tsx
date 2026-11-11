import { t } from "@lingui/core/macro";
import type { SettingsLayoutSection } from "../../components/layouts";
import { capabilityOn } from "../../lib/features";
import { WalletCredentialsCard } from "./WalletCredentialsCard";

type Space = { id: number; enabled_modules?: string[]; enabled_features?: string[] };

/** The wallet switches that sign passes with the space's credentials: membership cards and event passes. */
export const WALLET_SWITCHES = ["membership.wallet_passes", "events.wallet_passes"] as const;

/**
 * ID-11: Settings › Wallet passes. One set of credentials signs both membership and event passes, so the
 * card is its own section, present for the Space Manager while either switch is on (absent otherwise, #183B).
 */
export function walletSettingsSections(space: Space, canManageMakerspace: boolean): SettingsLayoutSection[] {
  if (!canManageMakerspace || !WALLET_SWITCHES.some(key => capabilityOn(space, key))) return [];
  return [{ id: "wallet", title: t`Wallet passes`,
    rows: <WalletCredentialsCard key={space.id} scope={{ kind: "space", makerspaceId: space.id }} /> }];
}
