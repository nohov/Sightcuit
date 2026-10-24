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

// Layout constants for sizing the recording panel around the video (px).
const PANEL_CHROME_W = 46; // panel padding 2×18 + panel border 2×2 + viewport border 2×3
const VIEWPORT_CHROME_H = 6 + 68; // viewport border 2×3 + transport bar
// Room the other panels keep beside the recording: in the landscape layout the
// model + measurements panels share its row; in the portrait layout the whole
// right-hand column sits beside it.
const SIDE_SPACE = {
  landscape: { gaps: 2 * 18, minW: 500 },
  portrait: { gaps: 18, minW: 760 },
};
const COMPACT_BELOW = 1100;

// Measures the height the recording panel can use and the width of its row.
function useRecordingSpace() {
  const ref = useRef(null);
  const [space, setSpace] = useState({ slotH: 0, rowW: 0 });
  useEffect(() => {
    const section = ref.current;
    const slot = section?.querySelector(".slot");
    const row = section?.parentElement;
    if (!slot || !row) return undefined;
    const measure = () => setSpace({ slotH: slot.clientHeight, rowW: row.clientWidth });
    const observer = new ResizeObserver(measure);
    observer.observe(slot);
    observer.observe(row);
    measure();
    return () => observer.disconnect();
  }, []);
  return [ref, space];
}

// Video size that fills the available height at the frame's aspect ratio,
// narrowed if it would squeeze the side panels.
function fitScreen({ slotH, rowW }, ratio, layout) {
  const compact = rowW > 0 && rowW < COMPACT_BELOW;
  const side = SIDE_SPACE[layout];
  let screenH = Math.max(0, slotH - VIEWPORT_CHROME_H);
  let screenW = screenH * ratio;
  const maxW = Math.max(160, rowW - side.gaps - side.minW - PANEL_CHROME_W);
  if (screenW > maxW) {
    screenW = maxW;
    screenH = screenW / ratio;
  }
  return { screenW, screenH, panelW: screenW + PANEL_CHROME_W, compact };
}

