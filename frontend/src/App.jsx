import React, { useEffect, useRef, useState } from "react";
import { lookup } from "./devices.js";
import { DEFAULT_SIZE_HW, initialRelay, saveRelay, subscribe, videoUrl } from "./feed.js";
import { Hammer, Screwdriver, Wrench } from "./components/Tools.jsx";
import { BreadboardPanel, StepsPanel } from "./components/LessonPreview.jsx";
import Inventory from "./components/Inventory.jsx";
import { useInventory } from "./inventory.js";

const Cog = ({ size = 28, className = "cog", color = "currentColor" }) => (
  <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.6" strokeLinecap="round" aria-hidden="true">
    <circle cx="12" cy="12" r="3" />
    <circle cx="12" cy="12" r="7" />
    <path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1 7 17M17 7l2.1-2.1" />
  </svg>
);

const STATUS_TEXT = {
  mock: "Preview mode",
  connecting: "Connecting to relay…",
  live: "Live · glasses relay",
  error: "Relay unreachable, retrying…",
  paused: "Paused",
};

function formatClock(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  const hh = String(Math.floor(s / 3600)).padStart(2, "0");
  const mm = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
  const ss = String(s % 60).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
}

// A real device label: not still pending and not Gemini's "none" (not a target device).
const isDeviceLabel = (label) => Boolean(label) && label !== "none";

function RelayForm({ relay, onConnect, onClose }) {
  const [url, setUrl] = useState(relay?.url || "http://localhost:8765");
  const [token, setToken] = useState(relay?.token || "");
  return (
    <form
      className="relay-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (url.trim() && token.trim()) onConnect({ url: url.trim().replace(/\/+$/, ""), token: token.trim() });
      }}
    >
      <div className="relay-title">Connect glasses relay</div>
      <label>
        Relay address
        <input className="mono" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="http://localhost:8765" />
      </label>
      <label>
        Token
        <input className="mono" value={token} onChange={(e) => setToken(e.target.value)} placeholder="printed by live_runner" />
      </label>
      <div className="relay-actions">
        <button type="submit" className="text-btn primary">Connect</button>
        {relay && (
          <button type="button" className="text-btn" onClick={() => onConnect(null)}>Use mock feed</button>
        )}
        <button type="button" className="text-btn" onClick={onClose}>Cancel</button>
      </div>
    </form>
  );
}

