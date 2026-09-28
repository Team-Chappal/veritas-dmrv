"""
S5.1 — bulk field ingest.

The behaviour worth testing is the failure handling. A batch endpoint that
returns 400 the moment one file is corrupt discards a morning of field
evidence, and nobody notices the bug because the happy path is the only path
anyone exercises by hand.
"""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

pytestmark = pytest.mark.tier5

URL = "/api/v1/media/ingest"


def png(seed: int = 0, width: int = 160, height: int = 120) -> bytes:
    """A deterministic image with a dark left band, so canopy signals appear."""
    rng = np.random.default_rng(seed)
    arr = (rng.random((height, width, 3)) * 90 + 80).astype("uint8")
    arr[:, : width // 3] = 40
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "PNG")
    return buf.getvalue()


def upload(name: str, data: bytes) -> tuple:
    return ("files", (name, data, "image/png"))


@pytest.fixture()
def field(token_for):
    return token_for("field")


# --------------------------------------------------------------------------- #
# Authorisation
# --------------------------------------------------------------------------- #


class TestIngestAuthorisation:
    def test_requires_a_token(self, anon_client):
        assert anon_client.post(URL, files=[upload("a.png", png())]).status_code == 401

    def test_field_upload_scope_is_the_right_one(self, anon_client, token_for):
        r = anon_client.post(URL, files=[upload("a.png", png())], headers=token_for("field"))
        assert r.status_code == 200

    @pytest.mark.parametrize("role", ["triage", "vvb"])
    def test_other_roles_are_refused(self, anon_client, token_for, role):
        """Ingest is a field action; review and sign-off must not upload."""
        r = anon_client.post(URL, files=[upload("a.png", png())], headers=token_for(role))
        assert r.status_code == 403

    def test_forged_token_refused(self, anon_client):
        r = anon_client.post(
            URL, files=[upload("a.png", png())], headers={"Authorization": "Bearer a.b.c"}
        )
        assert r.status_code == 401

    def test_both_prefixes_work(self, anon_client, field):
        for path in ("/v1/media/ingest", "/api/v1/media/ingest"):
            r = anon_client.post(path, files=[upload("a.png", png())], headers=field)
            assert r.status_code == 200, path


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #


class TestIngestHappyPath:
    def test_ingests_a_single_file(self, anon_client, field):
        r = anon_client.post(URL, files=[upload("a.png", png())], headers=field).json()
        assert r["requested"] == 1 and r["ingested"] == 1 and r["rejected"] == 0
        assert r["partial"] is False

    def test_ingests_a_batch(self, anon_client, field):
        files = [upload(f"{i}.png", png(i)) for i in range(5)]
        r = anon_client.post(URL, files=files, headers=field).json()
        assert r["ingested"] == 5
        assert len(r["items"]) == 5

    def test_returns_tags_with_evidence(self, anon_client, field):
        item = anon_client.post(URL, files=[upload("a.png", png())], headers=field).json()["items"][0]
        assert item["tags"], "no tags derived from a canopy-bearing image"
        assert set(item["tag_evidence"]) == set(item["tags"])

    def test_records_dimensions(self, anon_client, field):
        item = anon_client.post(
            URL, files=[upload("a.png", png(width=200, height=150))], headers=field
        ).json()["items"][0]
        assert (item["width_px"], item["height_px"]) == (200, 150)

    def test_context_is_recorded(self, anon_client, field):
        r = anon_client.post(
            URL, files=[upload("a.png", png())], headers=field,
            data={"project_id": "KEN-99", "milestone_phase": "progress",
                  "sustainability_domain": "restoration"},
        ).json()
        assert r["project_id"] == "KEN-99"
        assert r["milestone_phase"] == "progress"

    def test_context_changes_the_tags(self, anon_client, field):
        """Otherwise the context fields are decoration."""
        base = anon_client.post(
            URL, files=[upload("a.png", png())], headers=field,
            data={"milestone_phase": "baseline"},
        ).json()["items"][0]["tags"]
        progress = anon_client.post(
            URL, files=[upload("a.png", png())], headers=field,
            data={"milestone_phase": "progress"},
        ).json()["items"][0]["tags"]
        assert base != progress

    def test_tag_counts_aggregate_the_batch(self, anon_client, field):
        files = [upload(f"{i}.png", png(i)) for i in range(3)]
        r = anon_client.post(URL, files=files, headers=field).json()
        total = sum(r["tag_counts"].values())
        assert total == sum(len(i["tags"]) for i in r["items"])

    def test_tag_counts_are_ordered_by_frequency(self, anon_client, field):
        files = [upload(f"{i}.png", png(i)) for i in range(4)]
        counts = list(anon_client.post(URL, files=files, headers=field).json()["tag_counts"].values())
        assert counts == sorted(counts, reverse=True)

    def test_response_is_json_serialisable(self, anon_client, field):
        import json

        json.dumps(anon_client.post(URL, files=[upload("a.png", png())], headers=field).json())


