/* Static design previews. The boxes below are layout examples, never detector output. */
const h = React.createElement;
const themes = [
  { id: "command", title: "Steam Command", note: "Immersive brass and glass workshop" },
  { id: "stage", title: "Workshop Stage", note: "Theatrical red, warm brass, ticket labels" },
  { id: "ledger", title: "Field Ledger", note: "Parchment panels and copper instruments" },
  { id: "night", title: "Night Engine", note: "Navy enamel with restrained gold lines" },
];

function Gear({ small = false }) {
  return h("svg", { className: small ? "gear gear-small" : "gear", viewBox: "0 0 100 100", "aria-hidden": "true" },
    h("circle", { cx: 50, cy: 50, r: 35, fill: "none", stroke: "currentColor", strokeWidth: 13, strokeDasharray: "13 7" }),
    h("circle", { cx: 50, cy: 50, r: 22, fill: "none", stroke: "currentColor", strokeWidth: 5 }),
    h("circle", { cx: 50, cy: 50, r: 7, fill: "currentColor" }),
    [0, 45, 90, 135].map(a => h("line", { key: a, x1: 50, y1: 22, x2: 50, y2: 37, stroke: "currentColor", strokeWidth: 5, transform: `rotate(${a} 50 50)` }))
  );
}

function Box({ className, style, label, sublabel }) {
  return h("div", { className: `sample-box ${className}`, style },
    h("div", { className: "box-label" }, h("span", { className: "label-mark" }, "✦"), label, h("small", null, sublabel)),
    ["tl", "tr", "bl", "br"].map(corner => h("i", { key: corner, className: `corner ${corner}` }))
  );
}

function Scene() {
  return h("div", { className: "scene" },
    h("div", { className: "scene-wall" }),
    h("div", { className: "window" }, h("div", { className: "window-glow" })),
    h("div", { className: "wall-pipe" }),
    h("div", { className: "wall-gauge" }, h("div", { className: "gauge-needle" })),
    h("div", { className: "desk" }),
    h("div", { className: "monitor-art" },
      h("div", { className: "monitor-screen" }, h("div", { className: "screen-line one" }), h("div", { className: "screen-line two" }), h("div", { className: "screen-card" })),
      h("div", { className: "monitor-neck" }), h("div", { className: "monitor-foot" })
    ),
    h("div", { className: "laptop-art" }, h("div", { className: "laptop-screen" }, h("div", { className: "laptop-glow" })), h("div", { className: "laptop-base" })),
    h("div", { className: "projector-art" }, h("div", { className: "projector-lens" }), h("div", { className: "projector-vent" })),
    h(Box, { className: "main-box", style: { left: "28%", top: "19%", width: "47%", height: "53%" }, label: "MONITOR", sublabel: "SELECTED FRAME" }),
    h(Box, { className: "secondary-box", style: { left: "5%", top: "59%", width: "33%", height: "27%" }, label: "LAPTOP", sublabel: "FRAME STYLE" }),
    h("div", { className: "scene-caption" }, "ILLUSTRATIVE CAMERA COMPOSITION · NO INFERENCE")
  );
}

function CommandDeck({ select }) {
  return h("main", { className: "command-deck" },
    h("header", { className: "command-header" },
      h("div", { className: "command-brand" }, h(Gear, { small: true }), h("span", null, "SCAV", h("b", null, "SCRAP"))),
      h("div", { className: "command-header-title" }, "THE INVENTOR'S OPTICAL TABLE", h("small", null, "STEEL  /  STEAM  /  FIELD NOTES")),
      h("div", { className: "command-proof" }, "UI STUDY", h("strong", null, "NO MODEL OUTPUT"))
    ),
    h("div", { className: "command-stage" },
      h(Scene),
      h("div", { className: "command-vignette" }),
      h("div", { className: "command-arc arc-one" }),
      h("div", { className: "command-arc arc-two" }),
      h("div", { className: "command-crosshair" }),
      h("div", { className: "command-stage-tag" }, "OPTICAL FIELD", h("span", null, "01 / DESIGN COMPOSITION")),
      h("section", { className: "floating-panel taxonomy" },
        h("div", { className: "floating-heading" }, h(Gear, { small: true }), "OBJECT REGISTER"),
        h("p", null, "Five labels for a future detector study"),
        h("ol", null, ["Laptop", "Computer tower", "Monitor", "Printer", "Projector"].map((name, index) => h("li", { key: name }, h("em", null, `0${index + 1}`), name))),
        h("div", { className: "panel-foot" }, "CATALOG  /  FIVE FAMILIES")
      ),
      h("section", { className: "floating-panel states" },
        h("div", { className: "floating-heading" }, "FRAME LANGUAGE", h("span", null, "✦")),
        h("p", null, "Proposed visual states"),
        h("div", { className: "state-row" }, h("i", { className: "state-selected" }), "Selected device"),
        h("div", { className: "state-row" }, h("i", { className: "state-candidate" }), "Other frame"),
        h("div", { className: "state-row" }, h("i", { className: "state-view" }), "Better view needed"),
        h("div", { className: "panel-foot" }, "LAYOUT SAMPLES  /  NO INFERENCE")
      ),
      h("div", { className: "floating-note" }, h("span", null, "SPECIMEN 001"), h("strong", null, "MONITOR"), h("small", null, "Label treatment preview")),
      h("div", { className: "command-console" },
        h("div", { className: "console-meter" }, h("div", { className: "meter-ring" }, h(Gear, null))),
        h("div", { className: "console-message" }, h("small", null, "FIELD CONSOLE / VISUAL STUDY"), h("strong", null, "Select an object to open its field notes")),
        h("div", { className: "console-ticket" }, "REGISTER", h("span", null, "✦"))
      )
    ),
    h("nav", { className: "command-themes", "aria-label": "Preview theme" }, themes.map((item, index) =>
      h("button", { key: item.id, type: "button", className: item.id === "command" ? "active" : "", onClick: () => select(item.id) }, `0${index + 1}  ${item.title}`)
    )),
    h("div", { className: "command-disclaimer" }, "Original CSS artwork inspired by workshop consoles and steampunk instruments. Illustrative boxes only; no detector predictions or tracking results.")
  );
}

