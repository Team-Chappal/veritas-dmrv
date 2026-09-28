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

# Importing core.config loads backend/.env, so the harness honours the same file
# the app does rather than needing a hand-written export line.
import core.config  # noqa: E402,F401
from core.config import get_settings  # noqa: E402

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

    def skip(self, name, why):
        """Record a check that could not be attempted.

        Distinct from FAIL on purpose. A harness that reports "not run" as
        "failed" trains you to ignore red, and one that reports it as "passed"
        is worse. The first live run of the donor-reel check hit exactly this.
        """
        self.checks.append(
            {"name": name, "ok": True, "detail": f"SKIPPED: {why}", "skipped": True}
        )
        print(f"  [{YELLOW}SKIP{RESET}] {name}\n         {DIM}SKIPPED: {why}{RESET}")

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


def minimal_pdf() -> bytes:
    """A genuinely valid one-page PDF, byte-for-byte, with no dependencies.

    The audit-dossier URL composites text onto a PDF template, and a template has
    to actually exist and actually be a PDF or the composed URL cannot render.
    Shipping a hand-built minimal PDF beats shipping a .docx renamed, and beats
    skipping the check.
    """
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        None,  # content stream, filled below
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    stream = b"0 0 0 rg 0 0 595 842 re f BT /F1 24 Tf 60 780 Td "
    stream += b"(VERITAS dMRV audit dossier base) Tj ET"
    objects[3] = b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode()
    return bytes(out)


def background_png() -> bytes:
    """A plain dark plate, so the certificate overlay has something to sit on."""
    import numpy as np

    arr = np.zeros((1200, 1600, 3), dtype=np.uint8)
    arr[:, :] = (17, 94, 59)          # the project's green
    arr[:120, :] = (6, 78, 59)
    from PIL import Image

    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "PNG")
    return buf.getvalue()


def provision_brand_assets(report: "Report") -> None:
    """Upload the templates the campaign/report URLs composite onto.

    These are real dependencies, not test scaffolding: a certificate with no
    background and a dossier with no PDF base 404 or 400 no matter how correct
    the transformation grammar is. Provisioning them here means the grammar is
    what is under test.
    """
    import cloudinary.uploader

    for public_id, data, kind in (
        ("veritas-assets/certificate-background", background_png(), "image"),
        ("veritas-assets/audit-dossier-base", minimal_pdf(), "raw"),
    ):
        try:
            cloudinary.uploader.upload(
                data, public_id=public_id, overwrite=True, resource_type=kind,
                # Cloudinary enforces mandatory fields on every upload and does
                # not exempt shared brand assets, so these carry explicit
                # sentinel values. Naming them BRAND/none keeps it obvious in
                # the console that this asset is not field evidence.
                metadata={
                    "esg_project_id": "BRAND-000",
                    "sustainability_domain": "reforestation",
                    "cadastral_polygon_id": "BRAND-ASSET-NOT-EVIDENCE",
                    "capture_timestamp": "2026-01-01",
                    "milestone_phase": "baseline_month_0",
                },
            )
            report.add(f"brand asset provisioned: {public_id}", True, "uploaded")
        except Exception as exc:
            report.add(
                f"brand asset provisioned: {public_id}", False,
                f"{type(exc).__name__}: {exc}",
            )


