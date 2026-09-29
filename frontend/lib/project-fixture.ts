/**
 * Bundled timeline and summary.
 *
 * THE TIMELINE HAS A REAL GAP IN IT, on purpose. A fixture where every epoch is
 * complete demonstrates nothing about the component's whole reason for existing,
 * which is showing that evidence is MISSING. The month-6 epoch is short by one
 * asset and the month-18 epoch was never captured at all.
 */

import type { ProjectSummary, Timeline } from "./project";

export const DEMO_TIMELINE: Timeline = {
  project_id: "KEN-008",
  start_date: "2025-03-15",
  end_date: "2026-09-20",
  total_assets: 148,
  // Deliberately not 100. A project with a gap is the normal case.
  coverage_pct: 66.7,
  status: "GAPS_DETECTED",
  longest_gap_months: 6,
  epochs: [
    {
      label: "baseline_month_0",
      months_from_start: 0,
      expected_date: "2025-03-15",
      expected_assets: 3,
      observed_assets: 3,
      verified_assets: 3,
      quarantined_assets: 0,
      mean_canopy_delta_pct: 0,
      first_capture: "2025-03-15",
      last_capture: "2025-03-16",
      status: "FULL",
    },
    {
      label: "progress_month_6",
      months_from_start: 6,
      expected_date: "2025-09-15",
      expected_assets: 3,
      observed_assets: 2,
      verified_assets: 2,
      quarantined_assets: 0,
      mean_canopy_delta_pct: 11.4,
      first_capture: "2025-09-14",
      last_capture: "2025-09-18",
      status: "partial",
    },
    {
      label: "progress_month_18",
      months_from_start: 18,
      // NEVER CAPTURED. The gap a reviewer most needs to see.
      expected_date: "2026-03-15",
      expected_assets: 3,
      observed_assets: 0,
      verified_assets: 0,
      quarantined_assets: 0,
      mean_canopy_delta_pct: 0,
      first_capture: "",
      last_capture: "",
      status: "missing",
    },
    {
      label: "certified_year_3",
      months_from_start: 36,
      expected_date: "2028-03-15",
      expected_assets: 3,
      observed_assets: 3,
      verified_assets: 2,
      quarantined_assets: 1,
      mean_canopy_delta_pct: 38.3,
      first_capture: "2026-09-19",
      last_capture: "2026-09-20",
      status: "FULL",
    },
  ],
  gaps: [
    {
      label: "progress_month_6",
      expected_date: "2025-09-15",
      expected_assets: 3,
      observed_assets: 2,
      shortfall: 1,
      severity: "partial",
    },
    {
      label: "progress_month_18",
      expected_date: "2026-03-15",
      expected_assets: 3,
      observed_assets: 0,
      shortfall: 3,
      severity: "missing",
    },
  ],
  notes:
    "Epochs are the reporting schedule, not the capture history. An epoch with " +
    "no captures is a GAP in the evidence, which is different from a project " +
    "that finished early.",
};

export const DEMO_SUMMARY: ProjectSummary = {
  project_id: "KEN-008",
  project_name: "Kilifi Creek Mangrove Restoration",
  grounded: true,
  generator: "template",
  llm_enhanced: false,
  note:
    "Every figure below is a measured fact. Prose is assembled from those " +
    "facts; no language model generated any of it.",
  facts: {
    project_id: "KEN-008",
    project_name: "Kilifi Creek Mangrove Restoration",
    total_assets: 148,
    verified_assets: 131,
    quarantined_assets: 5,
    review_assets: 12,
    canopy_delta_pct: 38.2,
    mean_inlier_ratio: 0.845,
    estimated_tco2e_per_ha: 8.42,
    sampling_error_pct: 8.7,
    // Equal to gross because 8.7% sampling error is BELOW the 15% VM0047
    // threshold. It looks like a missing multiplication; it is the rule.
    net_certified_tco2e: 8.42,
    area_ha: 14.5,
    domain: "mangrove_restoration",
  },
  text:
    "Kilifi Creek Mangrove Restoration holds 148 assets across a reporting " +
    "schedule, of which 131 verified and 5 were quarantined. Mean canopy " +
    "cover rose 38.2% against the baseline. Estimated carbon benefit is 8.42 " +
    "tCO2e per hectare with a sampling error of 8.7%, below the 15% VM0047 " +
    "threshold that would require a discount, so the net certified figure is " +
    "unchanged.",
};
