/**
 * Project timeline and summary shapes.
 *
 * The timeline's `gaps` array is the point of the component. A timeline that
 * shows only what was collected is a marketing graphic; one that shows what was
 * expected and missed is a verification tool. `coverage_pct` and
 * `longest_gap_months` are reported so a gap cannot be quietly reframed as a
 * short project.
 */

export type EpochStatus = "FULL" | "partial" | "missing" | (string & {});
export type GapSeverity = "partial" | "missing" | (string & {});

export interface TimelineEpoch {
  label: string;
  months_from_start: number;
  expected_date: string;
  expected_assets: number;
  observed_assets: number;
  verified_assets: number;
  quarantined_assets: number;
  mean_canopy_delta_pct: number;
  first_capture: string;
  last_capture: string;
  status: EpochStatus;
}

export interface TimelineGap {
  label: string;
  expected_date: string;
  expected_assets: number;
  observed_assets: number;
  shortfall: number;
  severity: GapSeverity;
}

export interface Timeline {
  project_id: string;
  start_date: string;
  end_date: string;
  total_assets: number;
  coverage_pct: number;
  status: string;
  longest_gap_months: number;
  epochs: TimelineEpoch[];
  gaps: TimelineGap[];
  notes: string;
}

export interface ProjectFacts {
  project_id: string;
  project_name: string;
  total_assets: number;
  verified_assets: number;
  quarantined_assets: number;
  review_assets: number;
  canopy_delta_pct: number;
  mean_inlier_ratio: number;
  estimated_tco2e_per_ha: number;
  sampling_error_pct: number;
  net_certified_tco2e: number;
  area_ha: number;
  domain?: string;
}

export interface ProjectSummary {
  project_id: string;
  project_name: string;
  facts: ProjectFacts;
  text: string;
  grounded: boolean;
  generator: string;
  llm_enhanced: boolean;
  note: string;
}
