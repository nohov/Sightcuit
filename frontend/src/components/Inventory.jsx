// Inventory drawer: a brass tab at the bottom of the dashboard slides up a
// panel with two tabs — My Parts (every part the tutor has named, with a
// glasses snapshot from the first sighting) and My Projects (every build the
// user confirmed, with a Completed badge once the tutor reports it finished).

import React, { useEffect, useRef, useState } from "react";
import { partKey } from "../inventory.js";
import "./inventory.css";

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

function PartCard({ id, part, usedIn, onForget }) {
  return (
    <article className="inv-card seen">
      <div className="inv-thumb">
        {part.thumb ? (
          <img src={part.thumb} alt={`Glasses snapshot when the ${part.name} was named`} />
        ) : (
          <div className="inv-nophoto mono">No snapshot</div>
        )}
        <span className="inv-badge mono on">{part.thumb ? "SNAPSHOT" : "SEEN"}</span>
        <span className="inv-rivet tl" />
        <span className="inv-rivet tr" />
        <span className="inv-rivet bl" />
        <span className="inv-rivet br" />
      </div>
      <div className="inv-plate mono">{part.name}</div>
      <div className="inv-body">
        <div className="inv-status mono on">
          Seen {part.sightings}× · {timeAgo(part.lastSeen)}
        </div>
        {usedIn.length > 0 && (
          <div className="inv-used">
            Used in <span>{usedIn.join(", ")}</span>
          </div>
        )}
      </div>
      <button type="button" className="inv-remove" aria-label={`Forget the ${part.name}`} onClick={() => onForget(id)}>
        ×
      </button>
    </article>
  );
}

function PartsTab({ parts, projects, onForget }) {
  const entries = Object.entries(parts).sort(([, a], [, b]) => b.lastSeen - a.lastSeen);
  const usedIn = (key) =>
    Object.values(projects).filter((p) => p.parts.some((name) => partKey(name) === key)).map((p) => p.title);
  return (
    <>
      <p className="inv-note">
        {entries.length
          ? `${entries.length} part${entries.length === 1 ? "" : "s"} named so far. Each is added when the tutor names it; the first time saves a snapshot.`
          : 'Nothing yet. Look at a part and ask "what is this?".'}
      </p>
      <div className="inv-grid">
        {entries.map(([key, part]) => (
          <PartCard key={key} id={key} part={part} usedIn={usedIn(key)} onForget={onForget} />
        ))}
      </div>
    </>
  );
}

function ProjectCard({ project, onReset }) {
  const done = Boolean(project.completedAt);
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
          {done ? `Completed ${when(project.completedAt)}` : `Step ${project.step + 1} of ${project.steps.length}`}
        </div>
      </div>

      <ol className="inv-steps">
        {project.steps.map((say, i) => {
          const state = done || i < project.step ? "done" : i === project.step ? "now" : "";
          return (
            <li key={i} className={state}>
              <span className="inv-step-dot mono">{state === "done" ? "✓" : i + 1}</span>
              <span>{say}</span>
            </li>
          );
        })}
      </ol>

      {project.parts.length > 0 && (
        <div className="inv-parts-used">
          {project.parts.map((p) => (
            <span key={p}>{p}</span>
          ))}
        </div>
      )}

      {done && (
        <button type="button" className="inv-reset" onClick={() => onReset(project.title)}>
          Reset completion
        </button>
      )}
    </article>
  );
}

export default function Inventory({ inventory }) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState("parts");
  const closeRef = useRef(null);
  const tabRef = useRef(null);
  const projects = Object.values(inventory.projects).sort((a, b) => b.started - a.started);
  const partCount = Object.keys(inventory.parts).length;
  const doneCount = projects.filter((p) => p.completedAt).length;

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
        <span className="inv-count mono">{partCount + doneCount}</span>
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
              {partCount} part{partCount === 1 ? "" : "s"} named · {doneCount}/{projects.length} projects completed
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
            <PartsTab parts={inventory.parts} projects={inventory.projects} onForget={inventory.forgetPart} />
          ) : (
            <>
              {projects.map((p) => (
                <ProjectCard key={p.title} project={p} onReset={inventory.resetProject} />
              ))}
              <p className="inv-note">
                {projects.length
                  ? "A project marks itself complete when the tutor reports its last step done."
                  : "No projects yet. Ask what you can make, pick one, and say yes."}
              </p>
            </>
          )}
        </div>
      </section>
    </>
  );
}
