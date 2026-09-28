"""
S5 exit criteria, asserted.

    1. every response carries the provenance block
    2. p95 latency on the compare route is under 800 ms

Both are written as tests rather than checked by hand so a later change that
breaks either fails CI instead of being noticed by whoever demos it next.
"""

from __future__ import annotations

import statistics
import time

import pytest

from core.config import Settings
from core.provenance import (
    PROVENANCE_KEY,
    REQUEST_ID_HEADER,
    build_block,
    new_request_id,
    stamp,
)

pytestmark = pytest.mark.tier5

#: The corpus project id. Not KEN-042: that id is invented by several routes and
#: returns 404 from the seeded ones, which would make a 200-expecting test pass
#: for the wrong reason.
PROJECT = "KEN-008"


class _FakeRequest:
    def __init__(self, path: str = "/api/v1/search", method: str = "GET"):
        from starlette.datastructures import URL

        # A real URL, because URL.path is a read-only property and the block
        # reads it. Assigning to it raises.
        self.url = URL(f"http://testserver{path}")
        self.method = method


# --------------------------------------------------------------------------- #
# Block shape
# --------------------------------------------------------------------------- #


class TestBlockContents:
    def test_reports_fixture_mode_honestly(self):
        """A provenance block on fabricated data that does not say so is worse
        than no block: it lends false confidence to a synthetic number."""
        block = build_block(
            request=_FakeRequest(), settings=Settings(), request_id="x", started=time.perf_counter()
        )
        assert block["mode"] == "fixture"
        assert "FIXTURE" in block["evidence"]
        assert "validate_cloudinary_live" in block["caveat"]

    def test_no_caveat_when_configured_live(self):
        s = Settings(
            cloudinary_cloud_name="c", cloudinary_api_key="k", cloudinary_api_secret="s"
        )
        block = build_block(
            request=_FakeRequest(), settings=s, request_id="x", started=time.perf_counter()
        )
        assert block["mode"] == "live"
        assert block["caveat"] == ""

    def test_records_when_and_where(self):
        block = build_block(
            request=_FakeRequest("/api/v1/search"), settings=Settings(),
            request_id="abc", started=time.perf_counter(),
        )
        assert block["path"] == "/api/v1/search"
        assert block["method"] == "GET"
        assert block["request_id"] == "abc"
        assert block["generated_at"].endswith("Z")

    def test_points_at_the_provenance_endpoint(self):
        block = build_block(
            request=_FakeRequest(), settings=Settings(), request_id="x",
            started=time.perf_counter(),
        )
        assert block["provenance_endpoint"].endswith("/provenance")

    def test_never_contains_a_secret(self):
        s = Settings(jwt_secret="jwt-secret-value", cloudinary_api_secret="cld-secret")
        block = build_block(
            request=_FakeRequest(), settings=s, request_id="x", started=time.perf_counter()
        )
        assert "jwt-secret-value" not in str(block)
        assert "cld-secret" not in str(block)

    def test_request_ids_are_unique(self):
        assert len({new_request_id() for _ in range(200)}) == 200


class TestStamping:
    def test_attaches_to_a_dict(self):
        assert PROVENANCE_KEY in stamp({"a": 1}, {"request_id": "x"})

    def test_leaves_existing_content_intact(self):
        assert stamp({"a": 1, "b": 2}, {"request_id": "x"})["b"] == 2

    def test_does_not_reshape_a_list(self):
        """Wrapping a list as {"data": ...} would silently break every client."""
        payload = [1, 2, 3]
        assert stamp(payload, {"request_id": "x"}) is payload

    def test_does_not_overwrite_an_existing_block(self):
        existing = {"a": 1, PROVENANCE_KEY: {"mine": True}}
        assert stamp(existing, {"theirs": True})[PROVENANCE_KEY] == {"mine": True}


# --------------------------------------------------------------------------- #
# Criterion 1 — coverage
# --------------------------------------------------------------------------- #

STAMPED_ROUTES = [
    ("get", "/health"),
    ("get", "/api/v1/schema"),
    ("get", "/api/v1/search?q=mangrove"),
    ("get", f"/api/v1/projects/{PROJECT}/campaign"),
    ("get", f"/api/v1/projects/{PROJECT}/report"),
    ("get", f"/api/v1/projects/{PROJECT}/timeline"),
    ("get", f"/api/v1/projects/{PROJECT}/summary"),
    ("get", "/api/v1/assets/impact_evidence/KEN-042/provenance"),
]