function App() {
  const initial = new URLSearchParams(location.search).get("theme");
  const [theme, setTheme] = React.useState(themes.some(item => item.id === initial) ? initial : "command");
  const chosen = themes.find(item => item.id === theme);

  function select(id) {
    history.replaceState(null, "", `?theme=${id}`);
    setTheme(id);
  }

  if (theme === "command") return h(CommandDeck, { select });

  return h("main", { className: `app theme-${theme}` },
    h("header", { className: "masthead" },
      h("div", { className: "brand" }, h(Gear, { small: true }), h("span", null, "SCAV", h("b", null, "SCRAP"))),
      h("div", { className: "masthead-center" }, "A FIELD GUIDE TO MACHINES"),
      h("div", { className: "mock-stamp" }, "DESIGN STUDY", h("strong", null, "NO MODEL OUTPUT"))
    ),
    h("div", { className: "ribbon" }, h("span", null, "STEEL & STEAM"), h("span", null, "INTERFACE EXPLORATIONS"), h("span", null, "VOL. 01 / 04")),
    h("div", { className: "content" },
      h("section", { className: "left-column" },
        h("div", { className: "section-intro" }, h("div", { className: "eyebrow" }, "FIELD REGISTER / CAMERA VIEW"), h("h1", null, chosen.title), h("p", null, chosen.note)),
        h("div", { className: "viewfinder" },
          h("div", { className: "viewfinder-top" }, h("span", null, "OPTICAL FIELD  /  01"), h("span", null, "DESIGN PREVIEW")),
          h(Scene),
          h("div", { className: "viewfinder-bottom" }, h("span", null, "01  ·  FRAME TREATMENT"), h("span", null, "TAP A DEVICE TO REGISTER"))
        ),
        h("div", { className: "theme-switcher", "aria-label": "Preview theme" }, themes.map((item, index) =>
          h("button", { key: item.id, type: "button", className: item.id === theme ? "active" : "", onClick: () => select(item.id) },
            h("span", null, `0${index + 1}`), item.title
          )
        ))
      ),
      h("aside", { className: "register" },
        h("div", { className: "register-top" }, h(Gear, null), h("span", null, "THE OBJECT REGISTER")),
        h("div", { className: "register-paper" },
          h("div", { className: "paper-rule" }, "SPECIMEN CARD  ·  INTERFACE SAMPLE"),
          h("div", { className: "card-number" }, "Nº 001 / 005"),
          h("h2", null, "Monitor"),
          h("p", { className: "card-kicker" }, "DISPLAY APPARATUS"),
          h("div", { className: "card-rule" }),
          h("p", { className: "card-copy" }, "A quiet place for the selected device label and a short learning card."),
          h("div", { className: "card-actions" }, h("span", null, "VIEW FIELD NOTES"), h("span", null, "↗")),
          h("div", { className: "card-seal" }, h(Gear, { small: true }))
        ),
        h("div", { className: "register-bottom" },
          h("div", { className: "legend-title" }, "FRAME KEY"),
          h("div", { className: "legend-row" }, h("i", { className: "legend-solid" }), h("span", null, "Selected frame")),
          h("div", { className: "legend-row" }, h("i", { className: "legend-dashed" }), h("span", null, "Secondary frame")),
          h("div", { className: "register-note" }, "These frames show visual styling only. They are not detections or tracking results.")
        )
      )
    ),
    h("footer", { className: "footer" }, h("span", null, "SCAVSCRAP  /  VISUAL EXPLORATION"), h("span", null, "INSPIRED BY STAGECRAFT, BRASS INSTRUMENTS & FIELD JOURNALS"))
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(h(App));
