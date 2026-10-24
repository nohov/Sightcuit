const frame = document.getElementById("frame");
const sample = { class: "monitor", confidence: 0.87, box: [414, 107, 864, 422] };
ReactDOM.createRoot(frame.appendChild(document.createElement("div"))).render(
  React.createElement(DetectionBox, { detection: sample, frameWidth: 1120, frameHeight: 630 })
);
