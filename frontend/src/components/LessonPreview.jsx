import React from "react";
import "./lesson-preview.css";

// Local UI copy based on DESIGN.md v0.12. Navigation previews a prepared lesson;
// it neither verifies wiring nor sends session commands to the relay.
export const LESSON_STEPS = [
  {
    title: "Meet the parts",
    action: "Lay out the Arduino UNO R3, breadboard, red LED, 330 Ω resistor, two jumper wires, and compatible USB cable. Keep USB disconnected.",
    why: "The breadboard joins groups of holes without solder. Each component has one job in the light's electrical path.",
    required: "Breadboard · UNO R3 · LED · 330 Ω resistor · 2 jumpers · USB cable",
    focus: "inventory",
  },
  {
    title: "Plan the 5V connection",
    action: "Locate the UNO's 5V header and the first jumper. The reviewed placement diagram will specify the breadboard connection.",
    why: "This jumper will carry supply power to the resistor side of the circuit. Leave USB disconnected during assembly.",
    required: "UNO R3 · breadboard · first jumper",
    focus: "supply",
  },
  {
    title: "Place the 330 Ω resistor",
    action: "The resistor belongs in series between 5V and the LED's anode (+). Use the reviewed diagram for the actual holes.",
    why: "The resistor limits current through the LED. A 220 Ω example elsewhere in the repo is not the planned part for this lesson.",
    required: "330 Ω resistor · breadboard",
    focus: "resistor",
  },
  {
    title: "Orient the LED and ground",
    action: "The LED's anode (+) follows the resistor; its cathode (−) returns through the second jumper to UNO GND. Confirm polarity and hole placement from the reviewed plan.",
    why: "An LED conducts in one direction. The complete path must return to ground.",
    required: "Red LED · second jumper · UNO R3",
    focus: "led",
  },
  {
    title: "Review, then power",
    action: "Review every connection and the LED polarity. Follow the finalized power-up procedure before connecting USB, then observe the external LED.",
    why: "Advancing this preview does not verify the circuit. The expected result is an external LED that stays lit while powered.",
    required: "Completed circuit · compatible USB cable · approved power source",
    focus: "review",
  },
];

function ModelTab() {
  return (
    <div className="lesson-model-tab" role="img" aria-label="Brass breadboard model preview placeholder">
      <span className="lesson-model-label mono">MODEL / PREVIEW</span>
      <svg viewBox="0 0 100 100" aria-hidden="true">
        <circle cx="50" cy="51" r="37" fill="none" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="50" cy="51" r="31" fill="none" stroke="currentColor" strokeWidth=".65" strokeDasharray="2 3" />
        <rect x="35" y="31" width="30" height="40" rx="2" fill="none" stroke="currentColor" strokeWidth="1.4" />
        <path d="M38 37h24M38 65h24M43 42v18M50 42v18M57 42v18" fill="none" stroke="currentColor" strokeWidth=".7" />
        {[43, 50, 57].flatMap((x) => [45, 51, 57].map((y) => <circle key={`${x}-${y}`} cx={x} cy={y} r="1" fill="currentColor" />))}
      </svg>
    </div>
  );
}

export function StepsPanel({ stepIndex, onStepChange }) {
  const step = LESSON_STEPS[stepIndex];
  return (
    <section className="panel steps" aria-labelledby="steps-heading">
      <div className="lesson-step-layout">
        <div className="lesson-step-main">
          <div className="lesson-step-heading">
            <h2 id="steps-heading">Steps</h2>
            <span className="mono">{stepIndex + 1} / {LESSON_STEPS.length}</span>
          </div>
          <div className="lesson-step-number mono">STEP {stepIndex + 1}</div>
          <h3>{step.title}</h3>
          <p>{step.action}</p>
          <p className="lesson-why">{step.why}</p>
          <div className="lesson-required"><strong>Needed now</strong><span>{step.required}</span></div>
        </div>
        <ModelTab />
      </div>
      <div className="lesson-step-footer">
        <span className="mono">Preview navigation · no wiring verification</span>
        <div className="lesson-step-buttons">
          <button type="button" onClick={() => onStepChange(stepIndex - 1)} disabled={stepIndex === 0}>Back</button>
          <button type="button" onClick={() => onStepChange(stepIndex + 1)} disabled={stepIndex === LESSON_STEPS.length - 1}>Next</button>
        </div>
      </div>
    </section>
  );
}

const holes = Array.from({ length: 16 }, (_, col) =>
  Array.from({ length: 10 }, (_, row) => ({ x: 260 + col * 24, y: 90 + row * 11 + (row >= 5 ? 22 : 0), key: `${col}-${row}` })),
).flat();

