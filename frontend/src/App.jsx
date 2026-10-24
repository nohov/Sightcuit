import { useEffect, useMemo, useState } from "react";
import { DEVICES, DEVICE_IDS, lookup } from "./devices.js";
import { FRAME_HEIGHT, FRAME_WIDTH, subscribe } from "./feed.js";
import DeviceModel from "./components/DeviceModels.jsx";

const Cog = ({ size = 28, className = "cog", color = "currentColor" }) => (
  <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.6" strokeLinecap="round" aria-hidden="true">
    <circle cx="12" cy="12" r="3" />
    <circle cx="12" cy="12" r="7" />
    <path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1 7 17M17 7l2.1-2.1" />
  </svg>
);

function formatClock(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  const hh = String(Math.floor(s / 3600)).padStart(2, "0");
  const mm = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
  const ss = String(s % 60).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
}

// The device the dashboard describes: the most confident labelled track.
function primaryTrack(frame) {
  const labelled = (frame?.tracks || []).filter((t) => t.gemini_label);
  labelled.sort((a, b) => (b.proposal?.confidence ?? 0) - (a.proposal?.confidence ?? 0));
  return labelled[0] || null;
}

function RecordingPanel({ frame, elapsed, paused, onTogglePause }) {
  const tracks = frame?.tracks || [];
  return (
    <section className="panel recording">
      <div className="panel-head">
        <h2>Meta Recording</h2>
        <span className="mono muted">Ocular Feed · {FRAME_WIDTH}×{FRAME_HEIGHT}</span>
      </div>
      <div className="viewport">
        <div className="rec-badge mono">
          <span className={`rec-dot ${paused ? "" : "blink"}`} />
          {paused ? "PAUSED" : "REC"} {formatClock(elapsed)}
        </div>
        <span className="rivet" style={{ top: 10, right: 10 }} />
        <span className="rivet" style={{ bottom: 74, right: 10 }} />

        <div className="feed-placeholder">
          <svg width="60" height="60" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" aria-hidden="true">
            <circle cx="7" cy="13" r="4" />
            <circle cx="17" cy="13" r="4" />
            <path d="M11 13h2M3 13H2M22 13h-1M5 9l2-4M19 9l-2-4" />
          </svg>
          Meta glasses video feed
        </div>

        {/* Detection boxes, scaled from frame pixels to the viewport */}
        <div className="overlay" aria-hidden="true">
          {tracks.map((t) => {
            const [x1, y1, x2, y2] = t.proposal?.box_xyxy_pixels || [0, 0, 0, 0];
            const name = t.gemini_label ? lookup(t.gemini_label).label : "Identifying…";
            return (
              <div
                key={t.track_id}
                className={`det-box ${t.gemini_label ? "" : "pending"}`}
                style={{
                  left: `${(x1 / FRAME_WIDTH) * 100}%`,
                  top: `${(y1 / FRAME_HEIGHT) * 100}%`,
                  width: `${((x2 - x1) / FRAME_WIDTH) * 100}%`,
                  height: `${((y2 - y1) / FRAME_HEIGHT) * 100}%`,
                }}
              >
                <span className="det-label mono">
                  #{t.track_id} {name}
                  {t.proposal?.confidence != null && ` · ${Math.round(t.proposal.confidence * 100)}%`}
                </span>
              </div>
            );
          })}
        </div>

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
  const [frame, setFrame] = useState(null);
  const [paused, setPaused] = useState(false);
  const [pinned, setPinned] = useState("auto"); // "auto" follows the feed
  const [startedAt] = useState(() => Date.now());
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (paused) return undefined;
    return subscribe(setFrame);
  }, [paused]);

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const track = useMemo(() => primaryTrack(frame), [frame]);
  const activeId = pinned === "auto" ? track?.gemini_label ?? null : pinned;
  const known = Boolean(activeId && DEVICES[activeId]);
  const device = lookup(activeId);

  const tabs = [{ id: "auto", label: "Auto" }, ...DEVICE_IDS.map((id) => ({ id, label: DEVICES[id].label }))];

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <Cog size={40} className="cog accent-stroke" />
          <div>
            <div className="wordmark">SCAVSCRAP</div>
            <div className="subtitle">Salvage Survey Engine · Session No. 001</div>
          </div>
        </div>

        <nav className="tabs" aria-label="Device class">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              aria-pressed={pinned === t.id}
              className={`tab ${pinned === t.id ? "on" : ""}`}
              onClick={() => setPinned(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>

        <div className="actions">
          <span className="status-pill mono">
            <span className={`rec-dot ${paused ? "" : "blink"}`} />
            {paused ? "PAUSED" : "RECORDING"}
          </span>
          <button type="button" className="primary-btn">Export Ledger</button>
        </div>
      </header>

      <div className="row top">
        <RecordingPanel frame={frame} elapsed={(now - startedAt) / 1000} paused={paused} onTogglePause={() => setPaused((p) => !p)} />
        <ModelPanel id={known ? activeId : null} device={device} />
        <MeasurementsPanel device={device} />
      </div>

      <div className="row bottom">
        <ParticularsPanel device={device} track={pinned === "auto" ? track : null} known={known} activeId={activeId} />
        <AssayPanel device={device} />
      </div>
    </div>
  );
}
