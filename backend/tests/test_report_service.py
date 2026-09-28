"""
S5.6 — report assembly and the QR.

The QR tests decode with ``cv2.QRCodeDetector``: a different implementation from
the one that wrote the symbol. Checking that ``qr_matrix`` still contains the
string we passed in would only prove that a string is a string. Decoding an
independent reader proves the thing an auditor's phone will actually do.
"""

from __future__ import annotations

import base64
import io

import numpy as np
import pytest
from PIL import Image

from services.report_service import (
    QR_ERROR_CORRECTION,
    QR_MODULE_PIXELS,
    QR_QUIET_ZONE,
    ReportError,
    build_qr,
    build_report,
    content_address,
    qr_data_uri,
    qr_matrix,
    qr_svg,
    report_payload_url,
)

pytestmark = pytest.mark.tier5

APP_URL = "https://veritas.example"
PROJECT = "KEN-042"


def _decode(matrix: np.ndarray) -> str:
    """Decode a rasterised QR with an independent implementation."""
    import cv2

    # Upscale with NEAREST so module edges stay hard; a linear resize blurs the
    # finder patterns and the detector gives up.
    img = Image.fromarray(matrix, mode="L").convert("RGB")
    img = img.resize((img.width * 3, img.height * 3), Image.NEAREST)
    data, _, _ = cv2.QRCodeDetector().detectAndDecode(np.array(img))
    return data


def _report_kwargs(**over) -> dict:
    base = dict(
        project_id=PROJECT,
        project_name="Kilifi Community Mangrove Restoration",
        region="Kilifi, Kenya",
        net_tco2e_per_ha=8.42,
        sampling_ci90_pct=8.7,
        root_hash="sha256:" + "ab" * 32,
        cloud_name="demo-cloud",
        app_url=APP_URL,
        warped_public_id="projects/KEN-042/warped_baseline",
    )
    base.update(over)
    return base


# --------------------------------------------------------------------------- #
# Payload
# --------------------------------------------------------------------------- #


class TestPayloadUrl:
    def test_points_at_provenance_not_the_pdf(self):
        """The PDF is regenerated; the provenance record is content-addressed."""
        assert report_payload_url(APP_URL, PROJECT).endswith(
            f"/api/v1/assets/{PROJECT}/provenance"
        )

    def test_strips_trailing_slash(self):
        assert "//api" not in report_payload_url(APP_URL + "/", PROJECT)

    def test_escapes_awkward_project_ids(self):
        """A slash in an id would otherwise forge a different asset's URL."""
        url = report_payload_url(APP_URL, "KEN/042")
        assert "KEN/042" not in url
        assert "KEN%2F042" in url

    @pytest.mark.parametrize("bad", ["", "   "])
    def test_empty_project_id_refused(self, bad):
        with pytest.raises(ReportError, match="project_id"):
            report_payload_url(APP_URL, bad)


# --------------------------------------------------------------------------- #
# QR — verified by decoding, not by trusting the encoder
# --------------------------------------------------------------------------- #


class TestQrIsActuallyScannable:
    def test_decodes_back_to_the_payload(self):
        payload = report_payload_url(APP_URL, PROJECT)
        assert _decode(qr_matrix(payload)) == payload

    def test_decodes_for_a_long_public_id(self):
        """A realistic asset id pushes the symbol to a higher version."""
        payload = report_payload_url(APP_URL, "projects/KEN-042/mangrove/m18/warped_canopy_plate_v2")
        assert _decode(qr_matrix(payload)) == payload

    def test_decodes_for_a_non_ascii_project_id(self):
        payload = report_payload_url(APP_URL, "KEN-042-äöü")
        assert _decode(qr_matrix(payload)) == payload

    def test_uses_the_specified_quiet_zone(self):
        """Below 4 modules many scanners refuse the symbol entirely."""
        qr = build_qr("x")
        matrix = qr_matrix("x", module_pixels=1, quiet_zone=QR_QUIET_ZONE)
        # modules + 2 * quiet_zone, since the quiet zone surrounds the symbol
        assert matrix.shape[0] == len(qr.matrix) + 2 * QR_QUIET_ZONE

    def test_raster_scale_does_not_change_the_payload(self):
        payload = report_payload_url(APP_URL, PROJECT)
        for scale in (1, 3, 8):
            assert _decode(qr_matrix(payload, module_pixels=scale)) == payload

    def test_error_correction_level_is_pinned_not_boosted(self):
        """segno boosts the level by default, and boosting is payload-dependent.

        Left on, asking for 'l' on a short payload returns 'M' — so the symbol you
        get is not the level you chose, and it varies with URL length.
        """
        for level in ("l", "m", "q", "h"):
            # segno normalises the level to upper case on the way out.
            assert build_qr("payload", error=level).error == level.upper()
        assert QR_ERROR_CORRECTION == "m"

    def test_pinned_level_survives_a_long_payload(self):
        for payload in ("short", "x" * 300):
            assert build_qr(payload, error="l").error == "L"
        assert build_qr("x" * 300, error="h").error == "H"

    def test_higher_error_correction_produces_more_modules(self):
        """Proof the level changes the symbol rather than being ignored."""
        low = len(build_qr("payload", error="l").matrix)
        high = len(build_qr("payload", error="h").matrix)
        assert high > low

    def test_empty_payload_refused(self):
        with pytest.raises(ReportError, match="empty"):
            build_qr("")

    def test_rejects_a_zero_module_scale(self):
        with pytest.raises(ReportError, match="module_pixels"):
            qr_matrix("x", module_pixels=0)


