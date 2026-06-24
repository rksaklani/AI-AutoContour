import { create } from "zustand";

export type ToolName =
  | "Pan"
  | "Zoom"
  | "WindowLevel"
  | "StackScroll"
  | "Rotate"
  | "Crosshairs"
  | "Length"
  | "Angle"
  | "RectangleROI"
  | "EllipticalROI"
  | "Bidirectional"
  | "Probe"
  | "ArrowAnnotate";

export type ViewName = "axial" | "coronal" | "sagittal" | "volume3d";

/** `null` => 2x2 MPR + 3D grid; a view name => that single pane full-size. */
export type ViewLayout = ViewName | null;

/** VolView-style left panel tabs. */
export type LeftTab = "data" | "annotations" | "rendering";

export interface WindowLevelPreset {
  name: string;
  windowWidth: number;
  windowCenter: number;
}

export const WL_PRESETS: WindowLevelPreset[] = [
  { name: "Default", windowWidth: 400, windowCenter: 40 },
  { name: "CT Lung", windowWidth: 1500, windowCenter: -600 },
  { name: "CT Bone", windowWidth: 2000, windowCenter: 300 },
  { name: "CT Soft Tissue", windowWidth: 400, windowCenter: 40 },
  { name: "CT Brain", windowWidth: 80, windowCenter: 40 },
];

const DEFAULT_SEG_OPACITY = 0.45;

interface ViewerState {
  activeTool: ToolName;
  singleView: ViewLayout;
  leftTab: LeftTab;
  rightDrawerOpen: boolean;
  show3D: boolean;
  wlPreset: WindowLevelPreset;
  invert: boolean;
  showSegmentations: boolean;
  showAnnotations: boolean;
  selectedFindingId: string | null;
  selectedSeriesId: string | null;
  /** Per-segmentation opacity 0..1 keyed by segmentation id. */
  segOpacity: Record<string, number>;
  /** Segmentation ids hidden individually (masks toggle still applies globally). */
  hiddenSegIds: Record<string, boolean>;
  /** Cornerstone segmentationId for the active AI labelmap (shared MPR + 3D). */
  labelmapSegId: string | null;
  resetNonce: number;
  screenshotNonce: number;
  zoomNonce: number;
  zoomDirection: "in" | "out";
  setActiveTool: (tool: ToolName) => void;
  setSingleView: (view: ViewLayout) => void;
  setLeftTab: (tab: LeftTab) => void;
  toggleRightDrawer: () => void;
  setRightDrawerOpen: (open: boolean) => void;
  setShow3D: (show: boolean) => void;
  setWlPreset: (preset: WindowLevelPreset) => void;
  setSelectedSeriesId: (id: string | null) => void;
  toggleInvert: () => void;
  toggleSegmentations: () => void;
  toggleAnnotations: () => void;
  selectFinding: (id: string | null) => void;
  setSegOpacity: (id: string, opacity: number) => void;
  toggleSegVisibility: (id: string) => void;
  initSegOpacities: (ids: string[]) => void;
  setLabelmapSegId: (id: string | null) => void;
  resetView: () => void;
  requestScreenshot: () => void;
  zoomIn: () => void;
  zoomOut: () => void;
  /** Restore persisted session fields (localStorage). */
  hydrateSession: (partial: Partial<ViewerState>) => void;
  /** Serializable subset for session persistence. */
  sessionSnapshot: () => Record<string, unknown>;
}

export const useViewerStore = create<ViewerState>((set, get) => ({
  activeTool: "WindowLevel",
  singleView: null,
  leftTab: "data",
  rightDrawerOpen: true,
  show3D: false,
  wlPreset: WL_PRESETS[0],
  invert: false,
  showSegmentations: true,
  showAnnotations: true,
  selectedFindingId: null,
  selectedSeriesId: null,
  segOpacity: {},
  hiddenSegIds: {},
  labelmapSegId: null,
  resetNonce: 0,
  screenshotNonce: 0,
  zoomNonce: 0,
  zoomDirection: "in",
  setActiveTool: (activeTool) => set({ activeTool }),
  setSingleView: (singleView) => set({ singleView }),
  setLeftTab: (leftTab) => set({ leftTab }),
  toggleRightDrawer: () => set((s) => ({ rightDrawerOpen: !s.rightDrawerOpen })),
  setRightDrawerOpen: (rightDrawerOpen) => set({ rightDrawerOpen }),
  setShow3D: (show3D) => set({ show3D }),
  setWlPreset: (wlPreset) => set({ wlPreset }),
  setSelectedSeriesId: (selectedSeriesId) => set({ selectedSeriesId }),
  toggleInvert: () => set((s) => ({ invert: !s.invert })),
  toggleSegmentations: () => set((s) => ({ showSegmentations: !s.showSegmentations })),
  toggleAnnotations: () => set((s) => ({ showAnnotations: !s.showAnnotations })),
  selectFinding: (selectedFindingId) => set({ selectedFindingId }),
  setSegOpacity: (id, opacity) =>
    set((s) => ({ segOpacity: { ...s.segOpacity, [id]: opacity } })),
  toggleSegVisibility: (id) =>
    set((s) => ({
      hiddenSegIds: { ...s.hiddenSegIds, [id]: !s.hiddenSegIds[id] },
    })),
  initSegOpacities: (ids) =>
    set((s) => {
      const next = { ...s.segOpacity };
      ids.forEach((id) => {
        if (next[id] === undefined) next[id] = DEFAULT_SEG_OPACITY;
      });
      return { segOpacity: next };
    }),
  setLabelmapSegId: (labelmapSegId) => set({ labelmapSegId }),
  resetView: () => set((s) => ({ resetNonce: s.resetNonce + 1 })),
  requestScreenshot: () => set((s) => ({ screenshotNonce: s.screenshotNonce + 1 })),
  zoomIn: () =>
    set((s) => ({ zoomNonce: s.zoomNonce + 1, zoomDirection: "in" as const })),
  zoomOut: () =>
    set((s) => ({ zoomNonce: s.zoomNonce + 1, zoomDirection: "out" as const })),
  hydrateSession: (partial) => set(partial),
  sessionSnapshot: () => {
    const s = get();
    return {
      activeTool: s.activeTool,
      singleView: s.singleView,
      leftTab: s.leftTab,
      show3D: s.show3D,
      rightDrawerOpen: s.rightDrawerOpen,
      wlPreset: s.wlPreset,
      invert: s.invert,
      showSegmentations: s.showSegmentations,
      showAnnotations: s.showAnnotations,
      selectedSeriesId: s.selectedSeriesId,
      segOpacity: s.segOpacity,
      hiddenSegIds: s.hiddenSegIds,
    };
  },
}));
