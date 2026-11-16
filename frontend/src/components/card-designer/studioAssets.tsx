// Where the studio's images come from. Card designs upload to and read from the card-design asset routes
// (the default); a certificate supplies its own, because its artwork lives in the certificate resource store.
import { createContext, useContext } from "react";

export type UploadedAsset = { asset_id: string; mean_colour: string };
export type StudioAssets = {
  upload: (kind: "background" | "watermark" | "image", file: File) => Promise<UploadedAsset>;
  /** An object URL for the asset's bytes. */
  load: (assetId: string) => Promise<string>;
};

const Context = createContext<StudioAssets | null>(null);
export const StudioAssetsProvider = Context.Provider;
export const useStudioAssets = () => useContext(Context);
