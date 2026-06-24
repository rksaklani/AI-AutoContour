/**
 * Stub for `@icr/polyseg-wasm`.
 *
 * `@cornerstonejs/tools` statically pulls in a polyseg WASM worker (used only for
 * converting surface/contour representations into labelmap segmentations). That
 * `.wasm` import cannot be bundled by Vite/Rollup and breaks the production build.
 *
 * We don't use polyseg surface conversion, so we alias the package to this no-op
 * stub (see vite.config.ts). All other Cornerstone3D tools (pan/zoom/rotate/
 * window-level/scroll/measurement) work normally.
 */
export default class ICRPolySeg {
  async initialize(): Promise<void> {
    /* no-op */
  }
  convertContourRoiToSurface(): never {
    throw new Error("polyseg surface conversion is not available in this build");
  }
  convertLabelmapToSurface(): never {
    throw new Error("polyseg surface conversion is not available in this build");
  }
}
