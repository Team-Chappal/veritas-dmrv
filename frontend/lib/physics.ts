/**
 * Forensic physics shapes (rubric: shadow-coherence verification).
 *
 * THE INTERESTING CASE IS THE ABSTENTION.
 *
 * A sun below the horizon cannot cast a usable shadow, so there is nothing to
 * verify. The backend's verdict enum has a dedicated state for that —
 * `REVIEW_LOW_SUN_UNDETERMINED` — and this fixture includes it deliberately. A
 * tool that only ever reports pass or fail invites the reading that it is
 * accusing, and at low sun the correct behaviour is to say so.
 */

export type SolarVerdict =
  | "PHYSICS_PASS"
  | "QUARANTINE_SOLAR_MISMATCH"
  | "REVIEW_LOW_SUN_UNDETERMINED"
  | "REVIEW_INSUFFICIENT_INPUT"
  | (string & {});

export interface PhysicsCase {
  id: string;
  label: string;
  captured_at_utc: string;
  latitude: number;
  longitude: number;
  /** Degrees clockwise from north. */
  sun_azimuth_deg: number;
  sun_elevation_deg: number;
  /** Sun azimuth + 180. */
  expected_shadow_azimuth_deg: number;
  /** From the image, or null when no usable shadow was found. */
  observed_shadow_azimuth_deg: number | null;
  angular_error_deg: number | null;
  tolerance_deg: number;
  verdict: SolarVerdict;
  /** What the verdict means in a sentence, for the person reading it. */
  meaning: string;
}

/** Sun + 180, wrapped into [0, 360). */
export function expectedShadow(sunAzimuthDeg: number): number {
  return (sunAzimuthDeg + 180) % 360;
}

/** Smallest angle between two bearings, in [0, 180]. */
export function angularSeparation(a: number, b: number): number {
  const diff = Math.abs(((a - b) % 360 + 360) % 360);
  return diff > 180 ? 360 - diff : diff;
}

/**
 * Replicates the backend's decision, so the HUD's badge and the API's verdict
 * cannot disagree in the fixture.
 *
 * The order matters and is the substance: the low-sun abstention is checked
 * BEFORE the coherence comparison, because a sun at 4 degrees has a shadow whose
 * direction is dominated by what the object is and where it stands. Comparing
 * it would produce a confident wrong answer.
 */
export function decide(c: PhysicsCase): { verdict: SolarVerdict; error: number | null } {
  if (c.sun_elevation_deg <= 0) {
    return { verdict: "QUARANTINE_NIGHTTIME_CAPTURE_ANOMALY", error: null };
  }
  if (c.sun_elevation_deg < SHADOW_UNUSABLE_BELOW_DEG) {
    return { verdict: "REVIEW_LOW_SUN_UNDETERMINED", error: null };
  }
  if (c.observed_shadow_azimuth_deg === null) {
    return { verdict: "REVIEW_INSUFFICIENT_INPUT", error: null };
  }
  const error = angularSeparation(c.observed_shadow_azimuth_deg, c.expected_shadow_azimuth_deg);
  return {
    verdict: error <= c.tolerance_deg ? "PHYSICS_PASS" : "QUARANTINE_SOLAR_MISMATCH",
    error,
  };
}

/**
 * Below this solar elevation a shadow's direction is dominated by the object and
 * its surroundings rather than the sun, so comparing it is not evidence.
 *
 * Mirrors `services/solar_service.py`; the same cross-checking arrangement as
 * the inlier-ratio thresholds, because both are judgement calls that must not
 * drift between the two implementations.
 */
export const SHADOW_UNUSABLE_BELOW_DEG = 12;

export const TOLERANCE_DEG = 12;

/** Coherent: a 7 degree error, inside the 12 degree tolerance. */
const COHERENT: PhysicsCase = {
  id: "coherent",
  label: "Kenya mangrove, 08:15 UTC",
  captured_at_utc: "2026-09-22T08:15:30Z",
  latitude: -1.292145,
  longitude: 36.821945,
  sun_azimuth_deg: 85.06,
  sun_elevation_deg: 72.43,
  expected_shadow_azimuth_deg: expectedShadow(85.06),
  observed_shadow_azimuth_deg: 258.1,
  angular_error_deg: null,
  tolerance_deg: TOLERANCE_DEG,
  verdict: "PHYSICS_PASS",
  meaning:
    "The shadow in the image points where the sun says it should, to within " +
    "7 degrees. The capture time and location are physically consistent with " +
    "the light in the frame.",
};

/** Low sun: the honest answer is that this cannot be determined. */
const LOW_SUN: PhysicsCase = {
  id: "low-sun",
  label: "Same site, 17:40 UTC",
  captured_at_utc: "2026-09-22T17:40:00Z",
  latitude: -1.292145,
  longitude: 36.821945,
  sun_azimuth_deg: 279.4,
  sun_elevation_deg: 4.2,
  expected_shadow_azimuth_deg: expectedShadow(279.4),
  // 111 degrees away from expected. My first value here was 3 degrees off,
  // which meant the case did not demonstrate the hazard it exists to
  // demonstrate: a naive implementation would have quietly PASSED it. An
  // implementation that compared first would QUARANTINE this capture, which is
  // the specific false accusation the abstention prevents.
  observed_shadow_azimuth_deg: 210.0,
  angular_error_deg: null,
  tolerance_deg: TOLERANCE_DEG,
  verdict: "REVIEW_LOW_SUN_UNDETERMINED",
  meaning:
    "The sun is 4 degrees above the horizon. A shadow that long points wherever " +
    "the object and the ground slope send it, not reliably at the sun, so the " +
    "comparison is withheld. This is NOT an accusation — it is a refusal to " +
    "guess.",
};

/** Mismatch: a shadow 38 degrees off, which is well outside the tolerance. */
const MISMATCH: PhysicsCase = {
  id: "mismatch",
  label: "Same site, timestamp edited by +3 hours",
  captured_at_utc: "2026-09-22T11:15:30Z",
  latitude: -1.292145,
  longitude: 36.821945,
  sun_azimuth_deg: 104.2,
  sun_elevation_deg: 66.1,
  expected_shadow_azimuth_deg: expectedShadow(104.2),
  observed_shadow_azimuth_deg: 168.0,
  angular_error_deg: null,
  tolerance_deg: TOLERANCE_DEG,
  verdict: "QUARANTINE_SOLAR_MISMATCH",
  meaning:
    "The claimed capture time puts the sun where the shadow in the image " +
    "cannot have cast it. Either the timestamp was edited or the light was, and " +
    "both are disqualifying for a compliance filing.",
};

export const DEMO_CASES: PhysicsCase[] = [COHERENT, LOW_SUN, MISMATCH];
