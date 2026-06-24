import { VolumeViewport } from "@/features/viewer/VolumeViewport";

/**
 * Full-screen 3D volume rendering panel.
 */
export function VolumePanel({ imageUrls }: { imageUrls: string[] }) {
  return (
    <div className="viewer-single-host">
      <div className="viewer-single-frame">
        <VolumeViewport imageUrls={imageUrls} showPresetBar />
      </div>
    </div>
  );
}
