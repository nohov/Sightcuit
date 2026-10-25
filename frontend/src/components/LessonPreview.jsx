import React, { useState } from "react";
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

const COMPONENT_MODELS = [
  ["uno", "Arduino UNO R3"], ["breadboard", "Breadboard"],
  ["led", "Red LED"], ["resistor", "330 Ω resistor"], ["jumper", "Male-to-male jumpers ×2"],
];

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

// Live from the tutor's /events "tutor" field: the picked build's steps (finished ones crossed out) and every
// part the user has had named. Null before the tutor sends anything, e.g. on the mock feed or live_runner.
export function StepsPanel({ lesson }) {
  const steps = lesson?.steps || [];
  const parts = lesson?.parts || [];
  const need = (lesson?.needed || []).filter((item) => !item.have).map((item) => item.part);
  const done = (i) => lesson.finished || i < lesson.step_index;
  return (
    <section className="panel steps" aria-labelledby="steps-heading">
      <div className="lesson-step-layout">
        <div className="lesson-step-main">
          <h2 id="steps-heading" className="lesson-current-step">{lesson?.project || "Steps"}</h2>
          {steps.length ? (
            <ol className="lesson-step-list">
              {steps.map((say, i) => (
                <li key={i} className={done(i) ? "is-done" : i === lesson.step_index ? "is-current" : ""}
                  aria-current={!done(i) && i === lesson.step_index ? "step" : undefined}>
                  {done(i) ? <s>{say}</s> : say}
                </li>
              ))}
            </ol>
          ) : (
            <p className="lesson-why">{lesson ? "No project picked yet. Ask what you can make, then pick one." : "Waiting for the tutor…"}</p>
          )}
        </div>
        <div className="lesson-step-main">
          <h2 className="lesson-current-step">Parts found</h2>
          {parts.length ? (
            <ul className="lesson-step-list">{parts.map((part) => <li key={part}>{part}</li>)}</ul>
          ) : (
            <p className="lesson-why">Ask "what is this?" while looking at a part.</p>
          )}
          {need.length > 0 && (
            <>
              <h3 className="parts-need-heading">Still need</h3>
              <ul className="lesson-step-list">
                {need.map((part) => (
                  <li key={part} className="part-need"><span aria-hidden="true">✗ </span>{part}</li>
                ))}
              </ul>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
// Live from the tutor's confirmed plan: what the current step looks like when done, and any code the plan
// wrote. The plan's still-needed parts are listed under Parts found.
export function BreadboardPanel({ lesson }) {
  const [copied, setCopied] = useState(false);
  const copy = () => navigator.clipboard?.writeText(lesson.code).then(() => {
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }, () => {});
  return (
    <section className="panel breadboard-panel" aria-label="Plan">
      <div className="plan-workspace">
        <div className="plan-detail">
          <h3>This step is done when</h3>
          <p>{lesson?.check || "No step yet."}</p>
          {/* Only a plan that needs a microcontroller comes with code; nothing is assumed before then. */}
          {lesson?.code && (
            <>
              <div className="plan-code-head">
                <h3>Code</h3>
                <button type="button" className="text-btn" onClick={copy}>{copied ? "Copied" : "Copy"}</button>
              </div>
              <pre className="plan-code mono"><code>{lesson.code}</code></pre>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