class TestEveryResponseCarriesProvenance:
    @pytest.mark.parametrize("method,path", STAMPED_ROUTES)
    def test_route_is_stamped(self, anon_client, method, path):
        r = getattr(anon_client, method)(path)
        assert r.status_code == 200, f"{path} -> {r.status_code}"
        assert PROVENANCE_KEY in r.json(), f"{path} carries no provenance block"

    def test_search_hits_are_stamped(self, anon_client):
        assert PROVENANCE_KEY in anon_client.get("/api/v1/search?q=canopy").json()

    def test_request_id_is_echoed_as_a_header(self, anon_client):
        r = anon_client.get("/health")
        assert r.headers.get(REQUEST_ID_HEADER)

    def test_supplied_request_id_is_preserved(self, anon_client):
        """A client correlating its own records needs its id echoed back."""
        r = anon_client.get("/health", headers={REQUEST_ID_HEADER: "caller-supplied-1"})
        assert r.headers[REQUEST_ID_HEADER] == "caller-supplied-1"
        assert r.json()[PROVENANCE_KEY]["request_id"] == "caller-supplied-1"

    def test_two_requests_get_different_ids(self, anon_client):
        a = anon_client.get("/health").json()[PROVENANCE_KEY]["request_id"]
        b = anon_client.get("/health").json()[PROVENANCE_KEY]["request_id"]
        assert a != b

    def test_errors_keep_their_own_shape(self, anon_client):
        """A 401 must not grow a field a client could read as a success payload."""
        r = anon_client.post("/api/v1/triage/evaluate", json={})
        assert r.status_code == 401
        assert PROVENANCE_KEY not in r.json()
        assert r.headers.get(REQUEST_ID_HEADER)

    def test_webhook_response_is_stamped(self, anon_client):
        r = anon_client.post("/v1/cloudinary-webhooks/notify", json={
            "notification_type": "eager", "public_id": "a/b", "eager": [],
        })
        assert r.status_code == 200
        assert PROVENANCE_KEY in r.json()

    def test_unknown_project_404s_and_is_traceable(self, anon_client):
        r = anon_client.get("/api/v1/projects/NOPE-999/report")
        assert r.status_code == 404
        assert r.headers.get(REQUEST_ID_HEADER)

    def test_a_report_is_never_built_for_an_unknown_project(self, anon_client):
        """A filing artefact with invented carbon numbers is worse than none."""
        r = anon_client.get("/api/v1/projects/NOPE-999/report")
        assert "figures" not in r.json()

    def test_content_length_matches_the_stamped_body(self, anon_client):
        """A stale content-length truncates the response for a streaming client."""
        r = anon_client.get("/api/v1/search?q=forest")
        assert int(r.headers["content-length"]) == len(r.content)

    def test_response_is_still_valid_json(self, anon_client):
        import json

        json.loads(anon_client.get("/api/v1/search?q=forest").text)

    def test_openapi_schema_is_not_corrupted(self, anon_client):
        """The middleware must not stamp FastAPI's own schema document."""
        schema = anon_client.get("/openapi.json").json()
        assert "paths" in schema
        assert PROVENANCE_KEY not in schema


# --------------------------------------------------------------------------- #
# Criterion 2 — p95 latency on the compare route
# --------------------------------------------------------------------------- #

#: S5 exit criterion, from EXECUTION-PLAN.md.
COMPARE_P95_BUDGET_MS = 800.0


def _pair(soil_scene):
    import numpy as np

    progress = np.roll(soil_scene, 6, axis=1)
    return soil_scene, progress


class TestCompareLatency:
    """p95 on the registration route, measured end to end through the app.

    docs/LATENCY-BASELINE.md already benches the service in isolation; this
    benches the endpoint, because serialisation and multipart parsing are part
    of what a user waits for.
    """

    def test_p95_is_within_budget(self, anon_client, soil_scene, token_for):
        import io

        from PIL import Image

        base, prog = _pair(soil_scene)
        files = []
        for name, arr in (("baseline.png", base), ("progress.png", prog)):
            buf = io.BytesIO()
            Image.fromarray(arr).save(buf, "PNG")
            files.append(("baseline_image" if "baseline" in name else "progress_image",
                          (name, buf.getvalue(), "image/png")))

        headers = token_for("triage")
        timings: list[float] = []
        for _ in range(7):
            started = time.perf_counter()
            r = anon_client.post("/api/v1/cv/align-and-diff", files=files, headers=headers)
            timings.append((time.perf_counter() - started) * 1000)
            assert r.status_code == 200, r.text[:200]

        p95 = _percentile(timings, 95)
        assert p95 < COMPARE_P95_BUDGET_MS, (
            f"p95 {p95:.1f} ms exceeds the {COMPARE_P95_BUDGET_MS:.0f} ms budget "
            f"(all: {[round(t, 1) for t in timings]})"
        )

    def test_budget_is_the_number_the_spec_states(self):
        """Guards against someone "tidying" the budget to match a regression."""
        assert COMPARE_P95_BUDGET_MS == 800.0


def _percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile. Small n, so interpolating would imply precision
    the sample does not have."""
    if not values:
        raise ValueError("no samples")
    ordered = sorted(values)
    # Nearest-rank: 1-based rank, clamped, then converted to a 0-based index.
    rank = min(len(ordered), max(1, -(-int(pct * len(ordered)) // 100)))
    return ordered[rank - 1]


class TestPercentileHelper:
    def test_matches_a_known_case(self):
        assert _percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 95) == 10

    def test_single_sample(self):
        assert _percentile([42.0], 95) == 42.0

    def test_rejects_an_empty_sample(self):
        with pytest.raises(ValueError):
            _percentile([], 95)

    def test_median_helper_available(self):
        assert statistics.median([1, 3, 2]) == 2