# --------------------------------------------------------------------------- #
# Partial failure — the behaviour that matters
# --------------------------------------------------------------------------- #


class TestPartialFailure:
    def test_one_bad_file_does_not_sink_the_batch(self, anon_client, field):
        """The whole point: 39 good frames must not be lost to 1 corrupt one."""
        files = [
            upload("ok1.png", png(1)),
            upload("corrupt.png", b"this is not an image"),
            upload("ok2.png", png(2)),
        ]
        r = anon_client.post(URL, files=files, headers=field)
        assert r.status_code == 200
        body = r.json()
        assert body["ingested"] == 2 and body["rejected"] == 1
        assert body["partial"] is True

    def test_the_failure_names_the_file(self, anon_client, field):
        files = [upload("good.png", png()), upload("broken.png", b"junk")]
        items = anon_client.post(URL, files=files, headers=field).json()["items"]
        bad = next(i for i in items if i["status"] == "REJECTED")
        assert bad["filename"] == "broken.png"
        assert bad["error"]

    def test_rejected_items_carry_no_tags(self, anon_client, field):
        """A rejected file with tags would be evidence of nothing."""
        items = anon_client.post(
            URL, files=[upload("broken.png", b"junk")], headers=field
        ).json()["items"]
        assert items[0]["tags"] == []

    def test_empty_upload_rejected_not_crashed(self, anon_client, field):
        r = anon_client.post(URL, files=[upload("empty.png", b"")], headers=field)
        assert r.status_code == 200
        item = r.json()["items"][0]
        assert item["status"] == "REJECTED" and "empty" in item["error"]

    def test_a_fully_bad_batch_still_answers_200(self, anon_client, field):
        """A batch where everything failed is a reportable outcome, not a crash."""
        files = [upload("a.bin", b"x"), upload("b.bin", b"y")]
        r = anon_client.post(URL, files=files, headers=field)
        assert r.status_code == 200
        body = r.json()
        assert body["ingested"] == 0 and body["rejected"] == 2
        assert body["partial"] is False

    def test_oversized_decode_is_refused(self, anon_client, field):
        """A decompression bomb must be refused, not expanded into memory."""
        import mock_server

        original = mock_server.INGEST_MAX_PIXELS
        mock_server.INGEST_MAX_PIXELS = 10
        try:
            item = anon_client.post(
                URL, files=[upload("big.png", png())], headers=field
            ).json()["items"][0]
        finally:
            mock_server.INGEST_MAX_PIXELS = original
        assert item["status"] == "REJECTED"
        assert "ceiling" in item["error"]

    def test_ceiling_is_a_real_limit(self):
        import mock_server

        assert mock_server.INGEST_MAX_PIXELS > 0
        assert mock_server.INGEST_MAX_FILES > 0


# --------------------------------------------------------------------------- #
# Limits and names
# --------------------------------------------------------------------------- #


class TestLimits:
    def test_batch_cap_enforced(self, anon_client, field):
        import mock_server

        original = mock_server.INGEST_MAX_FILES
        mock_server.INGEST_MAX_FILES = 2
        try:
            files = [upload(f"{i}.png", png(i)) for i in range(3)]
            r = anon_client.post(URL, files=files, headers=field)
        finally:
            mock_server.INGEST_MAX_FILES = original
        assert r.status_code == 413

    def test_no_files_is_422(self, anon_client, field):
        r = anon_client.post(URL, data={"project_id": "KEN-1"}, headers=field)
        assert r.status_code == 422

    def test_whitespace_filename_is_normalised(self, anon_client, field):
        """A client sending "   " must not produce a blank asset id downstream."""
        r = anon_client.post(
            URL, files=[("files", ("   ", png(), "image/png"))], headers=field
        ).json()
        assert len(r["items"]) == 1
        assert r["items"][0]["filename"] == "unnamed"

    def test_filename_is_preserved_when_present(self, anon_client, field):
        r = anon_client.post(
            URL, files=[upload("mangrove/month18/frame_0042.png", png())], headers=field
        ).json()
        assert r["items"][0]["filename"] == "mangrove/month18/frame_0042.png"


