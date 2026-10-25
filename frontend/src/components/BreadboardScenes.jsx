import React, { useId } from "react";

const assetBase = import.meta.env.BASE_URL;
const unoGraphic = `${assetBase}electronics/vendor/arduino_Uno_Rev3_breadboard.svg`;
const breadboardGraphic = `${assetBase}electronics/vendor/breadboard.svg`;
const resistorGraphic = `${assetBase}electronics/vendor/resistor_330.svg`;
const ledGraphic = `${assetBase}electronics/vendor/LED-5mm-red-leg.svg`;

function BoardBase({ focus }) {
  const supplyFocus = focus === "supply" || focus === "review";
  const groundFocus = focus === "led" || focus === "review";
  return (
    <>
      <image className="board-scene-artwork" href={unoGraphic} x="12" y="69" width="212" height="151" preserveAspectRatio="xMidYMid meet" />
      <image className="board-scene-artwork" href={breadboardGraphic} x="244" y="81" width="411" height="131" preserveAspectRatio="xMidYMid meet" />
      {supplyFocus && <circle cx="138" cy="213" r="7" className="board-scene-pin-focus" />}
      {groundFocus && <circle cx="145" cy="213" r="7" className="board-scene-pin-focus" />}
    </>
  );
}

function LooseParts() {
  return (
    <g aria-label="Resistor, LED, two jumpers, and USB cable laid out beside the boards">
      <rect x="255" y="217" width="390" height="40" rx="3" className="board-scene-tray" />
      <path d="M269 232q12-15 28 0t28 0" className="board-scene-power-wire" />
      <path d="M269 246q12-15 28 0t28 0" className="board-scene-ground-wire" />
      <image className="board-scene-artwork" href={resistorGraphic} x="351" y="228" width="83" height="19" />
      <image className="board-scene-artwork" href={ledGraphic} x="461" y="216" width="20" height="38" />
      <path d="M522 238h50m0-8v16m0-16h23v16h-23" className="board-scene-usb" />
    </g>
  );
}

function SupplyJumper() {
  return (
    <g aria-label="First jumper, drawn as a loose route from UNO 5V toward the breadboard">
      <path d="M138 213C171 247 248 238 275 185S304 143 329 139" className="board-scene-power-wire" />
      <circle cx="329" cy="139" r="4" className="board-scene-open-end" />
    </g>
  );
}

function ResistorPart() {
  return (
    <g aria-label="330 ohm resistor staged over the breadboard, without selected holes">
      <image className="board-scene-artwork" href={resistorGraphic} x="346" y="131" width="86" height="19" />
    </g>
  );
}

function LedPart() {
  return (
    <g aria-label="Red LED staged over the breadboard with its polarity to be confirmed">
      <image className="board-scene-artwork" href={ledGraphic} x="475" y="122" width="27" height="51" />
    </g>
  );
}

function GroundJumper() {
  return (
    <g aria-label="Second jumper, drawn as a loose return toward UNO GND">
      <path d="M508 177C550 213 375 216 248 231S170 231 145 213" className="board-scene-ground-wire" />
      <circle cx="508" cy="177" r="4" className="board-scene-open-end" />
    </g>
  );
}