function RecordingPanel({ frame, sizeHW, elapsed, paused, onTogglePause, relay, status, onRelayChange, videoRef }) {
  const tracks = frame?.tracks || [];
  const [frameH, frameW] = sizeHW;
  const screenRef = useRef(null);
  const [screenSize, setScreenSize] = useState({ width: 0, height: 0 });
  const [formOpen, setFormOpen] = useState(false);
  const [videoFailed, setVideoFailed] = useState(false);
  const src = paused ? null : videoUrl(relay);

  // Re-request the video whenever the feed (re)connects: an MJPEG <img> never retries after the relay restarts,
  // and the browser reuses its cached image for an unchanged URL, so each attempt gets its own query value.
  const [videoAttempt, setVideoAttempt] = useState(0);
  useEffect(() => setVideoFailed(false), [src]);
  useEffect(() => {
    if (status !== "live") return;
    setVideoFailed(false);
    setVideoAttempt((n) => n + 1);
  }, [status]);

  const showVideo = Boolean(src) && !videoFailed;
  useEffect(() => {
    const screen = screenRef.current;
    if (!screen) return undefined;
    const measure = () => {
      const { width, height } = screen.getBoundingClientRect();
      setScreenSize((prev) => prev.width === width && prev.height === height ? prev : { width, height });
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(screen);
    return () => observer.disconnect();
  }, []);
  const imageRatio = frameW / frameH;
  const fittedWidth = screenSize.width && screenSize.height
    ? Math.min(screenSize.width, screenSize.height * imageRatio)
    : 0;
  const fittedHeight = fittedWidth / imageRatio;
  const stageStyle = fittedWidth
    ? { aspectRatio: `${frameW} / ${frameH}`, width: fittedWidth, height: fittedHeight }
    : { aspectRatio: `${frameW} / ${frameH}`, width: "100%" };

  return (
    <section className="panel recording">
      <div className="panel-head">
        <h2 className="visually-hidden">Meta Recording</h2>
        <span className="mono muted">
          {STATUS_TEXT[status]} · {frameW}×{frameH}
        </span>
      </div>
      <div className="slot">
      <div className="viewport">
        <div
          className="feed-screen"
          ref={screenRef}
        >
          <div className="rec-badge mono">
            <span className={`rec-dot ${paused ? "" : "blink"}`} />
            {paused ? "PAUSED" : "REC"} {formatClock(elapsed)}
          </div>
          <span className="rivet" style={{ top: 10, right: 10 }} />
          <span className="rivet" style={{ bottom: 10, right: 10 }} />
          {!showVideo && (
            <div className="feed-placeholder">
              <svg width="60" height="60" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" aria-hidden="true">
                <circle cx="7" cy="13" r="4" />
                <circle cx="17" cy="13" r="4" />
                <path d="M11 13h2M3 13H2M22 13h-1M5 9l2-4M19 9l-2-4" />
              </svg>
              {paused
                ? "Paused"
                : !relay
                  ? "Waiting for glasses relay"
                  : videoFailed
                    ? "No video from the relay yet"
                    : "Waiting for glasses video…"}
            </div>
          )}

          <div className="stage" style={stageStyle}>
            {showVideo && (
              <img ref={videoRef} crossOrigin="anonymous" className="video" src={`${src}&attempt=${videoAttempt}`} alt="Live view from the Meta glasses" onError={() => setVideoFailed(true)} />
            )}

            {/* Detection boxes, scaled from frame pixels to the drawn frame */}
            <div className="overlay" aria-hidden="true">
              {tracks.map((t) => {
                const [x1, y1, x2, y2] = t.proposal?.box_xyxy_pixels || [0, 0, 0, 0];
                const label = t.gemini_label;
                const name = !label ? "Identifying…" : label === "none" ? "Not a target" : t.name || lookup(label).label;
                return (
                  <div
                    key={t.track_id}
                    className={`det-box ${isDeviceLabel(label) ? "" : "pending"} ${x2 / frameW > 0.6 ? "plate-right" : ""}`}
                    style={{
                      left: `${(x1 / frameW) * 100}%`,
                      top: `${(y1 / frameH) * 100}%`,
                      width: `${((x2 - x1) / frameW) * 100}%`,
                      height: `${((y2 - y1) / frameH) * 100}%`,
                    }}
                  >
                    {/* Brass toolkit frame: corner brackets held by hand tools, ruler ticks along the edges */}
                    <span className="ruler top" />
                    <span className="ruler bottom" />
                    <span className="ruler left" />
                    <span className="ruler right" />
                    <span className="jaw tl" />
                    <span className="jaw tr" />
                    <span className="jaw bl" />
                    <span className="jaw br" />
                    <span className="tool tl"><Wrench /></span>
                    <span className="tool tr"><Hammer /></span>
                    <span className="tool bl"><Screwdriver /></span>
                    <span className="tool br"><Wrench /></span>
                    <span className="det-label mono">
                      <span className="screw" />
                      <Cog size={13} className={`cog tag-cog ${isDeviceLabel(label) ? "" : "fast"}`} />
                      #{t.track_id} {name}
                      {t.proposal?.confidence != null && ` · ${Math.round(t.proposal.confidence * 100)}%`}
                      <span className="screw" />
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {formOpen && (
          <RelayForm
            relay={relay}
            onConnect={(next) => {
              onRelayChange(next);
              setFormOpen(false);
            }}
            onClose={() => setFormOpen(false)}
          />
        )}

        <div className="transport">
          <button type="button" className="round-btn" aria-label={paused ? "Resume feed" : "Pause feed"} onClick={onTogglePause}>
            {paused ? (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M7 5v14l12-7z" /></svg>
            ) : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="6" y="5" width="4" height="14" /><rect x="14" y="5" width="4" height="14" /></svg>
            )}
          </button>
          <div className="mono">Frame {frame?.frame_index ?? "—"}</div>
          <div className="mono muted">
            {tracks.length} track{tracks.length === 1 ? "" : "s"}
          </div>
          <button type="button" className="text-btn relay-btn" onClick={() => setFormOpen((o) => !o)}>
            {relay ? "Relay settings" : "Connect relay"}
          </button>
        </div>
      </div>
      </div>
    </section>
  );
}

export default function App() {
  const [relay, setRelay] = useState(initialRelay);
  const [frame, setFrame] = useState(null);
  const [status, setStatus] = useState(relay ? "connecting" : "mock");
  const [paused, setPaused] = useState(false);
  const [startedAt] = useState(() => Date.now());
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (paused) return undefined;
    setFrame(null);
    if (!relay) {
      setStatus("mock");
      return undefined;
    }
    return subscribe(relay, setFrame, setStatus);
  }, [paused, relay]);

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const changeRelay = (next) => {
    saveRelay(next);
    setRelay(next);
  };

  // Keep the last known frame size so the layout doesn't jump while paused or reconnecting.
  const [sizeHW, setSizeHW] = useState(DEFAULT_SIZE_HW);
  const frameSize = frame?.image_size_hw_pixels;
  useEffect(() => {
    if (!frameSize?.[0] || !frameSize?.[1]) return;
    setSizeHW((prev) => (prev[0] === frameSize[0] && prev[1] === frameSize[1] ? prev : frameSize));
  }, [frameSize?.[0], frameSize?.[1]]);

  // Every part the tutor names and every project confirmed goes into the inventory, with a snapshot from the video.
  const videoRef = useRef(null);
  const inventory = useInventory();
  const { recordLesson } = inventory;
  useEffect(() => {
    if (!paused) recordLesson(frame?.tutor, videoRef.current);
  }, [frame, paused, recordLesson]);

  const recording = (
    <RecordingPanel
      frame={frame}
      sizeHW={sizeHW}
      elapsed={(now - startedAt) / 1000}
      paused={paused}
      onTogglePause={() => setPaused((p) => !p)}
      relay={relay}
      status={paused ? "paused" : status}
      onRelayChange={changeRelay}
      videoRef={videoRef}
    />
  );
  return (
    <div className="app">
      <h1 className="visually-hidden">ScavScrap scan dashboard</h1>
      <div className="dashboard-workspace workspace-frame-desk">
        <div className="workspace-layout">
          {recording}
          <StepsPanel lesson={frame?.tutor} />
          <BreadboardPanel lesson={frame?.tutor} />
        </div>
      </div>
      <Inventory inventory={inventory} />
    </div>
  );
}