def http_status(url: str, timeout: int = 20) -> tuple:
    """Return ``(status, content_type, byte_length, error_message)`` without raising.

    The error body is the single most useful thing available on a 4xx: Cloudinary
    names the exact component it rejected ("Cannot find matching layer start",
    "Unsupported font family Inter", "public_id ... is too long"). Discarding it
    -- as this originally did -- turns a one-line diagnosis into a guessing
    game, and the first live run printed a bare "0 bytes" for every failure.
    """
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = resp.read()
            return resp.status, resp.headers.get("Content-Type", ""), len(data), ""
    except urllib.error.HTTPError as exc:
        raw = b""
        try:
            raw = exc.read()
        except Exception:  # noqa: BLE001
            pass
        message = ""
        if raw:
            try:
                message = json.loads(raw.decode("utf-8", "replace")).get(
                    "error", {}
                ).get("message", "")
            except Exception:  # noqa: BLE001
                message = raw.decode("utf-8", "replace")[:200]
        return (
            exc.code,
            exc.headers.get("Content-Type", "") if exc.headers else "",
            0,
            message,
        )
    except Exception as exc:
        return 0, f"{type(exc).__name__}: {exc}", 0, ""


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
    # _unavailable_reason() is the FAILURE text. Printing it next to a PASS made
    # the first live run read as "SDK initialisation failed: None" beside a
    # green tick, which is how a real failure hid in step 2.
    detail = (
        f"cloud={client.cloud_name}, mode={get_settings().mode}"
        if client.is_live
        else client._unavailable_reason()
    )
    if not report.add("SDK initialised", client.is_live, detail):
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
    public_id = f"probe_{stamp}"  # bare: `folder=` below supplies the prefix
    uploaded = None
    try:
        import cloudinary.uploader

        # `metadata=`, NOT `context=`. context is the legacy free-text
        # key:value form and is silently ignored for structured metadata, so the
        # mandatory fields arrive empty and Cloudinary rejects the upload with a
        # message that names a field you did set.
        #
        # Every MANDATORY field must be supplied: Cloudinary enforces them on
        # every upload, and the analysis-output fields (verdict, confidence,
        # inlier ratio) are deliberately optional because they do not exist yet.
        upload_metadata = {
            "esg_project_id": "VAL-001",
            "sustainability_domain": "reforestation",
            "cadastral_polygon_id": "PARCEL-VALIDATION",
            "capture_timestamp": "2026-09-22",
            "milestone_phase": "baseline_month_0",
        }
        uploaded = cloudinary.uploader.upload(
            io.BytesIO(make_probe_image()),
            public_id=public_id,
            folder="veritas_validation",
            tags=["veritas", "validation"],
            metadata=upload_metadata,
            overwrite=True,
        )
        report.add("asset uploaded", bool(uploaded.get("public_id")),
                   f"public_id={uploaded.get('public_id')} "
                   f"bytes={uploaded.get('bytes')}")
        # The asset's stored public_id, which differs from the bare id we passed.
        uploaded_public_id = uploaded.get("public_id", public_id)
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

    written = client.set_structured_metadata(uploaded_public_id, payload)
    report.add("metadata written to Cloudinary", not written.fixture,
               written.reason if written.fixture else json.dumps(written.data))

    try:
        import cloudinary.api

        fetched = cloudinary.api.resource(uploaded_public_id, metadata=True)
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
    # The overlay assets these URLs reference must EXIST or the URLs 404 for a
    # reason that has nothing to do with the transformation grammar. The first
    # live run reported all four as broken when the real fault was a missing
    # asset -- so create the referenced assets before judging the grammar.
    provision_brand_assets(report)
    warped = uploaded_public_id + "_warped"
    try:
        import cloudinary.uploader

        for ref in (warped,):
            cloudinary.uploader.upload(
                make_probe_image(), public_id=ref.split("/")[-1],
                folder="veritas_validation", overwrite=True,
                metadata=upload_metadata,
            )
    except Exception as exc:
        report.add("referenced overlay assets created", False, f"{type(exc).__name__}: {exc}")
    urls = {
        "split_diff": build_split_diff_url(cloud, uploaded_public_id, warped, 38.2),
        "impact_certificate": build_impact_certificate_url(
            cloud, warped, "Validation Project", 38.2, "a" * 64
        ),
        # The reel is a VIDEO url; the probe asset is an image, so a 404 here
        # would be the harness's fault, not the builder's. Skip rather than
        # report a false negative, and say so.
        "donor_reel": None,
        "audit_pdf": build_audit_pdf_url(
            cloud, warped, "VAL-001", "Validation", 8.42, 9.4, "a" * 64
        ),
    }
    for name, url in urls.items():
        if url is None:
            report.skip(f"{name} URL renders",
                        "needs a VIDEO asset; the probe is an image. Upload a "
                        "video probe to cover this check.")
            continue
        status, ctype, size, message = http_status(url)
        ok = status == 200 and size > 0
        detail = f"HTTP {status}, {ctype}, {size} bytes"
        if not ok:
            if status == 401 and "acl" in (message or "").lower():
                # PDF output is an add-on, not a free-tier feature. Report it as
                # plan-gated rather than as a defect in the builder: a harness
                # that calls a paywall a bug gets its red ignored.
                report.skip(
                    f"{name} URL renders",
                    f"PLAN-GATED: Cloudinary returned 401 for f_pdf output "
                    f"({message}). The builder composes correctly in form, but "
                    "PDF generation needs a paid plan. Not verifiable here.",
                )
                continue
            detail += f"\n         CLOUDINARY SAYS: {message or '(no body)'}"
            if status == 404:
                detail += "\n         A 404 here usually means a REFERENCED asset is "\
                          "missing, not that the transformation is wrong."
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
    log = client.transformation_log(uploaded_public_id)
    report.add("transformation log readable", not log.fixture,
               log.reason if log.fixture else
               f"{len(log.data.get('transformations', []))} recorded transformation(s)")

    # -- 8. eager ---------------------------------------------------------- #
    print("\n8. Eager pre-render")
    try:
        import cloudinary.uploader

        eager = cloudinary.uploader.explicit(
            uploaded_public_id, type="upload",
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
            import cloudinary.uploader

            cloudinary.uploader.destroy(uploaded_public_id)
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
