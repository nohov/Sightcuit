// Inventory drawer: a brass tab at the bottom of the dashboard slides up a
// panel with two tabs — My Parts (the kit, with glasses snapshots once seen)
// and My Projects (each project, with a Completed badge next to its name once
// the lesson has reached its final step).

import React, { useEffect, useRef, useState } from "react";
import { KIT } from "../inventory.js";
import { LESSON_STEPS } from "./LessonPreview.jsx";
import "./inventory.css";

export const LED_PROJECT = {
  id: "red-led",
  title: "Light up a red LED",
  parts: ["Arduino UNO R3", "Breadboard", "330 Ω resistor", "Red LED", "2 jumper wires", "USB cable"],
};

const PROJECTS = [LED_PROJECT];

const when = (ms) =>
  new Date(ms).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

const Chevron = ({ up }) => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d={up ? "M6 15l6-6 6 6" : "M6 9l6 6 6-6"} />
  </svg>
);

function timeAgo(ms) {
  const s = Math.max(0, Math.round((Date.now() - ms) / 1000));
  if (s < 60) return "just now";
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} h ago`;
  return new Date(ms).toLocaleDateString();
}

// Simple drawings for the two parts without Fritzing artwork.
function PartDrawing({ id }) {
  if (id === "jumper") {
    return (
      <svg viewBox="0 0 120 80" className="inv-drawing" aria-hidden="true">
        <path d="M14 22 C40 2, 80 60, 106 30" stroke="#d4553a" strokeWidth="6" fill="none" strokeLinecap="round" />
        <path d="M14 52 C44 30, 76 84, 106 58" stroke="#c9a24a" strokeWidth="6" fill="none" strokeLinecap="round" />
        {[[14, 22], [106, 30], [14, 52], [106, 58]].map(([x, y]) => (
          <rect key={`${x}-${y}`} x={x - 5} y={y - 4} width="10" height="8" rx="1" fill="#2a1f14" stroke="#eadbc0" strokeWidth="1.2" />
        ))}
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 120 80" className="inv-drawing" aria-hidden="true">
      <path d="M12 40 H66" stroke="#2a1f14" strokeWidth="7" strokeLinecap="round" />
      <path d="M12 40 H66" stroke="#6b5a44" strokeWidth="5" strokeLinecap="round" />
      <rect x="66" y="27" width="26" height="26" rx="3" fill="#3a2a1a" stroke="#c9a24a" strokeWidth="2" />
      <rect x="92" y="31" width="16" height="18" rx="1" fill="#b9b9b9" stroke="#555" />
      <rect x="96" y="35" width="8" height="10" fill="#555" />
    </svg>
  );
}

function PartCard({ part, seen, onForget }) {
  const status = part.notDetected
    ? "The glasses can't spot this one yet — check it yourself."
    : seen
      ? `Spotted ${seen.sightings}× · ${timeAgo(seen.lastSeen)}`
      : "Not spotted by the glasses yet.";
  return (
    <article className={`inv-card ${seen ? "seen" : ""}`}>
      <div className="inv-thumb">
        {seen?.thumb ? (
          <img src={seen.thumb} alt={`Glasses snapshot of the ${part.name}`} />
        ) : part.art ? (
          <img className="inv-art" src={part.art} alt={`Drawing of the ${part.name}`} />
        ) : (
          <PartDrawing id={part.id} />
        )}
        <span className={`inv-badge mono ${seen ? "on" : ""}`}>{seen?.thumb ? "SNAPSHOT" : seen ? "SEEN" : "DRAWING"}</span>
        <span className="inv-rivet tl" />
        <span className="inv-rivet tr" />
        <span className="inv-rivet bl" />
        <span className="inv-rivet br" />
      </div>
      <div className="inv-plate mono">
        {part.name}
        {part.qty > 1 && ` ×${part.qty}`}
      </div>
      <div className="inv-body">
        <div className={`inv-status mono ${seen ? "on" : ""}`}>{status}</div>
        <p className="inv-desc">{part.what}</p>
        <div className="inv-used">
          Used in <span>{LED_PROJECT.title}</span>
        </div>
      </div>
      {seen && (
        <button type="button" className="inv-remove" aria-label={`Forget the ${part.name} sighting`} onClick={() => onForget(part.id)}>
          ×
        </button>
      )}
    </article>
  );
}

function PartsTab({ parts, onForget }) {
  const seenCount = KIT.filter((p) => parts[p.id]).length;
  return (
    <>
      <p className="inv-note">
        {seenCount} of {KIT.length} parts spotted. A part is marked only when the glasses detect it live; the first
        sighting saves a snapshot.
      </p>
      <div className="inv-grid">
        {KIT.map((part) => (
          <PartCard key={part.id} part={part} seen={parts[part.id]} onForget={onForget} />
        ))}
      </div>
    </>
  );
}

function ProjectCard({ project, stepIndex, completedAt, onReset }) {
  const done = Boolean(completedAt);
  return (
    <article className={`inv-project ${done ? "done" : ""}`}>
      <div className="inv-project-head">
        <div className="inv-project-title">
          {project.title}
          {done && (
            <span className="inv-complete" role="status">
              <span aria-hidden="true">✓</span> Completed
            </span>
          )}
        </div>
        <div className="mono muted">
          {done ? `Completed ${when(completedAt)}` : `Step ${stepIndex + 1} of ${LESSON_STEPS.length}`}
        </div>
      </div>

      <ol className="inv-steps">
        {LESSON_STEPS.map((s, i) => {
          const state = done || i < stepIndex ? "done" : i === stepIndex ? "now" : "";
          return (
            <li key={s.title} className={state}>
              <span className="inv-step-dot mono">{state === "done" ? "✓" : i + 1}</span>
              <span>{s.title}</span>
            </li>
          );
        })}
      </ol>

      <div className="inv-parts-used">
        {project.parts.map((p) => (
          <span key={p}>{p}</span>
        ))}
      </div>

      {done && (
        <button type="button" className="inv-reset" onClick={() => onReset(project.id)}>
          Reset completion
        </button>
      )}
    </article>
  );
}

export default function Inventory({ inventory, completed, onReset, stepIndex }) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState("parts");
  const closeRef = useRef(null);
  const tabRef = useRef(null);
  const seenCount = KIT.filter((p) => inventory.parts[p.id]).length;
  const doneCount = PROJECTS.filter((p) => completed[p.id]).length;

  useEffect(() => {
    if (!open) return undefined;
    closeRef.current?.focus();
    const onKey = (e) => e.key === "Escape" && close();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  function close() {
    setOpen(false);
    tabRef.current?.focus();
  }

  return (
    <>
      <button
        ref={tabRef}
        type="button"
        className={`inv-tab ${open ? "hidden" : ""}`}
        aria-expanded={open}
        aria-controls="inventory-drawer"
        onClick={() => setOpen(true)}
      >
        <Chevron up />
        Inventory
        <span className="inv-count mono">{seenCount + doneCount}</span>
      </button>

      <div className={`inv-backdrop ${open ? "open" : ""}`} onClick={close} aria-hidden="true" />
      <section
        id="inventory-drawer"
        className={`inv-drawer ${open ? "open" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label="Inventory"
        aria-hidden={!open}
        inert={open ? undefined : ""}
      >
        <header className="inv-head">
          <div>
            <h2>Inventory</h2>
            <div className="mono muted">
              {seenCount}/{KIT.length} parts spotted · {doneCount}/{PROJECTS.length} projects completed
            </div>
          </div>
          <div className="inv-tabs" role="tablist" aria-label="Inventory sections">
            {[
              ["parts", "My Parts"],
              ["projects", "My Projects"],
            ].map(([id, label]) => (
              <button key={id} type="button" role="tab" aria-selected={tab === id} className={tab === id ? "on" : ""} onClick={() => setTab(id)}>
                {label}
              </button>
            ))}
          </div>
          <button ref={closeRef} type="button" className="text-btn primary inv-close" onClick={close}>
            <Chevron />
            Back to lesson
          </button>
        </header>

        <div className="inv-scroll" role="tabpanel">
          {tab === "parts" ? (
            <PartsTab parts={inventory.parts} onForget={inventory.forgetPart} />
          ) : (
            <>
              {PROJECTS.map((p) => (
                <ProjectCard key={p.id} project={p} stepIndex={stepIndex} completedAt={completed[p.id]} onReset={onReset} />
              ))}
              <p className="inv-note">A project marks itself complete when you reach its last step.</p>
            </>
          )}
        </div>
      </section>
    </>
  );
}
