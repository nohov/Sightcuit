import React, { useEffect, useRef, useState } from "react";
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

// Live from the tutor's /events "tutor" field: the picked build's steps (finished ones crossed out) and the
// parts it needs, marked had once the tutor has named them. Scanned parts the build doesn't use are left out.
// Null before the tutor sends anything, e.g. on the mock feed or live_runner.
export function StepsPanel({ lesson }) {
  const steps = lesson?.steps || [];
  const needed = lesson?.needed || [];
  const done = (i) => lesson.finished || i < lesson.step_index;
  // On short screens the list scrolls; keep the current step in view. Scrolls only the list, never the page.
  const currentRef = useRef(null);
  useEffect(() => {
    const reveal = () => {
      const item = currentRef.current;
      const scrolls = (el) => el.scrollHeight > el.clientHeight && /auto|scroll/.test(getComputedStyle(el).overflowY);
      let box = item?.parentElement; // the nearest box that scrolls: the list, or else the panel itself
      while (box && !box.classList.contains("panel") && !scrolls(box)) box = box.parentElement;
      if (!box) return;
      const offset = item.getBoundingClientRect().top - box.getBoundingClientRect().top;
      if (offset < 0 || offset + item.offsetHeight > box.clientHeight) box.scrollTop += offset - 8;
    };
    reveal();
    document.fonts?.ready.then(reveal); // web fonts change line heights after the first render
  }, [lesson?.step_index, lesson?.project]);
  return (
    <section className="panel steps" aria-labelledby="steps-heading">
      <div className="lesson-step-layout">
        <div className="lesson-step-main">
          <h2 id="steps-heading" className="lesson-current-step">{lesson?.project || "Steps"}</h2>
          {steps.length ? (
            <ol className="lesson-step-list">
              {steps.map((say, i) => (
                <li key={i} ref={i === lesson.step_index ? currentRef : null}
                  className={done(i) ? "is-done" : i === lesson.step_index ? "is-current" : ""}
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
          <h2 className="lesson-current-step">Parts Needed</h2>
          {needed.length ? (
            <ul className="lesson-step-list">
              {needed.map(({ part, have }, i) => (
                <li key={i} className={have ? "" : "part-need"}>
                  <span aria-hidden="true">{have ? "✓ " : "✗ "}</span>{part}
                  <span className="visually-hidden">{have ? " (have)" : " (missing)"}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="lesson-why">
              {steps.length ? "This project has no parts list." : "Pick a project to see the parts it needs."}
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
// Live from the tutor's confirmed plan: what the current step looks like when done, and any code the plan
// wrote. The plan's parts, had and missing, are listed under Parts Needed.
export function BreadboardPanel({ lesson }) {
  const [copied, setCopied] = useState(false);
  // The clipboard needs localhost or https; elsewhere Copy says so and the code can be selected by hand.
  const copy = () => (navigator.clipboard ? navigator.clipboard.writeText(lesson.code) : Promise.reject()).then(
    () => setCopied("Copied"), () => setCopied("Copy failed: select the code below")).then(
    () => setTimeout(() => setCopied(false), 2500));
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
                <button type="button" className="text-btn" onClick={copy}>{copied || "Copy"}</button>
              </div>
              <div className="plan-code-body">
              <details className="ide-guide" open>
                <summary>How to put this code on the board</summary>
                <ol>
                  <li>
                    Download the Arduino IDE from{" "}
                    <a href="https://www.arduino.cc/en/software" target="_blank" rel="noreferrer">arduino.cc/en/software</a>,
                    install it and open it.
                  </li>
                  <li>Plug the Arduino Uno into this computer with its USB cable.</li>
                  <li>Choose <b>Tools → Board → Arduino Uno</b>, then <b>Tools → Port</b> and the port that names the Uno.</li>
                  <li>Press <b>Copy</b> above. In the Arduino IDE choose <b>File → New Sketch</b>, click in the new sketch's code window, select everything in it (<b>⌘A</b> or <b>Ctrl+A</b>) and paste over it (<b>⌘V</b> or <b>Ctrl+V</b>).</li>
                  <li>Press <b>Upload</b> (the → arrow) and wait for "Done uploading".</li>
                </ol>
              </details>
              <pre className="plan-code mono"><code>{lesson.code}</code></pre>
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
