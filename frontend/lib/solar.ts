/**
 * Solar position in the browser, so a judge can run a verification with no
 * backend at all.
 *
 * WHY THIS EXISTS RATHER THAN A CALL TO THE API
 *
 * The deployed demo at veritas-dmrv.vercel.app has no backend -- that is the
 * S6 exit criterion, and it is what makes the URL work for anyone. So an input a
 * judge can type into cannot be answered by the Python service that computes
 * solar positions server-side with pvlib. Either the console needs a backend,
 * or the browser needs the arithmetic.
 *
 * This is the NOAA Solar Calculator algorithm, which is the standard reference
 * implementation for this and is accurate to roughly a tenth of a degree for
 * dates within a few centuries of now.
 *
 * VALIDATED AGAINST pvlib, NOT AGAINST ITSELF. `frontend/e2e/solar.spec.ts`
 * runs all ten committed pvlib vectors through this code and asserts agreement
 * within a stated tolerance. Two independent implementations agreeing is the only
 * reason to believe a number shown to a judge, and the same argument as the
 * shadow-coherence work: two implementations of the same physics should not
 * share a bug.
 *
 * Note the below-horizon case: pvlib reports a defined azimuth for a sun 81
 * degrees UNDER the horizon, and so does NOAA, but both are conventions rather
 * than measurements there. The tolerance is looser below the horizon for that
 * reason, and the console never shows an azimuth for a sun that has set.
 */

export interface SolarPosition {
  /** Degrees clockwise from north. Undefined when the sun is below the horizon. */
  azimuthDeg: number;
  /** Degrees above the horizon. Negative when the sun has set. */
  elevationDeg: number;
  /** True when the sun is geometrically below the horizon. */
  belowHorizon: boolean;
  /** Solar noon for this longitude, in UTC. */
  solarNoonUtc: Date;
}

const RAD = Math.PI / 180;
const DEG = 180 / Math.PI;

/** Wrap into [0, 360). */
function wrap360(deg: number): number {
  return ((deg % 360) + 360) % 360;
}

/**
 * Solar position at an instant, for a location.
 *
 * @param latitude  degrees north, -90..90
 * @param longitude degrees east, -180..180
 * @param at        any Date; interpreted as an absolute instant
 */
export function solarPosition(latitude: number, longitude: number, at: Date): SolarPosition {
  if (!Number.isFinite(latitude) || latitude < -90 || latitude > 90) {
    throw new RangeError(`latitude out of range: ${latitude}`);
  }
  if (!Number.isFinite(longitude) || longitude < -180 || longitude > 180) {
    throw new RangeError(`longitude out of range: ${longitude}`);
  }
  if (Number.isNaN(at.getTime())) {
    throw new RangeError("not a valid instant");
  }

  // --- Julian day, and the century since J2000.0 --------------------------- //
  const jd = at.getTime() / 86400000 + 2440587.5;
  const t = (jd - 2451545.0) / 36525.0;

  // --- Geometric mean longitude and anomaly of the sun -------------------- //
  const l0 = wrap360(280.46646 + t * (36000.76983 + t * 0.0003032));
  const m = 357.52911 + t * (35999.05029 - 0.0001537 * t);
  const e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t);

  // --- Equation of centre, and the sun's true and apparent longitude ------- //
  const c =
    Math.sin(m * RAD) *
    (1.914602 - t * (0.004817 + 0.000014 * t)) +
    Math.sin(2 * m * RAD) * (0.019993 - 0.000101 * t) +
    Math.sin(3 * m * RAD) * 0.000289;

  const trueLong = l0 + c;
  const omega = 125.04 - 1934.136 * t;
  const appLong = trueLong - 0.00569 - 0.00478 * Math.sin(omega * RAD);

  // --- Obliquity of the ecliptic, corrected ------------------------------- //
  const seconds = 21.448 - t * (46.815 + t * (0.00059 - t * 0.001813));
  const e0 = 23.0 + (26.0 + seconds / 60.0) / 60.0;
  const obliquity = e0 + 0.00256 * Math.cos(omega * RAD);

  // --- Declination and the equation of time ------------------------------- //
  const declination =
    Math.asin(Math.sin(obliquity * RAD) * Math.sin(appLong * RAD)) * DEG;

  const y = Math.tan((obliquity / 2) * RAD) ** 2;
  const eqTime =
    4 *
    DEG *
    (y * Math.sin(2 * l0 * RAD) -
      2 * e * Math.sin(m * RAD) +
      4 * e * y * Math.sin(m * RAD) * Math.cos(2 * l0 * RAD) -
      0.5 * y * y * Math.sin(4 * l0 * RAD) -
      1.25 * e * e * Math.sin(2 * m * RAD));

  // --- True solar time, hour angle, then the angles themselves ------------- //
  const minutesUtc =
    at.getUTCHours() * 60 + at.getUTCMinutes() + at.getUTCSeconds() / 60;
  const trueSolarTime = (minutesUtc + eqTime + 4 * longitude + 1440) % 1440;
  let hourAngle = trueSolarTime / 4 - 180;
  if (hourAngle < -180) hourAngle += 360;

  const latRad = latitude * RAD;
  const decRad = declination * RAD;
  const haRad = hourAngle * RAD;

  const cosZenith =
    Math.sin(latRad) * Math.sin(decRad) +
    Math.cos(latRad) * Math.cos(decRad) * Math.cos(haRad);
  // Clamped: a float above 1 produces NaN from acos, and NaN in a verdict shown
  // to a judge is the worst possible output.
  const zenith = Math.acos(Math.min(1, Math.max(-1, cosZenith)));
  const elevation = 90 - zenith * DEG;

  // Solar noon, when the true solar time is 12:00.
  const solarNoonUtc = new Date(
    at.getTime() + (720 - 4 * longitude - eqTime) * 60000
  );

  if (elevation < 0) {
    return {
      azimuthDeg: NaN,
      elevationDeg: elevation,
      belowHorizon: true,
      solarNoonUtc,
    };
  }

  let azimuth: number;
  const sinZenith = Math.sin(zenith);
  if (Math.abs(sinZenith) < 1e-9) {
    // The sun is at the zenith, so azimuth is genuinely undefined. Returning a
    // number here would be inventing a precision the geometry does not have.
    azimuth = NaN;
  } else {
    const cosAz = (Math.sin(latRad) * Math.cos(zenith) - Math.sin(decRad)) / (
      Math.cos(latRad) * sinZenith
    );
    const base = Math.acos(Math.min(1, Math.max(-1, cosAz))) * DEG;
    azimuth = hourAngle > 0 ? wrap360(base + 180) : wrap360(540 - base);
  }

  return { azimuthDeg: azimuth, elevationDeg: elevation, belowHorizon: false, solarNoonUtc };
}

/** The bearing a shadow must point, if the geometry is well posed. */
export function expectedShadowAzimuth(sunAzimuthDeg: number): number {
  return wrap360(sunAzimuthDeg + 180);
}

/** The smallest angle between two bearings, in [0, 180]. */
export function angularSeparation(a: number, b: number): number {
  const d = Math.abs(wrap360(a - b));
  return d > 180 ? 360 - d : d;
}