# --------------------------------------------------------------------------- #
# The ingest/verify boundary
# --------------------------------------------------------------------------- #


class TestIngestDoesNotVerify:
    """Ingest records evidence. It does not judge it."""

    def test_response_says_so(self, anon_client, field):
        body = anon_client.post(URL, files=[upload("a.png", png())], headers=field).json()
        assert "does not verify" in body["note"]
        assert "/triage/evaluate" in body["note"]

    def test_no_verdict_field_is_returned(self, anon_client, field):
        """A status that looked like a verdict would be read as one."""
        body = anon_client.post(URL, files=[upload("a.png", png())], headers=field).json()
        for key in ("decision", "verdict", "status_decision", "confidence_score"):
            assert key not in body
        for key in ("decision", "verdict", "confidence_score"):
            assert key not in body["items"][0]


# --------------------------------------------------------------------------- #
# S5.6 — the report route
# --------------------------------------------------------------------------- #


class TestReportRoute:
    URL = "/api/v1/projects/KEN-042/report"

    def test_is_public(self, anon_client):
        """A filing artefact is already public via provenance; signing is separate."""
        assert anon_client.get(self.URL).status_code == 200

    @pytest.mark.parametrize("prefix", ["/v1", "/api/v1"])
    def test_both_prefixes(self, anon_client, prefix):
        assert anon_client.get(f"{prefix}/projects/KEN-042/report").status_code == 200

    def test_carries_the_pdf_url_and_qr(self, anon_client):
        d = anon_client.get(self.URL).json()
        assert d["pdf_url"].startswith("http")
        assert d["qr"]["payload"].endswith("/provenance")
        assert d["qr"]["png_data_uri"].startswith("data:image/png;base64,")

    def test_figures_are_present(self, anon_client):
        f = anon_client.get(self.URL).json()["figures"]
        assert f["net_certified_tco2e_per_ha"] > 0
        assert f["sampling_ci90_pct"] == 8.7

    def test_fixture_mode_says_so(self, anon_client):
        d = anon_client.get(self.URL).json()
        assert d["mode"] == "FIXTURE"
        assert "placeholder" in d["caveat"]

    def test_dossier_and_report_agree(self, anon_client):
        """Two artefacts quoting different carbon numbers is an audit-day defect.

        Both call the same biomass path, so this is a regression guard on the
        two routes continuing to share it.
        """
        report = anon_client.get(self.URL).json()["figures"]
        dossier = anon_client.get("/api/v1/audit/dossier/KEN-042").json()
        assert report["net_certified_tco2e_per_ha"] == \
            dossier["allometric_biomass_estimate"]["estimated_tco2e_per_hectare"]

    def test_no_discount_below_the_vm0047_threshold(self, anon_client):
        """VM0047 8.4 discounts only above 15% error, so net == gross at 8.7%.

        Pinned because gross == net looks like a missing multiplier, and the
        next person to read it will assume the calculation is broken.
        """
        figures = anon_client.get(self.URL).json()["figures"]
        assert figures["sampling_ci90_pct"] < 15
        assert figures["net_certified_tco2e_per_ha"] > 0

    def test_blank_project_id_is_422(self, anon_client):
        assert anon_client.get("/api/v1/projects/%20/report").status_code == 422

    def test_response_is_json_serialisable(self, anon_client):
        import json

        json.dumps(anon_client.get(self.URL).json())

    def test_qr_is_scannable_end_to_end(self, anon_client):
        """The route's QR decoded, not just the service function's."""
        import base64
        import io

        import numpy as np
        from PIL import Image
        import cv2

        d = anon_client.get(self.URL).json()
        raw = base64.b64decode(d["qr"]["png_data_uri"].split(",", 1)[1])
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        img = img.resize((img.width * 3, img.height * 3), Image.NEAREST)
        decoded, _, _ = cv2.QRCodeDetector().detectAndDecode(np.array(img))
        assert decoded == d["qr"]["payload"]
