/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
  readonly VITE_WS_BASE_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module "@cornerstonejs/dicom-image-loader";
declare module "@cornerstonejs/streaming-image-volume-loader";
declare module "dicom-parser";
