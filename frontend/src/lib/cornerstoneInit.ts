/**
 * Cornerstone3D initialization.
 *
 * Initializes the rendering core and the DICOM image loader exactly once.
 *
 * IMPORTANT (v1.x API): `@cornerstonejs/dicom-image-loader` v1.x does NOT export an
 * `init()` helper. Image loaders are registered as a side effect of assigning
 * `external.cornerstone` (its setter calls `wadouri.register()` / `wadors.register()`),
 * and `external.dicomParser` must be provided or the loader throws at decode time.
 * The previous `loader.init?.()` call silently no-opped, so no `wadouri:` loader was
 * ever registered and every viewport failed with
 * "loadImageFromImageLoader: no image loader for imageId".
 *
 * Kept defensive: any environment-specific failure is caught so the rest of the app
 * (findings, reports, overlays) keeps working in overlay-only mode.
 */
import * as cornerstone from "@cornerstonejs/core";
import * as dicomImageLoader from "@cornerstonejs/dicom-image-loader";
import { cornerstoneStreamingImageVolumeLoader } from "@cornerstonejs/streaming-image-volume-loader";
import * as csTools from "@cornerstonejs/tools";
import dicomParser from "dicom-parser";

/** Scheme prefix for volume ids handled by the streaming image volume loader. */
export const VOLUME_LOADER_SCHEME = "cornerstoneStreamingImageVolume";

interface DicomImageLoader {
  external: { cornerstone: unknown; dicomParser: unknown };
  configure: (opts: Record<string, unknown>) => void;
  webWorkerManager?: { initialize?: (opts: Record<string, unknown>) => void };
}

let initialized = false;
let initPromise: Promise<boolean> | null = null;

async function doInit(): Promise<boolean> {
  try {
    await cornerstone.init();

    // `init()` unconditionally enables SharedArrayBuffer, but SAB is only
    // available on cross-origin-isolated pages (COOP/COEP). Without it the
    // streaming volume loader throws. Disable it so volumes use plain
    // ArrayBuffers (slightly slower, but works everywhere / cross-origin).
    (cornerstone as unknown as { setUseSharedArrayBuffer: (v: boolean) => void }).setUseSharedArrayBuffer(
      false,
    );

    const loader = dicomImageLoader as unknown as DicomImageLoader;

    // dicomParser must be wired before any image is loaded.
    loader.external.dicomParser = dicomParser;

    loader.configure({
      useWebWorkers: true,
      decodeConfig: {
        convertFloatPixelDataToInt: false,
        use16BitDataType: true,
      },
    });

    // Assigning cornerstone triggers registration of the wadouri/wadors/dicomfile
    // image loaders (and their metadata providers) against the core.
    loader.external.cornerstone = cornerstone;

    loader.webWorkerManager?.initialize?.({
      maxWebWorkers: Math.min(navigator.hardwareConcurrency || 1, 4),
      startWebWorkersOnDemand: true,
      taskConfiguration: {
        decodeTask: { initializeCodecsOnStartup: false, strict: false },
      },
    });

    // Register the streaming volume loader so we can build 3D volumes from a
    // slice stack and drive true axial/coronal/sagittal MPR reformatting.
    cornerstone.volumeLoader.registerVolumeLoader(
      VOLUME_LOADER_SCHEME,
      cornerstoneStreamingImageVolumeLoader as never,
    );
    cornerstone.volumeLoader.registerUnknownVolumeLoader(
      cornerstoneStreamingImageVolumeLoader as never,
    );

    // Initialize the tools layer and register the interaction/measurement tools
    // we use (pan/zoom/rotate/window-level/scroll + measurement + annotation).
    // The polyseg WASM dependency that previously broke the build is stubbed out
    // via a Vite alias (see vite.config.ts + src/lib/polyseg-stub.ts).
    await csTools.init();
    const tools = [
      csTools.PanTool,
      csTools.ZoomTool,
      csTools.WindowLevelTool,
      csTools.StackScrollTool,
      csTools.StackScrollMouseWheelTool,
      csTools.TrackballRotateTool,
      csTools.VolumeRotateMouseWheelTool,
      csTools.PlanarRotateTool,
      csTools.CrosshairsTool,
      csTools.ReferenceLinesTool,
      csTools.LengthTool,
      csTools.AngleTool,
      csTools.RectangleROITool,
      csTools.EllipticalROITool,
      csTools.ProbeTool,
      csTools.BidirectionalTool,
      csTools.ArrowAnnotateTool,
      // Required for rendering AI labelmap segmentations across MPR + 3D viewports.
      csTools.SegmentationDisplayTool,
    ];
    tools.forEach((T) => {
      try {
        csTools.addTool(T);
      } catch {
        /* already registered */
      }
    });

    initialized = true;
    return true;
  } catch (err) {
    // eslint-disable-next-line no-console
    console.warn("Cornerstone3D init failed; viewer will run in overlay-only mode.", err);
    return false;
  }
}

export function initCornerstone(): Promise<boolean> {
  if (initialized) return Promise.resolve(true);
  initPromise = initPromise ?? doInit();
  return initPromise;
}

export function isCornerstoneReady(): boolean {
  return initialized;
}

/** Build a cornerstone image id from a presigned URL (WADO-URI scheme). */
export function imageIdFromUrl(url: string): string {
  return `wadouri:${url}`;
}
