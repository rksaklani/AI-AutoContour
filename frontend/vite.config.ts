import { fileURLToPath, URL } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import topLevelAwait from "vite-plugin-top-level-await";
import wasm from "vite-plugin-wasm";

const r = (p: string) => fileURLToPath(new URL(p, import.meta.url));

export default defineConfig(({ mode }) => {
  const isProd = mode === "production";

  return {
    plugins: [react(), wasm(), topLevelAwait()],
    resolve: {
      alias: {
        "@": r("./src"),
        // Stub the polyseg WASM module: @cornerstonejs/tools statically imports a
        // WASM worker (surface<->labelmap conversion) that Vite/Rollup cannot bundle.
        // We don't use that feature, so alias it to a no-op stub.
        "@icr/polyseg-wasm": r("./src/lib/polyseg-stub.ts"),
        // The ESM builds of Cornerstone3D have hundreds of circular dependencies
        // that break Rollup chunk ordering ("Cannot access X before
        // initialization" at runtime). The official workaround is to use the UMD
        // builds for production bundling.
        // See https://github.com/cornerstonejs/cornerstone3D/issues/742
        ...(isProd
          ? {
              "@cornerstonejs/core": r("./node_modules/@cornerstonejs/core/dist/umd/index.js"),
              "@cornerstonejs/tools": r("./node_modules/@cornerstonejs/tools/dist/umd/index.js"),
              "@cornerstonejs/streaming-image-volume-loader": r(
                "./node_modules/@cornerstonejs/streaming-image-volume-loader/dist/umd/index.js",
              ),
            }
          : {}),
      },
    },
    server: {
      host: true,
      port: 5173,
    },
    // Cornerstone's dicom image loader ships wasm/worker assets; exclude from prebundling.
    optimizeDeps: {
      exclude: ["@cornerstonejs/dicom-image-loader"],
    },
    worker: {
      format: "es",
    },
  };
});
