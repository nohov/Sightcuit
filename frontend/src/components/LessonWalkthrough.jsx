import React from "react";
import "./lesson-walkthrough.css";

function InventoryStep() {
  return (
    <li className="walkthrough-step walkthrough-inventory">
      <article aria-labelledby="walkthrough-inventory-title">
        <div className="walkthrough-step-head"><span>01 / PREPARE</span><h3 id="walkthrough-inventory-title">Meet the parts</h3></div>
        <p>With USB disconnected, spread the seven pieces across the table so each one can be seen.</p>
        <ul className="walkthrough-inventory-list" aria-label="First build inventory">
          <li><strong>1</strong> Arduino UNO R3</li>
          <li><strong>1</strong> Breadboard</li>
          <li><strong>1</strong> Red LED</li>
          <li><strong>1</strong> 330 Ω resistor</li>
          <li><strong>2</strong> Male-to-male jumper wires</li>
          <li><strong>1</strong> Compatible USB cable</li>
        </ul>
        <p className="walkthrough-aside">The PC or USB adapter that will supply power is additional. A part outside the camera view is unresolved, not confirmed missing.</p>
      </article>
    </li>
  );
}

function SupplyStep() {
  return (
    <li className="walkthrough-step walkthrough-supply">
      <article aria-labelledby="walkthrough-supply-title">
        <div className="walkthrough-step-head"><span>02 / SOURCE</span><h3 id="walkthrough-supply-title">Plan the 5V connection</h3></div>
        <p>Find the pin marked <strong>5V</strong> on the Arduino UNO R3. Set one jumper wire beside it.</p>
        <div className="walkthrough-route" aria-label="Planned supply path">
          <span>UNO 5V</span><b aria-hidden="true">→</b><span>First jumper</span><b aria-hidden="true">→</b><span>Breadboard supply node</span>
        </div>
        <p className="walkthrough-aside">The reviewed diagram must identify the correct breadboard hole. Leave USB disconnected while assembling.</p>
      </article>
    </li>
  );
}

function ResistorStep() {
  return (
    <li className="walkthrough-step walkthrough-resistor">
      <article aria-labelledby="walkthrough-resistor-title">
        <div className="walkthrough-step-head"><span>03 / LIMIT CURRENT</span><h3 id="walkthrough-resistor-title">Place the 330 Ω resistor</h3></div>
        <div className="walkthrough-resistor-layout">
          <p>Find the resistor specified as <strong>330 Ω</strong>. The resistor belongs between the 5V supply node and the LED’s positive side.</p>
          <div className="walkthrough-resistor-path" aria-label="Resistor position in the circuit"><span>5V side</span><strong>330 Ω</strong><span>LED anode (+)</span></div>
        </div>
        <p className="walkthrough-aside">Use the reviewed placement diagram for exact holes. The 220 Ω example elsewhere in the repository is not this lesson’s part.</p>
      </article>
    </li>
  );
}

function LedStep() {
  return (
    <li className="walkthrough-step walkthrough-led">
      <article aria-labelledby="walkthrough-led-title">
        <div className="walkthrough-step-head"><span>04 / COMPLETE THE PATH</span><h3 id="walkthrough-led-title">Orient the LED and ground</h3></div>
        <div className="walkthrough-polarity" aria-label="LED polarity and return path">
          <div><span className="walkthrough-polarity-mark">+</span><strong>Anode</strong><small>Receives current from the resistor</small></div>
          <span className="walkthrough-led-symbol" aria-hidden="true">LED →</span>
          <div><span className="walkthrough-polarity-mark">−</span><strong>Cathode</strong><small>Returns through jumper two to UNO GND</small></div>
        </div>
        <p>Confirm which LED lead is which, then follow the reviewed diagram for its placement and the second jumper’s return to <strong>GND</strong>.</p>
        <p className="walkthrough-aside">An LED conducts in one direction. Do not infer polarity or a hole location from this concept view alone.</p>
      </article>
    </li>
  );
}

function ReviewStep() {
  return (
    <li className="walkthrough-step walkthrough-review">
      <article aria-labelledby="walkthrough-review-title">
        <div className="walkthrough-step-head"><span>05 / CHECK & OBSERVE</span><h3 id="walkthrough-review-title">Review, then power</h3></div>
        <ol className="walkthrough-review-list">
          <li>Compare each connection and the LED polarity with the reviewed plan while USB is disconnected.</li>
          <li>Follow the finalized power-up procedure to connect the compatible USB cable.</li>
          <li>Observe the <strong>external red LED</strong>. It should stay lit while powered; removing USB power turns it off.</li>
        </ol>
        <p className="walkthrough-aside">Moving to this step records lesson progress; it does not verify the wiring. Record what happened and any help needed.</p>
      </article>
    </li>
  );
}

export default function LessonWalkthrough() {
  return (
    <section className="lesson-walkthrough" aria-labelledby="lesson-walkthrough-title">
      <header className="lesson-walkthrough-heading">
        <span className="mono">FIRST BUILD / DRAFT LESSON</span>
        <h2 id="lesson-walkthrough-title">The five steps, in order</h2>
        <p>These are draft instructions for the USB-powered red LED build. Exact holes and the power-up procedure await the reviewed project package.</p>
      </header>
      <ol className="lesson-walkthrough-list">
        <InventoryStep />
        <SupplyStep />
        <ResistorStep />
        <LedStep />
        <ReviewStep />
      </ol>
    </section>
  );
}