function Scene({ title, description, focus, variant, children }) {
  const drafting = variant === "drafting";
  const titleId = useId();
  const descriptionId = useId();
  const gridId = useId().replaceAll(":", "");
  const majorGridId = useId().replaceAll(":", "");
  const hatchId = useId().replaceAll(":", "");
  const engraveId = useId().replaceAll(":", "");
  const unoMaskId = useId().replaceAll(":", "");
  return (
    <svg className={drafting ? "board-drafting-scene" : "board-original-scene"} viewBox={drafting ? "0 0 680 275" : "0 44 680 242"} role="img" aria-labelledby={`${titleId} ${descriptionId}`}>
      <title id={titleId}>{title}</title>
      <desc id={descriptionId}>{description} Exact hole positions are not specified.</desc>
      <defs>
        <pattern id={gridId} width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0H0V20" className="board-drafting-grid-line" /></pattern>
        <pattern id={majorGridId} width="100" height="100" patternUnits="userSpaceOnUse"><path d="M100 0H0V100" className="board-drafting-major-line" /></pattern>
        <pattern id={hatchId} width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(28)"><path d="M0 0V7" className="board-drafting-hatch-line" /></pattern>
        <pattern id={engraveId} width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(30)"><path d="M0 0V4" className="board-drafting-engrave-line" /></pattern>
        <mask id={unoMaskId} maskUnits="userSpaceOnUse" x="12" y="69" width="212" height="151" style={{ maskType: "alpha" }}><image href={unoGraphic} x="12" y="69" width="212" height="151" /></mask>
      </defs>
      {drafting ? <>
        <rect width="680" height="275" className="board-drafting-paper" />
        <rect width="680" height="275" fill={`url(#${gridId})`} />
        <rect width="680" height="275" fill={`url(#${majorGridId})`} />
        <g className="board-drafting-guide" aria-hidden="true"><circle cx="449" cy="142" r="117" /><circle cx="449" cy="142" r="85" /><path d="M449 13V270M236 142H665" /></g>
      </> : <>
        <rect width="680" height="286" className="board-original-paper" />
        <text x="16" y="64" className="board-original-part-label">ARDUINO UNO REV3</text>
        <text x="244" y="74" className="board-original-part-label">SOLDERLESS BREADBOARD</text>
      </>}
      <BoardBase focus={focus} />
      {drafting && <rect x="12" y="69" width="212" height="151" fill={`url(#${engraveId})`} mask={`url(#${unoMaskId})`} className="board-drafting-engrave" aria-hidden="true" />}
      {children}
      {drafting ? <rect width="680" height="275" fill={`url(#${hatchId})`} className="board-drafting-hatch" aria-hidden="true" /> : <>
        <text x="16" y="240" className="board-original-part-label">UNO 5V</text>
        <text x="100" y="240" className="board-original-part-label">UNO GND</text>
        <text x="245" y="269" className="board-original-footer">Fritzing part views · diagram not matched to demo board</text>
      </>}
    </svg>
  );
}

function SimpleArduino() {
  return (
    <g>
      <text x="100" y="27" textAnchor="middle" className="setup-part-title">Arduino UNO</text>
      <rect x="25" y="50" width="150" height="185" rx="10" fill="#30291b" stroke="#c9a24a" strokeWidth="2" />
      <rect x="17" y="74" width="32" height="38" rx="3" fill="#bca77c" />
      <rect x="76" y="107" width="43" height="64" rx="3" fill="#14100b" stroke="#8c6a2e" />
      <text x="98" y="143" textAnchor="middle" className="setup-pin-label">UNO</text>
      {[0, 1, 2, 3, 4, 5, 6, 7].map(i => <rect key={i} x="145" y={70 + i * 19} width="10" height="9" rx="1" fill="#c9a24a" />)}
      <text x="48" y="195" className="setup-pin-label">5V</text>
      <text x="48" y="216" className="setup-pin-label">GND</text>
    </g>
  );
}

function SimpleBreadboard() {
  return (
    <g>
      <text x="411" y="27" textAnchor="middle" className="setup-part-title">Breadboard</text>
      <rect x="223" y="50" width="377" height="185" rx="10" fill="#cfbe96" stroke="#ead39d" strokeWidth="2" />
      <path d="M243 67H580 M243 219H580" stroke="#a78a50" strokeWidth="2" />
      <rect x="242" y="136" width="339" height="12" rx="4" fill="#a69571" />
      {Array.from({ length: 24 }, (_, col) => [0, 1].flatMap(side =>
        Array.from({ length: 5 }, (_, row) => <circle key={`${col}-${side}-${row}`}
          cx={250 + col * 14} cy={80 + side * 79 + row * 11} r="2.6" fill="#6c6047" />)
      ))}
    </g>
  );
}

export function BaseBoardScene() {
  return (
    <svg viewBox="0 0 620 255" role="img" aria-label="Arduino UNO and empty breadboard overview">
      <desc>Component overview, with no wired connections or exact placement instructions.</desc>
      <SimpleArduino />
      <SimpleBreadboard />
    </svg>
  );
}

