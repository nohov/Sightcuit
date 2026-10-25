import React from "react";
import "./lesson-preview.css";
import "../../../holograms-local/hologram-display.js";
import BreadboardScene from "./BreadboardScenes.jsx";
import { detectedPreview } from "../componentPreview.js";

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

const COMPONENT_MODELS = [
  ["uno", "Arduino UNO R3"], ["breadboard", "Breadboard"],
  ["led", "Red LED"], ["resistor", "330 Ω resistor"], ["jumper", "Male-to-male jumpers ×2"],
];

function ModelTab({ selected, observation, automatic }) {
  const modelName = COMPONENT_MODELS.find(([id]) => id === selected)?.[1] ?? "Awaiting component";
  return (
    <div className="lesson-model-tab">
      <div className={`lesson-model-gauge ${selected ? "is-model" : ""}`}>
        {selected ? <hologram-display device={selected} variant="drafting" compact="" /> : (
          <div className="lesson-model-waiting">Waiting for one supported component detection</div>
        )}
      </div>
      <p className="lesson-model-name">{modelName}</p>
      <p className="lesson-model-caption" role="status">
        {automatic ? (observation ? `Detected: ${observation.observed_label}` : "Auto · no unambiguous live component") : "Manual component preview"}
      </p>
    </div>
  );
}

export function ModelPreviewControls({ mode, onModeChange }) {
  return (
    <section className="model-preview-controls" aria-label="Temporary model design controls">
      <span className="mono">TEMPORARY · MODEL PREVIEW CONTROLS</span>
      <div className="lesson-model-switcher" role="group" aria-label="Component model preview">
        <button type="button" aria-pressed={mode === "auto"} onClick={() => onModeChange("auto")}>Auto · detected</button>
        {COMPONENT_MODELS.map(([id, label]) => (
          <button key={id} type="button" aria-pressed={mode === id} onClick={() => onModeChange(id)}>{label}</button>
        ))}
      </div>
    </section>
  );
}

export function StepsPanel({ stepIndex, onStepChange, frame, detectionLive = false, detectionFresh = false, mode = "auto" }) {
  const step = LESSON_STEPS[stepIndex];
  const observation = detectedPreview(frame, detectionLive, detectionFresh);
  const automatic = mode === "auto";
  const selected = automatic ? observation?.model_id : mode;
  return (
    <section className="panel steps" aria-labelledby="steps-heading">
      <div className="lesson-step-layout">
        <div className="lesson-step-main">
          <h2 id="steps-heading" className="lesson-current-step">Step {stepIndex + 1}</h2>
          <h3>{step.title}</h3>
          <p>{step.action}</p>
          <p className="lesson-why">{step.why}</p>
          <div className="lesson-required"><strong>Needed now</strong><span>{step.required}</span></div>
        </div>
        <ModelTab selected={selected} observation={observation} automatic={automatic} />
      </div>
      <div className="lesson-step-footer">
        <div className="lesson-step-buttons">
          <button type="button" onClick={() => onStepChange(stepIndex - 1)} disabled={stepIndex === 0}>Back</button>
          <button type="button" onClick={() => onStepChange(stepIndex + 1)} disabled={stepIndex === LESSON_STEPS.length - 1}>Next</button>
        </div>
      </div>
    </section>
  );
}
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

      <ul>
        {LESSON_PARTS.map((part) => {
          const state = stepIndex === 0 ? "inventory" : part.step < stepIndex ? "earlier" : part.step === stepIndex ? "now" : "later";
          return (
            <li className={`part-${state}`} key={part.name}
              aria-label={`${part.name}${state === "earlier" ? ": used in an earlier step" : state === "now" ? ": needed in this step" : ""}`}>
              <span>{part.name}</span>

            </li>
          );
        })}
      </ul>

    </aside>
  );
}

export function BreadboardPanel({ stepIndex }) {
  return (
    <section className="panel breadboard-panel" aria-label="Breadboard setup">
      <div className="breadboard-workspace">
        <PartsList stepIndex={stepIndex} />
        <div className="breadboard-drawing breadboard-drawing-simple">
          <BreadboardScene stepIndex={stepIndex} variant="original" />
        </div>
      </div>
    </section>
  );
}
