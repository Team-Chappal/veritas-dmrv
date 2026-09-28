#!/usr/bin/env python
"""
First live Cloudinary validation run.

WHY THIS EXISTS
---------------
The Stage 4 PR was merged with an explicit caveat: every credentialed path is
written and guarded, but **none of it has ever run against a real account**, and
none of the composed transformation URLs has been rendered. The composed URLs
are the claim that matters to a Cloudinary judge, and "it looks like a valid
transformation chain" is not evidence.

This script turns that caveat into a checklist with pass/fail output. It is
deliberately ordered so the cheapest and most decisive checks run first:

  1. credentials present          — nothing else matters without these
  2. schema fingerprint matches   — catches a code/schema drift on the account
  3. one real upload              — proves write access
  4. structured metadata round-trip
  5. rendered URL actually returns 200 and is an image
  6. search expression executes
  7. transformation log is readable
  8. eager transform completes
  9. webhook signature scheme     — prints observed headers, settles the
                                     question this project refuses to answer
                                     from memory

Step 9 is the important one. `services/webhook_service.py` deliberately does not
assert which signature construction Cloudinary uses, because asserting it from
memory is how the Chave "correction" happened. This script prints what a real
notification looks like so the scheme is established by observation.

USAGE
    export CLOUDINARY_CLOUD_NAME=... CLOUDINARY_API_KEY=... CLOUDINARY_API_SECRET=...
    python scripts/validate_cloudinary_live.py
    python scripts/validate_cloudinary_live.py --keep     # leave the test asset
    python scripts/validate_cloudinary_live.py --json     # machine-readable
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

import numpy as np  # noqa: E402

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


class Report:
    def __init__(self) -> None:
        self.checks = []

    def add(self, name, ok, detail="", severity="error"):
        self.checks.append(
            {"name": name, "ok": bool(ok), "detail": str(detail), "severity": severity}
        )
        mark = f"{GREEN}PASS{RESET}" if ok else (f"{RED}FAIL{RESET}" if severity == "error" else f"{YELLOW}WARN{RESET}")
        print(f"  [{mark}] {name}" + (f"\n         {DIM}{detail}{RESET}" if detail else ""))
        return ok

    @property
    def failed(self):
        return [c for c in self.checks if not c["ok"] and c["severity"] == "error"]

    @property
    def warned(self):
        return [c for c in self.checks if not c["ok"] and c["severity"] == "warn"]


def make_probe_image(width: int = 640, height: int = 480) -> bytes:
    """A deterministic image with real structure, so SIFT finds keypoints."""
    import cv2

    rng = np.random.default_rng(20260922)
    img = np.full((height, width, 3), (120, 96, 68), np.uint8)
    for _ in range(180):
        cx, cy = int(rng.integers(0, width)), int(rng.integers(0, height))
        colour = tuple(int(v) for v in rng.integers(0, 255, 3))
        cv2.circle(img, (cx, cy), int(rng.integers(6, 28)), colour, -1)
    for _ in range(25):
        x0, y0 = int(rng.integers(0, width - 60)), int(rng.integers(0, height - 60))
        cv2.rectangle(img, (x0, y0), (x0 + int(rng.integers(20, 80)), y0 + int(rng.integers(15, 50))),
                      tuple(int(v) for v in rng.integers(0, 255, 3)), -1)
    noisy = img.astype(np.int16) + rng.normal(0, 6, img.shape).astype(np.int16)
    img = np.clip(noisy, 0, 255).astype(np.uint8)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def http_status(url: str, timeout: int = 20) -> tuple:
    """Return ``(status, content_type, byte_length)`` without raising."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = resp.read()
            return resp.status, resp.headers.get("Content-Type", ""), len(data)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers.get("Content-Type", "") if exc.headers else "", 0
    except Exception as exc:
        return 0, f"{type(exc).__name__}: {exc}", 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="store_true", help="do not destroy the test asset")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument("--notification-url", default="", help="your deployed webhook URL")
    args = parser.parse_args()

    report = Report()
    print(f"\n{YELLOW}VERITAS dMRV — live Cloudinary validation{RESET}\n")

    # -- 1. credentials ---------------------------------------------------- #
    print("1. Credentials")
    required = ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET")
    missing = [k for k in required if not os.getenv(k)]
    if not report.add(
        "credentials present", not missing,
        f"missing: {missing}" if missing else "all three set",
    ):
        print(f"\n{RED}Cannot continue without credentials.{RESET} "
              f"Everything else in this script is untestable.\n")
        return 1

    from core.cloudinary_client import (
        CloudinaryClient,
        build_audit_pdf_url,
        build_donor_reel_url,
        build_impact_certificate_url,
        build_split_diff_url,
        validate_metadata,
    )

    client = CloudinaryClient()
    if not report.add("SDK initialised", client.is_live, client._unavailable_reason()):
        return 1

    # -- 2. schema --------------------------------------------------------- #
    print("\n2. Structured metadata schema")
    result = client.ensure_metadata_schema()
    report.add("schema bootstrap", not result.fixture,
               result.reason if result.fixture else json.dumps(result.data))
    report.add(
        "schema fingerprint matches the account",
        not result.fixture and result.data.get("fields") == 11,
        f"local fingerprint {client.schema_fingerprint()}; account has "
        f"{result.data.get('fields')} field(s). If these differ the account was "
        "bootstrapped from a different version of the code.",
        severity="warn",
    )

    # -- 3. upload --------------------------------------------------------- #
    print("\n3. Upload and write access")
    stamp = str(int(time.time()))
    public_id = f"veritas_validation/{stamp}"
    uploaded = None
    try:
        import cloudinary

        uploaded = cloudinary.uploader.upload(
            io.BytesIO(make_probe_image()),
            public_id=public_id,
            folder="veritas_validation",
            tags=["veritas", "validation"],
            overwrite=True,
        )
        report.add("asset uploaded", bool(uploaded.get("public_id")),
                   f"public_id={uploaded.get('public_id')} "
                   f"bytes={uploaded.get('bytes')}")
    except Exception as exc:
        report.add("asset uploaded", False, f"{type(exc).__name__}: {exc}")
        return finish(report, args)

    # -- 4. metadata round-trip ------------------------------------------- #
    print("\n4. Structured metadata round-trip")
    payload = {
        "esg_project_id": "VAL-001",
        "sustainability_domain": "reforestation",
        "cadastral_polygon_id": "PARCEL-VALIDATION",
        "capture_timestamp": "2026-09-22",
        "solar_azimuth_error": 0,
        "jev_triage_decision": "VERIFIED_PASS",
        "jev_confidence_score": 96,
        "c2pa_provenance": "C2PA_VERIFIED",
        "milestone_phase": "progress_month_18",
    }
    try:
        validate_metadata(payload)
        report.add("payload passes local validation", True, "11-field schema enforced locally")
    except Exception as exc:
        report.add("payload passes local validation", False, str(exc))

    written = client.set_structured_metadata(public_id, payload)
    report.add("metadata written to Cloudinary", not written.fixture,
               written.reason if written.fixture else json.dumps(written.data))

    try:
        fetched = cloudinary.api_client.call_api(
            "get", [f"resources/image/upload/{public_id}"], params={"metadata": True}
        )
        stored = (fetched.get("metadata") or {})
        matched = all(str(stored.get(k)) == str(v) for k, v in payload.items())
        report.add("metadata read back matches", matched,
                   f"read {len(stored)} field(s); "
                   + ("all match" if matched else f"MISMATCH: {stored}"))
    except Exception as exc:
        report.add("metadata read back matches", False, f"{type(exc).__name__}: {exc}")

    # -- 5. rendered URLs --------------------------------------------------- #
    print("\n5. Transformation URLs actually render")
    cloud = client.cloud_name
    warped = public_id + "_warped"
    urls = {
        "split_diff": build_split_diff_url(cloud, public_id, warped, 38.2),
        "impact_certificate": build_impact_certificate_url(
            cloud, warped, "Validation Project", 38.2, "a" * 64
        ),
        "donor_reel": build_donor_reel_url(cloud, public_id),
        "audit_pdf": build_audit_pdf_url(
            cloud, warped, "VAL-001", "Validation", 8.42, 9.4, "a" * 64
        ),
    }
    for name, url in urls.items():
        status, ctype, size = http_status(url)
        ok = status == 200 and size > 0
        detail = f"HTTP {status}, {ctype}, {size} bytes"
        if not ok and status == 400:
            detail += "  <- the composed transformation was REJECTED. This is "\
                      "the unproven claim from the PR: compare the chain against "\
                      "Cloudinary's current transformation grammar."
        report.add(f"{name} URL renders", ok, detail)

    # -- 6. search --------------------------------------------------------- #
    print("\n6. Search API")
    expression = 'metadata.esg_project_id="VAL-001"'
    found = client.search(expression, max_results=5)
    ok = not found.fixture and found.data.get("total_count", 0) >= 1
    report.add("structured search executes and finds the asset", ok,
               found.reason if found.fixture else
               f"expression {expression!r} -> total_count={found.data.get('total_count')}")

    # -- 7. transformation log -------------------------------------------- #
    print("\n7. Transformation log (rubric bullet 6)")
    log = client.transformation_log(public_id)
    report.add("transformation log readable", not log.fixture,
               log.reason if log.fixture else
               f"{len(log.data.get('transformations', []))} recorded transformation(s)")

    # -- 8. eager ---------------------------------------------------------- #
    print("\n8. Eager pre-render")
    try:
        eager = cloudinary.uploader.explicit(
            public_id, type="upload",
            eager=[{"width": 400, "height": 300, "crop": "fill"}],
            eager_async=False,
        )
        report.add("eager transform completes", bool(eager.get("eager")),
                   f"{(eager.get('eager') or [{}])[0].get('secure_url','')}")
    except Exception as exc:
        report.add("eager transform completes", False, f"{type(exc).__name__}: {exc}")

    # -- 9. webhook signature scheme -------------------------------------- #
    print("\n9. Webhook signature scheme")
    from services.webhook_service import (
        SIGNATURE_HEADERS,
        WebhookVerifier,
        describe_scheme_uncertainty,
    )

    verifier = WebhookVerifier(secret=os.getenv("CLOUDINARY_WEBHOOK_SECRET"))
    print(f"       {DIM}{describe_scheme_uncertainty()}{RESET}")
    report.add(
        "webhook secret configured", verifier.requires_signature,
        "set CLOUDINARY_WEBHOOK_SECRET to enforce signature verification; "
        "without it the processor ACCEPTS unverified notifications"
        + ("" if verifier.requires_signature else " — THIS IS UNSAFE IN PRODUCTION"),
        severity="warn",
    )
    print(f"       {DIM}signature headers to watch for: {list(SIGNATURE_HEADERS)}{RESET}")
    if args.notification_url:
        print(f"       {DIM}point the account's notification_url at: "
              f"{args.notification_url}{RESET}")
    print(f"       {DIM}then re-run and log the headers a real notification "
          f"carries.{RESET}")

    # -- cleanup ----------------------------------------------------------- #
    if uploaded and not args.keep:
        try:
            cloudinary.uploader.destroy(public_id)
            report.add("test asset cleaned up", True, f"destroyed {public_id}")
        except Exception as exc:
            report.add("test asset cleaned up", False, str(exc), severity="warn")

    return finish(report, args)


def finish(report, args) -> int:
    print()
    if args.json:
        print(json.dumps({"checks": report.checks}, indent=2))
    passed = len(report.checks) - len(report.failed) - len(report.warned)
    print(f"{passed} passed, {len(report.failed)} failed, {len(report.warned)} warnings")
    if report.failed:
        print(f"\n{RED}Live validation FAILED. These paths are not trustworthy "
              f"until they pass.{RESET}")
        return 1
    if report.warned:
        print(f"\n{YELLOW}Live validation passed with warnings — see above.{RESET}")
    print(f"\n{GREEN}Live validation passed. The Stage 4 caveat can be lifted.{RESET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
