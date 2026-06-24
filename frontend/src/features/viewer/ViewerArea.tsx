import { MprViewer } from "@/features/viewer/MprViewer";
import { VolumePanel } from "@/features/viewer/VolumePanel";
import { useViewerStore } from "@/store/viewerStore";
import type { Finding, StudyOverlay } from "@/types";

export function ViewerArea({
  imageUrls,
  findings,
  overlay,
}: {
  imageUrls: string[];
  findings: Finding[];
  overlay?: StudyOverlay;
}) {
  const show3D = useViewerStore((s) => s.show3D);

  return (
    <div className="flex min-w-0 flex-1 flex-col overflow-hidden bg-black">
      {show3D ? (
        <VolumePanel imageUrls={imageUrls} />
      ) : (
        <MprViewer imageUrls={imageUrls} findings={findings} overlay={overlay} />
      )}
    </div>
  );
}