function RecordingPanel({ frame, sizeHW, layout, elapsed, paused, onTogglePause, relay, status, onRelayChange }) {
  const tracks = frame?.tracks || [];
  const [frameH, frameW] = sizeHW;
  const [sectionRef, space] = useRecordingSpace();
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

  // Size the recording box to the video's own shape, so there are no bars beside or above it.
  const ratio = frameW / frameH;
  const { screenW, screenH, panelW, compact } = fitScreen(space, ratio, layout);

  const showVideo = Boolean(src) && !videoFailed;

  return (
    <section className="panel recording" ref={sectionRef} style={compact ? undefined : { flex: "0 0 auto", width: panelW }}>
      <div className="panel-head">
        <h2>Meta Recording</h2>
        <span className="mono muted">
          {STATUS_TEXT[status]} · {frameW}×{frameH}
        </span>
      </div>
      <div className="slot">
      <div className="viewport">
        <div
          className="feed-screen"
          style={compact ? { width: "100%", aspectRatio: `${frameW} / ${frameH}` } : { width: screenW, height: screenH }}
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
                  ? "Meta glasses video feed (mock detections)"
                  : videoFailed
                    ? "No video from the relay yet"
                    : "Waiting for glasses video…"}
            </div>
          )}

          <div className="stage">
            {showVideo && (
              <img className="video" src={`${src}&attempt=${videoAttempt}`} alt="Live view from the Meta glasses" onError={() => setVideoFailed(true)} />
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

const MAX_DEVICES = 3; // more than this would make every panel too small to read
const TOP_METALS = 3;

// One entry per device in view (labelled tracks, most confident first).
function devicesInView(frame) {
  const labelled = (frame?.tracks || []).filter((t) => isDeviceLabel(t.gemini_label));
  labelled.sort((a, b) => (b.proposal?.confidence ?? 0) - (a.proposal?.confidence ?? 0));
  return labelled.slice(0, MAX_DEVICES).map((track) => {
    const id = track.gemini_label;
    const device = lookup(id);
    return {
      key: track.track_id,
      id,
      track,
      device,
      known: Boolean(DEVICES[id]),
      title: track.name || (DEVICES[id] ? device.label : id),
    };
  });
}

function hiddenCount(frame) {
  const n = (frame?.tracks || []).filter((t) => isDeviceLabel(t.gemini_label)).length;
  return Math.max(0, n - MAX_DEVICES);
}

// Small "#3 Apple MacBook" caption shown above each device's section when several are in view.
const DeviceTag = ({ entry }) => (
  <div className="device-tag mono">
    #{entry.key} {entry.title}
  </div>
);

const MoreNote = ({ count }) =>
  count > 0 ? <div className="more-note mono">+{count} more in view</div> : null;

function ModelPanel({ entries, more }) {
  const multi = entries.length > 1;
  const shown = entries.length ? entries : [null];
  return (
    <section className="panel model">
      <div className="panel-head">
        <h2>Automaton Model</h2>
        <span className="mono muted">{entries.length ? (multi ? `${entries.length} devices` : entries[0].title) : "—"}</span>
      </div>
      <div className={`porthole-wrap ${multi ? "multi" : ""}`}>
        {shown.map((entry) => (
          <figure className="porthole-item" key={entry ? entry.key : "none"}>
            <div className="porthole" role="img" aria-label={`Rotating model of ${entry ? entry.title : "an unknown device"}`}>
              <div className="model-scale">
                <DeviceModel id={entry?.known ? entry.id : null} />
              </div>
            </div>
            {multi && <figcaption className="mono">#{entry.key} {entry.device.label}</figcaption>}
          </figure>
        ))}
      </div>
      <MoreNote count={more} />
      <div className="cogs">
        <Cog size={28} className="cog" />
        <Cog size={20} className="cog rev" />
      </div>
    </section>
  );
}

function Gauges({ device }) {
  const labels = ["Width", "Height", "Depth"];
  const volume = device.dims ? (device.dims[0] * device.dims[1] * device.dims[2]) / 1000 : null;
  return (
    <>
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
    </>
  );
}

function MeasurementsPanel({ entries, more }) {
  if (entries.length <= 1) {
    return (
      <section className="panel measurements">
        <h2>Measurements</h2>
        <Gauges device={entries[0]?.device ?? lookup(null)} />
      </section>
    );
  }
  // Several devices: one compact brass plate of figures per device.
  return (
    <section className="panel measurements">
      <h2>Measurements</h2>
      <div className="stack">
        {entries.map((entry) => {
          const { dims, weight } = entry.device;
          return (
            <div className="measure-card" key={entry.key}>
              <DeviceTag entry={entry} />
              <div className="measure-grid">
                {["W", "H", "D"].map((axis, i) => (
                  <div className="mini-gauge" key={axis}>
                    <span className="mono">{dims ? dims[i] : "—"}</span>
                    <span className="mini-axis">{axis} mm</span>
                  </div>
                ))}
                <div className="mini-gauge">
                  <span className="mono">{weight ?? "—"}</span>
                  <span className="mini-axis">g</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <MoreNote count={more} />
    </section>
  );
}

function Particulars({ entry, showTag }) {
  const { device, track, known, id } = entry;
  return (
    <div className="particulars-item">
      {showTag ? <DeviceTag entry={entry} /> : <div className="device-name">{entry.title}</div>}
      <p className="device-desc">
        {track.description
          ? track.description
          : track.name || known
            ? "Writing a description…"
            : `The detector sent "${id}", which this dashboard has no entry for yet. Add it to src/devices.js to show its model and metal data.`}
      </p>
      <div className="facts">
        <div>
          <div className="fact-label">Category</div>
          <div className="fact-value">{device.label}</div>
        </div>
        <div>
          <div className="fact-label">Detector label</div>
          <div className="fact-value mono">{track.gemini_label ?? "—"}</div>
        </div>
        <div>
          <div className="fact-label">Label source</div>
          <div className="fact-value mono">{track.label_source ?? "—"}</div>
        </div>
      </div>
    </div>
  );
}

function ParticularsPanel({ entries, more }) {
  return (
    <section className="panel particulars">
      <h2>Device Particulars</h2>
      {entries.length === 0 ? (
        <>
          <div className="device-name">Scanning…</div>
          <p className="device-desc">Waiting for the detector to label a device in view.</p>
        </>
      ) : (
        <div className={entries.length > 1 ? "split" : "single"}>
          {entries.map((entry) => (
            <Particulars entry={entry} key={entry.key} showTag={entries.length > 1} />
          ))}
        </div>
      )}
      <MoreNote count={more} />
    </section>
  );
}

// The three heaviest metals for a device.
function topMetals(device) {
  return Object.entries(device.metals)
    .sort((a, b) => b[1] - a[1])
    .slice(0, TOP_METALS);
}

function MetalBars({ device }) {
  const metals = topMetals(device);
  if (!metals.length) return <p className="device-desc">No metal data for this device.</p>;
  const max = Math.max(1e-9, ...metals.map(([, g]) => g));
  return (
    <div className="bars">
      {metals.map(([name, grams]) => (
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
  );
}

function AssayPanel({ entries, more }) {
  return (
    <section className="panel assay">
      <div className="panel-head">
        <h2>Metal Assay</h2>
        <span className="mono muted">Top {TOP_METALS} metals</span>
      </div>
      {entries.length === 0 ? (
        <p className="device-desc">No device in view.</p>
      ) : (
        <div className={entries.length > 1 ? "split" : "single"}>
          {entries.map((entry) => (
            <div className="assay-item" key={entry.key}>
              {entries.length > 1 && <DeviceTag entry={entry} />}
              <MetalBars device={entry.device} />
            </div>
          ))}
        </div>
      )}
      <MoreNote count={more} />
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

  // Keep the last known frame size so the layout doesn't jump while paused or reconnecting.
  const [sizeHW, setSizeHW] = useState(DEFAULT_SIZE_HW);
  const frameSize = frame?.image_size_hw_pixels;
  useEffect(() => {
    if (!frameSize?.[0] || !frameSize?.[1]) return;
    setSizeHW((prev) => (prev[0] === frameSize[0] && prev[1] === frameSize[1] ? prev : frameSize));
  }, [frameSize?.[0], frameSize?.[1]]);
  const layout = sizeHW[0] > sizeHW[1] ? "portrait" : "landscape";

  const entries = useMemo(() => devicesInView(frame), [frame]);
  const more = hiddenCount(frame);

  const recording = (
    <RecordingPanel
      frame={frame}
      sizeHW={sizeHW}
      layout={layout}
      elapsed={(now - startedAt) / 1000}
      paused={paused}
      onTogglePause={() => setPaused((p) => !p)}
      relay={relay}
      status={paused ? "paused" : status}
      onRelayChange={changeRelay}
    />
  );
  const modelAndMeasurements = (
    <>
      <ModelPanel entries={entries} more={more} />
      <MeasurementsPanel entries={entries} more={more} />
    </>
  );
  const bottomRow = (
    <div className="row bottom">
      <ParticularsPanel entries={entries} more={more} />
      <AssayPanel entries={entries} more={more} />
    </div>
  );

  // Tall (portrait) video gets a full-height column on the left; wide video
  // shares the top row with the model and measurements.
  return layout === "portrait" ? (
    <div className="app portrait">
      <h1 className="visually-hidden">ScavScrap scan dashboard</h1>
      {recording}
      <div className="side-column">
        <div className="row top">{modelAndMeasurements}</div>
        {bottomRow}
      </div>
    </div>
  ) : (
    <div className="app">
      <h1 className="visually-hidden">ScavScrap scan dashboard</h1>
      <div className="row top">
        {recording}
        {modelAndMeasurements}
      </div>
      {bottomRow}
    </div>
  );
}