const LESSON_PARTS = [
  { name: "Arduino UNO R3", step: 1 },
  { name: "Breadboard", step: 1 },
  { name: "Jumper wire 1", step: 1 },
  { name: "330 Ω resistor", step: 2 },
  { name: "Red LED", step: 3 },
  { name: "Jumper wire 2", step: 3 },
  { name: "USB cable", step: 4 },
];

function PartsList({ stepIndex }) {
  return (
    <aside className="breadboard-parts" aria-label="Lesson parts by step">
      <h3>Parts</h3>
      <p className="mono">Planned use by step</p>
      <ul>
        {LESSON_PARTS.map((part) => {
          const state = stepIndex === 0 ? "inventory" : part.step < stepIndex ? "earlier" : part.step === stepIndex ? "now" : "later";
          const label = { inventory: "Inspect", earlier: "Earlier", now: "Now", later: "Later" }[state];
          return (
            <li className={`part-${state}`} key={part.name}>
              <span>{part.name}</span>
              <small className="mono">{label}</small>
            </li>
          );
        })}
      </ul>
      <p className="parts-note">Step progress does not confirm a part was placed.</p>
    </aside>
  );
}

export function BreadboardPanel({ stepIndex }) {
  const step = LESSON_STEPS[stepIndex];
  return (
    <section className="panel breadboard-panel" aria-labelledby="breadboard-heading">
      <div className="panel-head">
        <h2 id="breadboard-heading">Breadboard Setup</h2>
        <span className="mono muted">ILLUSTRATIVE · STEP {stepIndex + 1}</span>
      </div>
      <div className="breadboard-workspace">
        <PartsList stepIndex={stepIndex} />
        <div className="breadboard-drawing">
        <svg viewBox="0 0 680 275" role="img" aria-labelledby="board-title board-description">
          <title id="board-title">Concept drawing of an Arduino and breadboard</title>
          <desc id="board-description">The current step highlights the circuit stage. Hole positions and wire placement are intentionally unspecified until a reviewed diagram for the actual breadboard is available.</desc>
          <rect x="25" y="72" width="156" height="164" rx="8" className="board-shell" />
          <rect x="38" y="86" width="129" height="136" rx="5" className="board-inner" />
          <rect x="25" y="115" width="17" height="28" rx="2" className="board-port" />
          <rect x="100" y="112" width="40" height="54" rx="3" className="board-chip" />
          <text x="103" y="136" className="board-caption">UNO</text>
          <text x="101" y="150" className="board-caption small">R3</text>
          <text x="56" y="102" className="board-caption">5V</text>
          <text x="56" y="204" className="board-caption">GND</text>
          {[0, 1, 2, 3, 4].map((i) => <rect key={`uno-pin-${i}`} x={150} y={103 + i * 18} width="11" height="7" className="board-pin" />)}
          <rect x="225" y="45" width="427" height="200" rx="9" className="breadboard-shell" />
          <path d="M246 66H632 M246 227H632" className={`breadboard-rail ${step.focus === "supply" || step.focus === "review" ? "is-current" : ""}`} />
          <path d="M246 143H632" className="breadboard-channel" />
          {holes.map((hole) => <circle key={hole.key} cx={hole.x} cy={hole.y} r="2.6" className="breadboard-hole" />)}
          <text x="239" y="36" className="board-caption">SOLDERLESS BREADBOARD</text>
          <text x="629" y="39" className="board-caption small" textAnchor="end">CONCEPT VIEW</text>
          <text x="240" y="264" className="board-caption small">Terminal groups shown for orientation, not placement.</text>
          <path d="M180 105H216 M180 202H216" className="board-guide" />
          <text x="187" y="94" className={`board-caption ${step.focus === "supply" || step.focus === "review" ? "is-current" : ""}`}>5V</text>
          <text x="185" y="218" className={`board-caption ${step.focus === "led" || step.focus === "review" ? "is-current" : ""}`}>GND</text>
        </svg>
        </div>
      </div>
      <div className="circuit-reference" aria-label="Specified series circuit path">
        <span className={step.focus === "supply" || step.focus === "review" ? "is-current" : ""}>UNO 5V</span>
        <b aria-hidden="true">→</b>
        <span className={step.focus === "resistor" || step.focus === "review" ? "is-current" : ""}>330 Ω resistor</span>
        <b aria-hidden="true">→</b>
        <span className={step.focus === "led" || step.focus === "review" ? "is-current" : ""}>LED anode (+) → cathode (−)</span>
        <b aria-hidden="true">→</b>
        <span className={step.focus === "led" || step.focus === "review" ? "is-current" : ""}>UNO GND</span>
      </div>
      <p className="breadboard-note">Concept preview only. Exact holes, connection review, and power-up procedure need the prepared plan for the confirmed breadboard. Keep USB disconnected during assembly.</p>
    </section>
  );
}
