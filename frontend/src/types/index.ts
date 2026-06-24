export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  role: string | null;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface Instance {
  id: string;
  sop_instance_uid: string | null;
  instance_number: number | null;
  object_key: string;
  url: string | null;
}

export interface Series {
  id: string;
  series_instance_uid: string | null;
  modality: string;
  series_number: number | null;
  description: string;
  instance_count: number;
  instances: Instance[];
}

export interface Study {
  id: string;
  patient_name: string;
  patient_id: string;
  patient_sex: string;
  patient_age: string;
  modality: string;
  body_part: string;
  description: string;
  status: string;
  study_date: string | null;
  created_at: string;
  series: Series[];
}

export interface StudyListItem {
  id: string;
  patient_name: string;
  modality: string;
  body_part: string;
  description: string;
  status: string;
  created_at: string;
}

export interface Job {
  id: string;
  study_id: string;
  status: string;
  stage: string;
  progress: number;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface Finding {
  id: string;
  study_id: string;
  segmentation_id: string | null;
  label: string;
  location: string;
  confidence: number;
  volume_cc: number | null;
  severity: "low" | "moderate" | "high" | string;
  bbox: Record<string, number>;
  description: string;
  recommendation: string;
}

export interface Segmentation {
  id: string;
  study_id: string;
  label: string;
  structure_type: string;
  mask_object_key: string | null;
  color: string;
  stats: Record<string, number>;
  mask_url: string | null;
}

export interface ContourPolygon {
  z_mm: number;
  points: number[][];
}

export interface RoiOverlay {
  segmentation_id: string | null;
  label: string;
  color: string;
  structure_type: string;
  contours: ContourPolygon[];
  bbox: Record<string, number>;
  mask_url: string | null;
}

export interface StudyOverlay {
  slice_z_mm: number[];
  rois: RoiOverlay[];
}

export interface Annotation {
  id: string;
  study_id: string;
  finding_id: string | null;
  kind: string;
  geometry: Record<string, number>;
  text: string;
  ai_generated: boolean;
}

export interface Report {
  id: string;
  study_id: string;
  status: string;
  summary: Record<string, unknown>;
  created_at: string;
  formats: string[];
}

export interface JobProgressEvent {
  job_id?: string;
  study_id?: string;
  stage: string;
  progress: number;
  status: string;
  error?: string;
  type?: string;
}
