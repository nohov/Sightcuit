import { useEffect, useMemo, useRef, useState } from "react";
import { DEVICES, lookup } from "./devices.js";
import { DEFAULT_SIZE_HW, initialRelay, saveRelay, subscribe, videoUrl } from "./feed.js";
import DeviceModel from "./components/DeviceModels.jsx";
import { Hammer, Screwdriver, Wrench } from "./components/Tools.jsx";

const Cog = ({ size = 28, className = "cog", color = "currentColor" }) => (
  <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.6" strokeLinecap="round" aria-hidden="true">
    <circle cx="12" cy="12" r="3" />
    <circle cx="12" cy="12" r="7" />
    <path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1 7 17M17 7l2.1-2.1" />
  </svg>
);

const STATUS_TEXT = {
  mock: "Mock feed",
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

// The device the dashboard describes: the most confident labelled track.
function primaryTrack(frame) {
  const labelled = (frame?.tracks || []).filter((t) => isDeviceLabel(t.gemini_label));
  labelled.sort((a, b) => (b.proposal?.confidence ?? 0) - (a.proposal?.confidence ?? 0));
  return labelled[0] || null;
}

// Size of the area the frame is drawn into, so boxes line up with the letterboxed video.
function useElementSize() {
  const ref = useRef(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setSize({ width, height });
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return [ref, size];
}

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

function RecordingPanel({ frame, elapsed, paused, onTogglePause, relay, status, onRelayChange }) {
  const tracks = frame?.tracks || [];
  const [frameH, frameW] = frame?.image_size_hw_pixels || DEFAULT_SIZE_HW;
  const [screenRef, screen] = useElementSize();
  const [formOpen, setFormOpen] = useState(false);
  const [videoFailed, setVideoFailed] = useState(false);
  const src = paused ? null : videoUrl(relay);

  // Remount the video whenever the feed (re)connects: an MJPEG <img> never retries after the relay restarts.
  const [videoAttempt, setVideoAttempt] = useState(0);
  useEffect(() => setVideoFailed(false), [src]);
  useEffect(() => {
    if (status !== "live") return;
    setVideoFailed(false);
    setVideoAttempt((n) => n + 1);
  }, [status]);

  // Fit the frame inside the screen area, keeping its aspect ratio.
  const scale = Math.min(screen.width / frameW, screen.height / frameH) || 0;
  const stage = {
    width: frameW * scale,
    height: frameH * scale,
    left: (screen.width - frameW * scale) / 2,
    top: (screen.height - frameH * scale) / 2,
  };
  const showVideo = Boolean(src) && !videoFailed;

  return (
    <section className="panel recording">
      <div className="panel-head">
        <h2>Meta Recording</h2>
        <span className="mono muted">
          {STATUS_TEXT[status]} · {frameW}×{frameH}
        </span>
      </div>
      <div className="viewport">
        <div className="rec-badge mono">
          <span className={`rec-dot ${paused ? "" : "blink"}`} />
          {paused ? "PAUSED" : "REC"} {formatClock(elapsed)}
        </div>
        <span className="rivet" style={{ top: 10, right: 10 }} />
        <span className="rivet" style={{ bottom: 74, right: 10 }} />

        <div className="screen" ref={screenRef}>
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
                  ? "Meta glasses video feed (mock detections)"
                  : videoFailed
                    ? "No video from the relay yet"
                    : "Waiting for glasses video…"}
            </div>
          )}

          <div className="stage" style={stage}>
            {showVideo && (
              <img key={videoAttempt} className="video" src={src} alt="Live view from the Meta glasses" onError={() => setVideoFailed(true)} />
            )}

            {/* Detection boxes, scaled from frame pixels to the drawn frame */}
            <div className="overlay" aria-hidden="true">
              {tracks.map((t) => {
                const [x1, y1, x2, y2] = t.proposal?.box_xyxy_pixels || [0, 0, 0, 0];
                const label = t.gemini_label;
                const name = !label ? "Identifying…" : label === "none" ? "Not a target" : lookup(label).label;
                return (
                  <div
                    key={t.track_id}
                    className={`det-box ${isDeviceLabel(label) ? "" : "pending"}`}
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
    </section>
  );
}

function ModelPanel({ id, device }) {
  return (
    <section className="panel model">
      <div className="panel-head">
        <h2>Automaton Model</h2>
        <span className="mono muted">{device.label}</span>
      </div>
      <div className="porthole-wrap">
        <div className="porthole" role="img" aria-label={`Rotating model of a ${device.label}`}>
          <DeviceModel id={id} />
        </div>
      </div>
      <div className="cogs">
        <Cog size={28} className="cog" />
        <Cog size={20} className="cog rev" />
      </div>
    </section>
  );
}

function MeasurementsPanel({ device }) {
  const labels = ["Width", "Height", "Depth"];
  const volume = device.dims ? (device.dims[0] * device.dims[1] * device.dims[2]) / 1000 : null;
  return (
    <section className="panel measurements">
      <h2>Measurements</h2>
      <div className="gauges">
        {labels.map((label, i) => (
          <div className="gauge-row" key={label}>
            <div className="gauge">
              <div className="mono gauge-value">{device.dims ? device.dims[i] : "—"}</div>
              <div className="gauge-unit">mm</div>
            </div>
            <div className="gauge-label">{label}</div>
          </div>
        ))}
      </div>
      <div className="stat-row first">
        <span>Volume</span>
        <span className="mono">{volume != null ? `${volume.toFixed(1)} cm³` : "—"}</span>
      </div>
      <div className="stat-row">
        <span>Est. weight</span>
        <span className="mono">{device.weight != null ? `${device.weight} g` : "—"}</span>
      </div>
    </section>
  );
}

function ParticularsPanel({ device, track, known, activeId }) {
  const waiting = !activeId;
  return (
    <section className="panel particulars">
      <h2>Device Particulars</h2>
      <div className="device-name">{known ? device.label : waiting ? "Scanning…" : "Unrecognized device"}</div>
      <p className="device-desc">
        {known
          ? "[Short description of the scanned device: type, condition, visible components and anything notable for recovery.]"
          : waiting
            ? "Waiting for the detector to label a device in view."
            : `The detector sent "${activeId}", which this dashboard has no entry for yet. Add it to src/devices.js to show its model and metal data.`}
      </p>
      <div className="facts">
        <div>
          <div className="fact-label">Category</div>
          <div className="fact-value">{device.label}</div>
        </div>
        <div>
          <div className="fact-label">Detector label</div>
          <div className="fact-value mono">{track?.gemini_label ?? "—"}</div>
        </div>
        <div>
          <div className="fact-label">Label source</div>
          <div className="fact-value mono">{track?.label_source ?? "—"}</div>
        </div>
      </div>
    </section>
  );
}

function AssayPanel({ device }) {
  const entries = Object.entries(device.metals);
  const max = Math.max(1e-9, ...entries.map(([, g]) => g));
  const total = entries.reduce((s, [, g]) => s + g, 0);
  return (
    <section className="panel assay">
      <div className="panel-head">
        <h2>Metal Assay</h2>
        <span className="mono accent total">
          Total {entries.length ? (total >= 100 ? total.toFixed(0) : total.toFixed(1)) : "—"} g
        </span>
      </div>
      {entries.length ? (
        <div className="bars">
          {entries.map(([name, grams]) => (
            <div className="bar-item" key={name}>
              <div className="bar-head">
                <span>{name}</span>
                <span className="mono muted">{grams} g</span>
              </div>
              <div className="bar-track">
                <div className="bar-fill" style={{ width: `${Math.max(2, (grams / max) * 100)}%` }} />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="device-desc">No metal data for this device.</p>
      )}
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

  const track = useMemo(() => primaryTrack(frame), [frame]);
  const activeId = track?.gemini_label ?? null;
  const known = Boolean(activeId && DEVICES[activeId]);
  const device = lookup(activeId);

  return (
    <div className="app">
      <h1 className="visually-hidden">ScavScrap scan dashboard</h1>

      <div className="row top">
        <RecordingPanel
          frame={frame}
          elapsed={(now - startedAt) / 1000}
          paused={paused}
          onTogglePause={() => setPaused((p) => !p)}
          relay={relay}
          status={paused ? "paused" : status}
          onRelayChange={changeRelay}
        />
        <ModelPanel id={known ? activeId : null} device={device} />
        <MeasurementsPanel device={device} />
      </div>

      <div className="row bottom">
        <ParticularsPanel device={device} track={track} known={known} activeId={activeId} />
        <AssayPanel device={device} />
      </div>
    </div>
  );
}
