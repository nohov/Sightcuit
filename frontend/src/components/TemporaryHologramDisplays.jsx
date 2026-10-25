// TEMPORARY display-only review area. Remove this component and its App.jsx
// mount when the design review is finished. No feed or recognition inputs.
import React from "react";
import "../../../holograms-local/hologram-display.js";
import "./temporary-hologram-displays.css";
import TemporaryVictorianCards from "./TemporaryVictorianCards.jsx";
import designSpecUrl from "../../../DESIGN.md?url";

const DISPLAYS = [
  ["uno", "Arduino UNO R3 · quantity 1"],
  ["breadboard", "Solderless breadboard · quantity 1"],
  ["led", "Red LED · quantity 1"],
  ["resistor", "330 Ω resistor · quantity 1"],
  ["jumper", "Male-to-male jumper wires · quantity 2"],
];

export default function TemporaryHologramDisplays() {
  return (
    <>
    <section id="temporary-hologram-displays" className="temporary-holograms" aria-labelledby="drafting-grid-heading">
      <header className="temporary-holograms-heading">
        <span className="temporary-display-badge">TEMPORARY · DISPLAY ONLY</span>
        <h2 id="drafting-grid-heading">Drafting Grid — Five Circuit Components</h2>
        <p>
          Original rotating 3D component studies with pen-and-ink geometry. Adjust each backdrop
          from −100 to +100. These are illustrative models, not live detections or manufacturing drawings.
        </p>
        <p>Source: <a href={designSpecUrl} target="_blank" rel="noreferrer">DESIGN.md v0.12 — First demo: USB-powered red LED, inventory table</a>.
          The spec includes a sixth item type, the compatible USB cable; it remains required setup equipment and is not one of these five models.</p>
        <p className="temporary-holograms-instructions">
          Hover or focus a display to spread its parts and show labels. Click or tap to hold it open.
        </p>
      </header>
      <div className="temporary-holograms-grid" role="group" aria-labelledby="drafting-grid-heading">
        {DISPLAYS.map(([id, label]) => (
          <article className="temporary-hologram-card" key={`drafting-${id}`} aria-labelledby={`drafting-model-${id}`}>
            <div className="temporary-hologram-card-heading">
              <h3 id={`drafting-model-${id}`}>{label} — Drafting grid</h3>
              <span className="temporary-display-badge">TEMPORARY DISPLAY · DRAFTING GRID</span>
            </div>
            <hologram-display device={id} variant="drafting" />
            <p className="temporary-hologram-caption">Illustrative animation only · Not a live device</p>
          </article>
        ))}
      </div>
    </section>
    <TemporaryVictorianCards />
    </>
  );
}
