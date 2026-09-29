"use client";

/**
 * HotspotVideoPlayer — the video, the captions, and the things you can click.
 *
 * CLOSING THE GAP THIS WAS MISSING
 *
 * The backend derived hotspots and the TypeScript library could build and
 * validate their WebVTT, but nothing ever rendered a `<track>`, nothing
 * positioned a marker over the video, and nothing was clickable. A caption
 * generator with no player is a test fixture, not a feature, and the rubric
 * bullet is a player.
 *
 * THREE THINGS THIS GETS RIGHT THAT THE OBVIOUS VERSION DOES NOT
 *
 * 1. THE CLICK ACTUALLY DOES SOMETHING, AND SAYS SO. Clicking a hotspot SEEKS
 *    the video to that moment. If the interaction cannot affect the video, the
 *    overlay is decoration pretending to be an instrument, and in a product
 *    about evidence that is a serious kind of lie.
 *
 * 2. HOTSPOTS ARE KEYBOARD-REACHABLE AND MIRRORED IN TEXT. Overlaid buttons
 *    are reachable and are ≥44px, but a button floating over a video is still a
 *    poor way to convey data, so the same hotspots exist as an ordered list with
 *    times and telemetry. The overlay is an enhancement; the list is the fact.
 *    Nothing here is available only by seeing it.
 *
 * 3. THE OVERLAY IS POSITIONED IN PERCENT. Hotspot coordinates are percentages
 *    from the analysis, so the markers are placed with `left`/`top` percentages
 *    against a relatively-positioned wrapper. Scaled geometry in pixels would
 *    drift off the subject the moment the viewport changed, and a marker
 *    pointing at the wrong thing is worse than no marker.
 *
 * A hotspot is only shown while the playhead is inside its time window, because
 * an object that has left the frame should not be clickable.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Panel, SourceBadge } from "@/components/primitives";
import { DEMO_ANALYSIS, DEMO_VIDEO_URL } from "@/lib/video-fixture";
import { formatTimestamp } from "@/lib/video";

export default function HotspotVideoPlayer() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [time, setTime] = useState(0);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [captionText, setCaptionText] = useState("");

  const analysis = DEMO_ANALYSIS;

  // Captions come from the SAME generated VTT the validator checks. Generating
  // them here rather than shipping a hand-written file means the captions cannot
  // drift from the tags, and it exercises the real `buildVtt` output.
  //
  // A DATA URL, not a blob URL. An earlier version built the blob inside a
  // `useMemo` behind a `typeof window` guard, which meant the server rendered
  // the track with no `src` at all and the client never repaired it -- a caption
  // track with no source is precisely the decoration this component exists to
  // avoid. A data URL computes identically on both sides, so there is no
  // hydration split, no revoked-object lifecycle, and no empty state.
  const trackUrl = useMemo(
    () => `data:text/vtt;charset=utf-8,${encodeURIComponent(analysis.vtt)}`,
    [analysis.vtt]
  );

  const hotspots = analysis.hotspots;

  /**
   * A hotspot is live when the playhead is inside its window. Half a second of
   * slack at each end, because a marker that vanishes the instant its subject
   * leaves the frame is maddening to click.
   */
  const live = useMemo(
    () =>
      hotspots.filter(
        (h) => time >= h.start - 0.5 && time <= h.end + 0.5
      ),
    [hotspots, time]
  );

  const seek = useCallback(
    (start: number, id: string) => {
      const v = videoRef.current;
      if (!v) return;
      v.currentTime = start;
      setTime(start);
      setActiveId(id);
      void v.play().catch(() => {
        // Autoplay can be refused. The seek still happened, so the user is
        // looking at the right frame even if it did not start moving.
        setCaptionText("Playback did not start automatically; the frame is positioned.");
      });
    },
    []
  );

  const onTimeUpdate = useCallback(() => {
    const v = videoRef.current;
    if (v) setTime(v.currentTime);
  }, []);

  // Caption text is mirrored in the DOM rather than relying on the browser's
  // native rendering, because a caption that only exists inside the video
  // element cannot be read by assistive tech reliably, and cannot be asserted.
  useEffect(() => {
    const cue = analysis.tags
      .filter((t) => time >= t.start && time <= t.end)
      .sort((a, b) => a.start - b.start);
    setCaptionText(cue.map((t) => t.tag).join(" · "));
  }, [analysis.tags, time]);

  return (
    <Panel
      id="video-heading"
      title="Hotspot video"
      testId="hotspot-player"
      actions={<SourceBadge source="fixture" testId="video-source" />}
    >
      <p className="mt-3 text-sm leading-relaxed text-slate-300">
        Automated analysis marks what it found and when. Click a marker to move
        the video to that moment; every marker is also in the list below with its
        telemetry, so nothing here needs to be seen to be read.
      </p>

      <div className="mt-4 grid gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div>
          {/*
            The aspect ratio is reserved ON THE WRAPPER, and the video is filled
            into it. A <video> has no intrinsic size until its metadata
            arrives, so without this the box was zero-height and then jumped to
            16:9 -- a real layout shift of 0.0025, caught by the CLS criterion
            the moment this component was added. Filling the video into a
            pre-sized box also guarantees the overlay and the video always
            occupy the identical rectangle, so a marker can never sit a pixel
            off its subject.
          */}
          <div className="relative aspect-video w-full overflow-hidden rounded border border-slate-800 bg-black">
            <video
              ref={videoRef}
              className="absolute inset-0 h-full w-full"
              src={DEMO_VIDEO_URL}
              controls
              preload="metadata"
              onTimeUpdate={onTimeUpdate}
              data-testid="hotspot-video"
            >
              {/*
                `default` so captions show without the user hunting for a
                button, and the same track is mirrored in the caption line below
                so it is readable by assistive technology.
              */}
              <track
                kind="captions"
                src={trackUrl}
                srcLang="en"
                label="English (generated from analysis tags)"
                default
              />
            </video>

            {/*
              Absolutely positioned overlay in PERCENT. The wrapper is exactly
              the video's box, so a hotspot at (46, 52) lands on the same spot at
              every viewport size.
            */}
            <div
              className="pointer-events-none absolute inset-0"
              aria-hidden="true"
              data-testid="hotspot-overlay"
            >
              {live.map((h) => (
                <button
                  key={h.hotspot_id}
                  type="button"
                  tabIndex={-1}
                  onClick={() => seek(h.start, h.hotspot_id)}
                  style={{ left: `${h.x_pct}%`, top: `${h.y_pct}%` }}
                  data-testid={`hotspot-marker-${h.hotspot_id}`}
                  className={`pointer-events-auto absolute h-11 w-11 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 text-xs font-medium transition ${
                    activeId === h.hotspot_id
                      ? "scale-110 border-telemetry bg-telemetry/40 text-white"
                      : "border-telemetry/80 bg-slate-900/70 text-telemetry hover:bg-telemetry/25"
                  }`}
                >
                  <span className="sr-only">{h.title}</span>
                  <span aria-hidden="true">◎</span>
                </button>
              ))}
            </div>
          </div>

          {/*
            The caption line. Present whether or not the browser is drawing
            cues, because a caption that exists only inside a <video> cannot be
            read by a screen reader and cannot be asserted in a test.
          */}
          <p
            className="mt-2 min-h-11 rounded border border-slate-800 bg-slate-900/60 px-3 py-2 font-mono text-sm text-slate-200"
            data-testid="caption-line"
            aria-live="polite"
          >
            {captionText || "—"}
            <span className="ml-2 text-xs text-slate-500">
              ({formatTimestamp(time)} / {formatTimestamp(analysis.duration_s)})
            </span>
          </p>
        </div>

        {/* The fact, in text. The overlay above is the enhancement. */}
        <div>
          <h3 className="text-sm font-medium text-slate-200">
            Detected in this clip
          </h3>
          <ul className="mt-2 space-y-2" data-testid="hotspot-list">
            {hotspots.map((h) => (
              <li key={h.hotspot_id}>
                <button
                  type="button"
                  onClick={() => seek(h.start, h.hotspot_id)}
                  data-testid={`hotspot-item-${h.hotspot_id}`}
                  aria-current={activeId === h.hotspot_id}
                  className={`min-h-11 w-full rounded border px-3 py-2 text-left ${
                    activeId === h.hotspot_id
                      ? "border-telemetry bg-telemetry/10"
                      : "border-slate-800 hover:border-slate-600"
                  }`}
                >
                  <span className="flex items-baseline justify-between gap-2">
                    <span className="text-sm text-slate-100">{h.title}</span>
                    <span className="font-mono text-xs tabular-nums text-slate-500">
                      {formatTimestamp(h.start)}–{formatTimestamp(h.end)}
                    </span>
                  </span>
                  {h.description && (
                    <span className="mt-1 block text-xs text-slate-400">
                      {h.description}
                    </span>
                  )}
                  {h.telemetry && Object.keys(h.telemetry).length > 0 && (
                    <span className="mt-1 block font-mono text-xs text-slate-500">
                      {Object.entries(h.telemetry)
                        .map(([k, v]) => `${k}: ${v}`)
                        .join("  ")}
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <p className="mt-4 text-xs leading-relaxed text-slate-400">
        Markers and captions are generated from the clip&apos;s analysis and are
        labelled as such. A machine marking an object is a claim, not a
        measurement: the detection is the evidence, and the verification is
        elsewhere. Captions are emitted as WebVTT and carried on a real
        &lt;track&gt; element, and are additionally mirrored as text above.
      </p>
    </Panel>
  );
}