function InventoryScene({ variant }) {
  return (
    <Scene variant={variant} focus="inventory" title="Step 1: inspect the Arduino and breadboard" description="Bare Arduino UNO R3 and breadboard, ready for the seven-piece inventory check.">
      <LooseParts />
    </Scene>
  );
}

function SupplyScene({ variant }) {
  return (
    <Scene variant={variant} focus="supply" title="Step 2: plan the first jumper from UNO 5V" description="A red first jumper is staged toward the breadboard with an open end; no hole is selected.">
      <SupplyJumper />
    </Scene>
  );
}

function ResistorScene({ variant }) {
  return (
    <Scene variant={variant} focus="resistor" title="Step 3: stage the 330 ohm resistor" description="The first jumper and 330 ohm resistor are staged over the breadboard; neither end has a selected hole.">
      <SupplyJumper />
      <ResistorPart />
    </Scene>
  );
}

function LedScene({ variant }) {
  return (
    <Scene variant={variant} focus="led" title="Step 4: orient the red LED and return to UNO GND" description="Both jumpers, the 330 ohm resistor, and red LED are staged; polarity and exact holes still require review.">
      <SupplyJumper />
      <ResistorPart />
      <LedPart />
      <GroundJumper />
    </Scene>
  );
}

function ReviewScene({ variant }) {
  return (
    <Scene variant={variant} focus="review" title="Step 5: review the circuit before USB power" description="The complete set of staged pieces is shown, with loose ends to signal that the wiring has not been verified.">
      <SupplyJumper />
      <ResistorPart />
      <LedPart />
      <GroundJumper />
    </Scene>
  );
}

const scenes = [InventoryScene, SupplyScene, ResistorScene, LedScene, ReviewScene];

const sceneDetails = [
  ["Meet the parts", "Lay out the seven pieces. Keep USB disconnected."],
  ["Plan the 5V connection", "The first jumper route is conceptual; the reviewed plan selects the breadboard node."],
  ["Place the 330 Ω resistor", "Show the resistor in series after 5V without assigning exact holes."],
  ["Orient the LED and ground", "Check polarity and the second jumper’s return to UNO GND."],
  ["Review, then power", "Check the connections before following the finalized USB power-up procedure."],
];

export default function BreadboardScene({ stepIndex, variant = "original" }) {
  const CurrentScene = scenes[stepIndex] ?? InventoryScene;
  return <CurrentScene variant={variant} />;
}

function SceneVersion({ variant, title, description }) {
  return (
    <section className={`breadboard-scene-gallery breadboard-scene-gallery-${variant}`} aria-labelledby={`breadboard-scene-gallery-${variant}-title`}>
      <header>
        <span className="mono">{variant === "original" ? "ORIGINAL VERSION" : "DRAFTING VERSION"} · OUTSIDE THE DASHBOARD</span>
        <h2 id={`breadboard-scene-gallery-${variant}-title`}>{title}</h2>
        <p>{description}</p>
      </header>
      <ol>
        {sceneDetails.map(([title, detail], index) => (
          <li key={title}>
            <div className="breadboard-scene-gallery-copy">
              <span className="mono">STEP {index + 1} / 5</span>
              <h3>{title}</h3>
              <p>{detail}</p>
            </div>
            <div className="breadboard-scene-gallery-diagram"><BreadboardScene stepIndex={index} variant={variant} /></div>
          </li>
        ))}
      </ol>
      <p className="breadboard-scene-gallery-credit">Part artwork: <a href="https://github.com/fritzing/fritzing-parts" target="_blank" rel="noreferrer">Fritzing parts library</a>, <a href="https://creativecommons.org/licenses/by-sa/3.0/" target="_blank" rel="noreferrer">CC BY-SA 3.0</a>. The breadboard illustration has not been matched to the demo’s physical board.</p>
    </section>
  );
}

export function BreadboardSceneGallery() {
  return <>
    <SceneVersion variant="original" title="Arduino UNO R3 + breadboard setup" description="The colored part diagrams used in the lesson, shown in step order." />
    <SceneVersion variant="drafting" title="Arduino UNO R3 + breadboard drafting study" description="The same five stages on a drafting grid with ink treatment. Step notes sit outside the drawings." />
  </>;
}
