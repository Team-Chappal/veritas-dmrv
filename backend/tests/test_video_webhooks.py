"""
Tier 3 — AI Video Analysis & Webhook Handling

Two properties carry most of the weight here:

* A WebVTT caption track is a media file with a strict grammar, and both ways it
  fails are silent. ``build_vtt`` re-parses its own output and refuses to emit
  an invalid track — a test that a rendered track validates is therefore a real
  check, not a tautology, because the re-parse is independent of the writer.
* A webhook is an unauthenticated POST to a public URL. Anyone who learns the
  endpoint can POST a fabricated payload and mark a fraudulent asset as
  VERIFIED_PASS, so unverifiable notifications must be REJECTED, and retries
  must not double-apply.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest


def _now() -> str:
    """A fresh unix timestamp, as Cloudinary sends it."""
    return str(int(time.time()))

from services.video_service import (
    CUE_GAP_SECONDS,
    MIN_CUE_SECONDS,
    MIN_TAG_CONFIDENCE,
    VideoAnalysisError,
    build_vtt,
    format_timestamp,
    parse_google_video_tagging,
    parse_timestamp,
    segments_to_hotspots,
    validate_vtt,
)
from services.webhook_service import (
    DEFAULT_SIGNATURE_SCHEME,
    SCHEME_CLOUDINARY_DOCUMENTED,
    SIGNATURE_HEADERS,
    TIMESTAMP_HEADER,
    WebhookAction,
    WebhookProcessor,
    WebhookVerifier,
    compute_signature,
    describe_scheme_uncertainty,
)

pytestmark = pytest.mark.tier3


def tagging_payload(*items) -> dict:
    return {
        "info": {
            "categorization": {
                "google_video_tagging": {
                    "data": [
                        {
                            "tag": tag,
                            "start_time_offset": start,
                            "end_time_offset": end,
                            "confidence": confidence,
                        }
                        for tag, start, end, confidence in items
                    ]
                }
            }
        }
    }


NESTED = tagging_payload(
    ("forest", 0.0, 14.5, 0.98),
    ("canopy", 2.1, 12.0, 0.95),
    ("watercourse", 8.0, 14.5, 0.91),
    ("blurry", 1.0, 2.0, 0.31),
    ("noise", 3.0, 3.1, 0.99),
)


# =========================================================================== #
# Timecode
# =========================================================================== #


class TestTimestamps:
    @pytest.mark.parametrize("seconds,expected", [
        (0.0, "00:00:00.000"),
        (14.5, "00:00:14.500"),
        (61.2, "00:01:01.200"),
        (3661.5, "01:01:01.500"),
    ])
    def test_formats_correctly(self, seconds, expected):
        assert format_timestamp(seconds) == expected

    def test_rounding_carries_into_the_next_second(self):
        """59.9996 must not wrap to a negative field."""
        assert format_timestamp(59.9996) == "00:01:00.000"

    @pytest.mark.parametrize("bad", [-5.0, float("nan"), None, "x"])
    def test_total_over_bad_input(self, bad):
        """A malformed third-party timecode must not produce a broken track."""
        assert format_timestamp(bad) == "00:00:00.000"

    def test_round_trips(self):
        for v in (0.0, 7.25, 61.2, 3661.5):
            assert parse_timestamp(format_timestamp(v)) == pytest.approx(v, abs=0.001)


# =========================================================================== #
# Segment parsing
# =========================================================================== #


class TestTaggingParsing:
    def test_extracts_segments(self):
        """Parsing filters on CONFIDENCE only.

        Duration filtering is deliberately deferred to the renderers, so a
        brief-but-credible observation is not hidden at the door. See
        ``test_preserves_short_segments_for_the_cue_builder_to_filter``.
        """
        segments = parse_google_video_tagging(NESTED)
        assert {s.tag for s in segments} == {
            "forest", "canopy", "watercourse", "noise"
        }

    def test_drops_low_confidence(self):
        assert "blurry" not in {s.tag for s in parse_google_video_tagging(NESTED)}

    def test_preserves_short_segments_for_the_cue_builder_to_filter(self):
        """Duration is a rendering concern; confidence is a signal concern.

        Filtering duration at parse time would silently hide a real but brief
        observation from the hotspot surface.
        """
        assert any(s.tag == "noise" for s in parse_google_video_tagging(NESTED))

    def test_sorted_by_start(self):
        starts = [s.start for s in parse_google_video_tagging(NESTED)]
        assert starts == sorted(starts)

    def test_inverted_window_is_normalised(self):
        segments = parse_google_video_tagging(
            tagging_payload(("x", 10.0, 2.0, 0.9))
        )
        assert segments[0].start == 2.0 and segments[0].end == 10.0

    @pytest.mark.parametrize("payload", [
        {}, None, {"info": {}}, {"info": {"categorization": {}}},
        {"info": {"categorization": {"google_video_tagging": {"data": "nope"}}}},
    ])
    def test_malformed_payloads_yield_nothing(self, payload):
        assert parse_google_video_tagging(payload) == []

    def test_malformed_items_are_skipped_not_fatal(self):
        segments = parse_google_video_tagging({
            "info": {"categorization": {"google_video_tagging": {"data": [
                "garbage", {"no_tag": 1}, {"tag": "ok", "start": 0, "end": 5, "confidence": 0.9},
            ]}}}
        })
        assert [s.tag for s in segments] == ["ok"]


# =========================================================================== #
# VTT rendering
# =========================================================================== #


class TestVttRendering:
    def test_output_validates(self):
        assert validate_vtt(build_vtt(parse_google_video_tagging(NESTED))) == []

    def test_nested_windows_become_multiple_lines_in_one_cue(self):
        """Cloudinary nests windows; overlapping cues are invalid VTT.

        Dropping the nested tag would discard a real observation, so the
        timeline is swept and nested tags share a cue as separate lines.
        """
        vtt = build_vtt(parse_google_video_tagging(NESTED))
        blocks = [b for b in vtt.split("\n\n") if "forest" in b]
        nested = [b for b in blocks if "canopy" in b]
        assert nested, "a window where both forest and canopy are active"
        for block in nested:
            lines = [ln for ln in block.strip().split("\n") if ln.strip()]
            assert lines[0].isdigit()
            assert "-->" in lines[1]
            assert "forest" in lines and "canopy" in lines

    def test_no_cue_overlaps_another(self):
        problems = validate_vtt(build_vtt(parse_google_video_tagging(NESTED)))
        assert not [p for p in problems if "overlaps" in p]

    def test_no_negative_duration_cue(self):
        """The defect the validator caught during development."""
        vtt = build_vtt(parse_google_video_tagging(NESTED))
        for block in vtt.split("\n\n"):
            if "-->" not in block:
                continue
            timing = [ln for ln in block.split("\n") if "-->" in ln][0]
            start, end = (s.strip() for s in timing.split("-->"))
            assert parse_timestamp(end) > parse_timestamp(start), timing

    def test_every_observation_survives(self):
        """Sweeping must not lose a tag."""
        vtt = build_vtt(parse_google_video_tagging(NESTED))
        for tag in ("forest", "canopy", "watercourse"):
            assert tag in vtt, f"{tag} was dropped by the sweep"

    def test_header_present(self):
        assert build_vtt(parse_google_video_tagging(NESTED)).startswith("WEBVTT")

    def test_empty_input_refused(self):
        with pytest.raises(VideoAnalysisError):
            build_vtt([])

    def test_all_below_confidence_refused(self):
        with pytest.raises(VideoAnalysisError, match="confidence"):
            build_vtt([{"tag": "x", "start": 0, "end": 9, "confidence": 0.1}])

    def test_all_too_short_refused(self):
        with pytest.raises(VideoAnalysisError):
            build_vtt([{"tag": "x", "start": 0, "end": 0.2, "confidence": 0.9}])

    def test_cue_arrow_in_tag_is_refused(self):
        """Rewriting a tag containing cue syntax would invent content."""
        with pytest.raises(VideoAnalysisError, match="arrow"):
            build_vtt([{"tag": "a-->b", "start": 0, "end": 9, "confidence": 0.9}])

    def test_newline_in_tag_is_collapsed_not_emitted(self):
        vtt = build_vtt([{"tag": "a\nb", "start": 0, "end": 9, "confidence": 0.9}])
        assert "a b" in vtt
        assert validate_vtt(vtt) == []

    def test_max_lines_caps_cue_count(self):
        vtt = build_vtt(parse_google_video_tagging(NESTED), max_lines=2)
        assert len([b for b in vtt.split("\n\n") if "-->" in b]) <= 2

    def test_deterministic(self):
        segs = parse_google_video_tagging(NESTED)
        assert build_vtt(segs) == build_vtt(segs)

    def test_accepts_dicts_and_objects_alike(self):
        segs = parse_google_video_tagging(NESTED)
        assert build_vtt(segs) == build_vtt([s.to_dict() for s in segs])


class TestVttValidator:
    """The validator must actually catch malformed tracks."""

    def test_detects_missing_header(self):
        assert "missing WEBVTT header" in validate_vtt("1\n00:00:00.000 --> 00:00:01.000\nx\n")

    def test_detects_overlap(self):
        bad = "WEBVTT\n\n1\n00:00:00.000 --> 00:00:05.000\na\n\n2\n00:00:02.000 --> 00:00:07.000\nb\n"
        assert any("overlaps" in p for p in validate_vtt(bad))

    def test_detects_inverted_cue(self):
        bad = "WEBVTT\n\n1\n00:00:05.000 --> 00:00:01.000\na\n"
        assert any("ends at or before" in p for p in validate_vtt(bad))

    def test_detects_unparseable_timestamp(self):
        assert any("unparseable" in p for p in validate_vtt("WEBVTT\n\n1\nxx --> yy\na\n"))

    def test_accepts_a_good_track(self):
        assert validate_vtt("WEBVTT\n\n1\n00:00:00.000 --> 00:00:05.000\nforest\n") == []


# =========================================================================== #
# Hotspots
# =========================================================================== #


class TestHotspots:
    def test_builds_hotspots(self):
        hs = segments_to_hotspots(parse_google_video_tagging(NESTED))
        assert len(hs) >= 2
        assert all(0.0 <= h.x_pct <= 100.0 for h in hs)

    def test_applies_the_same_filters_as_the_caption_track(self):
        """A 0.1s hotspot is unclickable and only adds noise to the pin list."""
        tags = {h.title for h in segments_to_hotspots(parse_google_video_tagging(NESTED))}
        assert "Noise" not in tags
        assert "Blurry" not in tags

    def test_label_metadata_is_applied(self):
        hs = segments_to_hotspots(
            parse_google_video_tagging(NESTED),
            {"canopy": {"title": "Closed Canopy", "description": "74% cover",
                        "telemetry": {"cover": "74%"}}},
        )
        canopy = next(h for h in hs if h.hotspot_id.endswith("canopy"))
        assert canopy.title == "Closed Canopy"
        assert canopy.telemetry["cover"] == "74%"

    def test_unlabelled_tag_still_produces_a_hotspot(self):
        hs = segments_to_hotspots([{"tag": "wetland", "start": 0, "end": 9, "confidence": 0.9}])
        assert hs and hs[0].title == "Wetland"

    def test_ids_are_unique_and_slugged(self):
        hs = segments_to_hotspots(parse_google_video_tagging(NESTED))
        assert len({h.hotspot_id for h in hs}) == len(hs)
        assert all(h.hotspot_id.replace("-", "").isalnum() for h in hs)


# =========================================================================== #
# Webhook signature verification
# =========================================================================== #


class TestSignatureVerification:
    BODY = b'{"notification_type":"eager","public_id":"a/b"}'

    def test_no_secret_skips_verification(self):
        ok, reason = WebhookVerifier(secret=None).verify(self.BODY, {})
        assert ok and "skipped" in reason

    def test_requires_signature_is_false_without_a_secret(self):
        assert WebhookVerifier(secret=None).requires_signature is False
        assert WebhookVerifier(secret="s3cret").requires_signature is True

    def test_correct_signature_accepted(self):
        v = WebhookVerifier(secret="s3cret")
        ts = _now()
        sig = compute_signature(self.BODY, "s3cret", timestamp=ts)
        ok, _ = v.verify(self.BODY, {"X-Cld-Signature": sig, TIMESTAMP_HEADER: ts})
        assert ok

    def test_header_lookup_is_case_insensitive(self):
        v = WebhookVerifier(secret="s3cret")
        ts = _now()
        sig = compute_signature(self.BODY, "s3cret", timestamp=ts)
        for key in ("X-Cld-Signature", "x-cld-signature", "X-CLD-SIGNATURE"):
            assert v.verify(self.BODY, {key: sig, TIMESTAMP_HEADER: ts})[0], key

    def test_wrong_signature_rejected(self):
        v = WebhookVerifier(secret="s3cret")
        assert not v.verify(
            self.BODY, {"X-Cld-Signature": "deadbeef", TIMESTAMP_HEADER: _now()}
        )[0]

    def test_missing_signature_rejected(self):
        v = WebhookVerifier(secret="s3cret")
        ok, reason = v.verify(self.BODY, {})
        assert not ok and "no signature header" in reason

    def test_missing_timestamp_rejected(self):
        """The timestamp is part of the signed string, so no signature without it
        can be checked -- and guessing the construction is how this module shipped
        a verifier that rejected every genuine notification."""
        v = WebhookVerifier(secret="s3cret")
        sig = compute_signature(self.BODY, "s3cret", timestamp=_now())
        ok, reason = v.verify(self.BODY, {"X-Cld-Signature": sig})
        assert not ok and TIMESTAMP_HEADER in reason

    def test_stale_timestamp_rejected_as_a_replay(self):
        """A captured, correctly-signed request must not stay valid forever."""
        v = WebhookVerifier(secret="s3cret", valid_for=60)
        old = str(int(time.time()) - 3600)
        sig = compute_signature(self.BODY, "s3cret", timestamp=old)
        ok, reason = v.verify(self.BODY, {"X-Cld-Signature": sig, TIMESTAMP_HEADER: old})
        assert not ok and "replay" in reason

    def test_garbage_timestamp_rejected(self):
        v = WebhookVerifier(secret="s3cret")
        ok, reason = v.verify(
            self.BODY, {"X-Cld-Signature": "abc", TIMESTAMP_HEADER: "not-a-time"}
        )
        assert not ok and "timestamp" in reason

    def test_hmac_signature_is_rejected(self):
        """The scheme is NOT HMAC.

        This is the exact bug the live documentation review caught: every scheme
        in this module used hmac(secret, body), which would have rejected every
        genuine Cloudinary notification while passing every test here.
        """
        v = WebhookVerifier(secret="s3cret")
        ts = _now()
        hmac_sig = hmac.new(b"s3cret", self.BODY, hashlib.sha1).hexdigest()
        ok, _ = v.verify(self.BODY, {"X-Cld-Signature": hmac_sig, TIMESTAMP_HEADER: ts})
        assert not ok

    def test_documented_scheme_is_a_plain_hash_with_the_secret_appended(self):
        """sha(body + timestamp + secret) -- not a keyed MAC."""
        ts = "1719310887"
        expected = hashlib.sha1(self.BODY + ts.encode() + b"s3cret").hexdigest()
        assert compute_signature(self.BODY, "s3cret", timestamp=ts) == expected
        assert compute_signature(self.BODY, "s3cret", timestamp=ts, algorithm="sha256") \
            == hashlib.sha256(self.BODY + ts.encode() + b"s3cret").hexdigest()

    def test_timestamp_is_required_by_compute_signature(self):
        with pytest.raises(ValueError, match="timestamp is required"):
            compute_signature(self.BODY, "s3cret")

    def test_tampered_body_rejected(self):
        v = WebhookVerifier(secret="s3cret")
        ts = _now()
        sig = compute_signature(self.BODY, "s3cret", timestamp=ts)
        assert not v.verify(
            self.BODY + b" ", {"X-Cld-Signature": sig, TIMESTAMP_HEADER: ts}
        )[0]

    def test_all_documented_signature_headers_are_honoured(self):
        v = WebhookVerifier(secret="s")
        ts = _now()
        sig = compute_signature(self.BODY, "s", timestamp=ts)
        for header in SIGNATURE_HEADERS:
            assert v.verify(self.BODY, {header: sig, TIMESTAMP_HEADER: ts})[0], header

    def test_scheme_is_a_parameter_not_an_assertion(self):
        """The exact construction is unconfirmed and must not be hard-coded."""
        text = describe_scheme_uncertainty()
        assert "NOT confirmed against a real notification" in text
        assert "NOT HMAC" in text
        assert WebhookVerifier(secret="s").scheme == DEFAULT_SIGNATURE_SCHEME
        assert DEFAULT_SIGNATURE_SCHEME == SCHEME_CLOUDINARY_DOCUMENTED
        # Still unconfirmed against live traffic, so it stays a parameter rather
        # than a hard-coded construction: an unknown scheme is still refused.
        with pytest.raises(ValueError, match="Unknown signature scheme"):
            compute_signature(self.BODY, "s", "some_other_idea", timestamp=_now())

    def test_unknown_scheme_rejected(self):
        with pytest.raises(ValueError, match="Unknown signature scheme"):
            compute_signature(self.BODY, "s", "telepathy")

    def test_empty_secret_rejected(self):
        with pytest.raises(ValueError, match="secret is required"):
            compute_signature(self.BODY, "", timestamp=_now())

    def test_unsupported_algorithm_rejected(self):
        with pytest.raises(ValueError, match="algorithm"):
            compute_signature(self.BODY, "s", DEFAULT_SIGNATURE_SCHEME, "whirlpool", _now())

    def test_unknown_scheme_rejected(self):
        with pytest.raises(ValueError, match="Unknown signature scheme"):
            compute_signature(self.BODY, "s", "telepathy", timestamp=_now())

    def test_legacy_scheme_names_still_resolve(self):
        """An old config naming must not start raising on a string nobody
        remembers writing."""
        ts = _now()
        expected = compute_signature(self.BODY, "s", timestamp=ts)
        for legacy in ("body_plus_secret", "secret_plus_body", "plain_concat"):
            assert compute_signature(self.BODY, "s", legacy, timestamp=ts) == expected


# =========================================================================== #
# Webhook processing
# =========================================================================== #


def _post(processor, payload, secret=None, timestamp=None):
    body = json.dumps(payload).encode()
    headers = {}
    if secret:
        headers["X-Cld-Signature"] = compute_signature(
            body, secret, timestamp=timestamp or _now()
        )
        headers[TIMESTAMP_HEADER] = timestamp or _now()
    return processor.process(body, headers)


class TestWebhookProcessing:
    def test_unverified_payload_is_rejected(self):
        """The security-critical case: a fabricated POST must not be applied."""
        p = WebhookProcessor(WebhookVerifier(secret="s3cret"))
        result = _post(p, {"notification_type": "eager", "public_id": "a/b",
                           "eager": [{"secure_url": "x"}]})
        assert result.action == WebhookAction.REJECTED_UNVERIFIED
        assert result.accepted is False
        assert result.derived == {}

    def test_verified_eager_notification_accepted(self):
        p = WebhookProcessor(WebhookVerifier(secret="s3cret"))
        result = _post(p, {"notification_type": "eager", "public_id": "a/b",
                           "eager": [{"transformation": "c_fill,w_100", "secure_url": "u"}]},
                       secret="s3cret")
        assert result.accepted
        assert result.derived["ready_count"] == 1

    def test_retry_is_deduplicated(self):
        """Cloudinary retries; a resend must not double-apply."""
        p = WebhookProcessor(WebhookVerifier(secret="s3cret"))
        payload = {"notification_type": "eager", "public_id": "a/b",
                   "eager": [{"secure_url": "u"}]}
        assert _post(p, payload, "s3cret").action == WebhookAction.ACCEPTED
        second = _post(p, payload, "s3cret")
        assert second.action == WebhookAction.DUPLICATE

    def test_dedup_key_uses_explicit_id_when_present(self):
        p = WebhookProcessor()
        a = {"notification_type": "eager", "notification_id": "n1", "public_id": "x"}
        b = dict(a, public_id="y")
        assert _post(p, a).accepted
        assert _post(p, b).action == WebhookAction.DUPLICATE

    def test_video_notification_produces_a_caption_track(self):
        p = WebhookProcessor()
        result = _post(p, {
            "notification_type": "video", "public_id": "v/1", **NESTED,
        })
        assert result.accepted
        assert "WEBVTT" in result.derived["vtt"]
        assert "canopy" in result.derived["tags"]
        assert result.derived["hotspots"]

    def test_malformed_json_rejected(self):
        p = WebhookProcessor(WebhookVerifier(secret="s"))
        ts = _now()
        result = p.process(
            b"not json",
            {"X-Cld-Signature": compute_signature(b"not json", "s", timestamp=ts),
             TIMESTAMP_HEADER: ts},
        )
        assert result.action == WebhookAction.REJECTED_MALFORMED

    def test_non_object_payload_rejected(self):
        p = WebhookProcessor()
        assert _post(p, [1, 2, 3]).action == WebhookAction.REJECTED_MALFORMED

    def test_unhandled_type_ignored_not_failed(self):
        p = WebhookProcessor()
        result = _post(p, {"notification_type": "context", "public_id": "a"})
        assert result.action == WebhookAction.IGNORED_UNHANDLED

    def test_result_is_json_serialisable(self):
        p = WebhookProcessor()
        json.dumps(_post(p, {"notification_type": "eager", "public_id": "a",
                             "eager": []}).to_dict())

    def test_history_is_retained_for_audit(self):
        p = WebhookProcessor()
        _post(p, {"notification_type": "eager", "public_id": "a", "eager": []})
        assert len(p.results) == 1

    def test_fixture_mode_accepts_unsigned_so_the_demo_works(self):
        """Degrade open, but the result still admits verification was skipped."""
        p = WebhookProcessor(WebhookVerifier(secret=None))
        result = _post(p, {"notification_type": "eager", "public_id": "a", "eager": []})
        assert result.accepted
        assert "skipped" in result.reason
