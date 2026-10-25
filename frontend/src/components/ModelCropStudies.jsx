import React from "react";
import "./model-crop-studies.css";

const CROPS = [
  {
    id: "outer",
    title: "Outer gold edge",
    note: "Preserves the complete outside of the brass rim.",
    scale: 1.065,
  },
  {
    id: "center",
    title: "Centered gold edge",
    note: "Cuts at the rim's outside edge for a clean circle.",
    scale: 1.078,
  },
  {
    id: "tight",
    title: "Tight gold edge",
    note: "Trims a little of the outer brass, keeping its gold outline visible.",
    scale: 1.09,
  },
];

export default function ModelCropStudies() {
  return (
    <section className="model-crop-studies" aria-labelledby="model-crop-heading">
      <div className="model-crop-intro">
        <span className="mono">TEMPORARY DISPLAY · CROP STUDIES</span>
        <h2 id="model-crop-heading">Circular model preview</h2>
        <p>Three precise trims of the same brass circle. Each keeps the gold rim at the edge; the preview in Steps stays as it is.</p>
      </div>
      <div className="model-crop-grid">
        {CROPS.map((crop, index) => (
          <figure className="model-crop-card" key={crop.id}>
            <div className="model-crop-window" style={{ "--crop-scale": crop.scale }}>
              <hologram-display device="breadboard" variant="drafting" compact="" />
            </div>
            <figcaption>
              <span className="mono">0{index + 1} / 03</span>
              <h3>{crop.title}</h3>
              <p>{crop.note}</p>
            </figcaption>
          </figure>
        ))}
      </div>
    </section>
  );
}