class TestQrEmbeddings:
    def test_data_uri_is_a_png(self):
        uri = qr_data_uri("payload")
        assert uri.startswith("data:image/png;base64,")
        raw = base64.b64decode(uri.split(",", 1)[1])
        assert raw[:8] == b"\x89PNG\r\n\x1a\n"

    def test_data_uri_png_decodes_and_still_carries_the_payload(self):
        """The embedded image, not the matrix, is what a client receives."""
        uri = qr_data_uri(report_payload_url(APP_URL, PROJECT))
        raw = base64.b64decode(uri.split(",", 1)[1])
        assert _decode(np.array(Image.open(io.BytesIO(raw)).convert("L"))) == \
            report_payload_url(APP_URL, PROJECT)

    def test_svg_is_wellformed(self):
        svg = qr_svg("payload")
        assert svg.lstrip().startswith("<?xml")
        assert "<svg" in svg and "</svg>" in svg

    def test_svg_viewbox_matches_the_matrix(self):
        """A wrong viewBox renders a cropped or stretched code that will not scan."""
        import re

        qr = build_qr("payload")
        svg = qr_svg("payload")
        width = int(re.search(r'width="(\d+)"', svg).group(1))
        assert width == (len(qr.matrix) + 2 * QR_QUIET_ZONE) * 4


# --------------------------------------------------------------------------- #
# Report assembly
# --------------------------------------------------------------------------- #


class TestBuildReport:
    def test_builds_a_report(self):
        r = build_report(**_report_kwargs())
        assert r["project_id"] == PROJECT
        assert r["pdf_url"].startswith("https://res.cloudinary.com/demo-cloud/")
        assert r["qr"]["payload"].endswith("/provenance")

    def test_figures_are_returned_alongside_the_pdf_url(self):
        """A PDF composite is opaque; the JSON must be able to disagree visibly."""
        r = build_report(**_report_kwargs())
        assert r["figures"]["net_certified_tco2e_per_ha"] == 8.42
        assert r["figures"]["sampling_ci90_pct"] == 8.7
        assert r["figures"]["root_hash"].startswith("sha256:")

    def test_report_id_is_stable_for_identical_inputs(self):
        assert build_report(**_report_kwargs())["report_id"] == \
            build_report(**_report_kwargs())["report_id"]

    def test_report_id_changes_when_the_figures_change(self):
        a = build_report(**_report_kwargs())["report_id"]
        b = build_report(**_report_kwargs(net_tco2e_per_ha=9.0))["report_id"]
        assert a != b

    def test_report_id_changes_with_the_project(self):
        assert content_address("A", "x") != content_address("B", "x")

    def test_every_field_is_json_serialisable(self):
        import json

        json.dumps(build_report(**_report_kwargs()))

    @pytest.mark.parametrize("missing", ["project_id", "net_tco2e_per_ha"])
    def test_required_fields_refused(self, missing):
        kwargs = _report_kwargs()
        kwargs[missing] = "" if missing == "project_id" else None
        with pytest.raises(ReportError):
            build_report(**kwargs)

    def test_negative_carbon_figure_is_representable(self):
        """A removal project reports a negative number; it must not be clamped."""
        r = build_report(**_report_kwargs(net_tco2e_per_ha=-3.15))
        assert r["figures"]["net_certified_tco2e_per_ha"] == -3.15

    def test_qr_in_the_report_is_scannable(self):
        r = build_report(**_report_kwargs())
        assert _decode(qr_matrix(r["qr"]["payload"])) == r["qr"]["payload"]

    def test_module_pixel_default_is_used(self):
        r = build_report(**_report_kwargs())
        assert QR_MODULE_PIXELS >= 1
        assert r["qr"]["quiet_zone_modules"] == QR_QUIET_ZONE
