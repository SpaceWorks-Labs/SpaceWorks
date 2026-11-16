// Lane G installs these browser-only lazy dependencies and their license notices.
// Vendor output is treated as untrusted and checked against our own bounds.
declare module "three";
declare module "three/addons/loaders/STLLoader.js";
declare module "three/addons/loaders/OBJLoader.js";
declare module "three/addons/loaders/3MFLoader.js";
declare module "three/addons/controls/OrbitControls.js";
declare module "occt-import-js";
declare module "occt-import-js/dist/occt-import-js.wasm?url" { const url: string; export default url; }
declare module "linkedom/worker";
declare module "fflate";
declare module "@tracespace/core";
