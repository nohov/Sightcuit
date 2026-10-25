// TEMPORARY local design study; remove after a frame is selected.
import React from "react";
import "./temporary-victorian-cards.css";
import rococo from "../assets/frame-studies/gold-rococo.png";

const studies = [
  { id: "rococo", number: "I", title: "Venetian Scroll", material: "Gold leaf · shell crest · tapered acanthus", image: rococo, source: "https://www.metmuseum.org/art/collection/search/461645", sourceLabel: "Reference: The Met — Venetian Rococo frame" },
];

export default function TemporaryVictorianCards() {
  return (
    <section className="victorian-studies" id="victorian-frame-studies" aria-labelledby="victorian-studies-title">
      <header className="victorian-studies-heading">
        <span className="temporary-display-badge">TEMPORARY · FRAME STUDIES</span>
        <h2 id="victorian-studies-title">Earlier Reference — Venetian Scroll</h2>
        <p>The earlier slim frame remains here for comparison. Use the controls above the dashboard to compare the two thicker workspace frames.</p>
        <p className="victorian-study-note">Temporary reference · Illustrative content only.</p>
      </header>
      <div className="victorian-studies-grid">
        {studies.map((study) => (
          <article className={`victorian-study victorian-study--${study.id}`} key={study.id} aria-labelledby={`frame-title-${study.id}`}>
            <div className="victorian-frame">
              <div className="victorian-card-paper">
                <span className="victorian-accession">WORKSHOP ARCHIVE · № 024</span>
                <div className="victorian-rule" aria-hidden="true">✦</div>
                <h3>Material Particulars</h3>
                <p className="victorian-subtitle">An inventory of recovered things</p>
                <svg className="victorian-specimen" viewBox="0 0 160 110" fill="none" stroke="currentColor" aria-hidden="true">
                  <ellipse cx="80" cy="92" rx="51" ry="8" strokeDasharray="2 4" opacity=".5" />
                  <path d="M44 26 112 19 116 72 48 79Z M50 31 106 25 110 67 54 73Z M48 79 116 72 139 88 68 98 24 87Z M24 87 25 91 68 103 139 92 139 88 M55 82 110 77 123 85 68 92Z M69 95 84 93" />
                  <path d="m64 81 13 8m0-10 13 8m0-10 13 8m-46-2 55-7" opacity=".6" />
                  <path d="M18 19v49m-4-45 4-4 4 4M14 64l4 4 4-4M43 10l69-7" opacity=".5" />
                  <circle cx="80" cy="49" r="8" strokeWidth=".7" /><path d="M80 38v22M69 49h22" strokeWidth=".6" />
                </svg>
                <p className="victorian-specimen-name">Portable Computing Apparatus</p>
                <dl className="victorian-ledger">
                  <div><dt>Principal metal</dt><dd>Aluminium</dd></div>
                  <div><dt>Gross weight</dt><dd>1.34 kg</dd></div>
                  <div><dt>Condition</dt><dd>Salvageable</dd></div>
                </dl>
                <p className="victorian-card-foot">SPECIMEN STUDY · DISPLAY ONLY</p>
              </div>
              <img className="victorian-frame-art" src={study.image} alt="" loading="lazy" />
            </div>
            <footer className="victorian-study-caption">
              <span>{study.number}</span>
              <div><h3 id={`frame-title-${study.id}`}>{study.title}</h3><p>{study.material}</p><a className="victorian-source" href={study.source} target="_blank" rel="noreferrer">{study.sourceLabel}</a></div>
            </footer>
          </article>
        ))}
      </div>
    </section>
  );
}
