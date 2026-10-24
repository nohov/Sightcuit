const assert = require("node:assert/strict");
const { test } = require("node:test");

global.React = { createElement: (type, props, ...children) => ({ type, props, children }) };
global.window = global;
require("./DetectionBox.js");

test("positions a detector box using the source frame dimensions", () => {
  const result = DetectionBox({
    detection: { class: "monitor", confidence: 0.87, box: [100, 50, 300, 250] },
    frameWidth: 400,
    frameHeight: 400,
  });
  assert.deepEqual(result.props.style, { left: "25%", top: "12.5%", width: "50%", height: "50%" });
  assert.equal(result.props["aria-label"], "monitor, 87% confidence");
});

test("does not render invalid detector coordinates", () => {
  assert.equal(DetectionBox({
    detection: { class: "monitor", confidence: 0.87, box: [300, 50, 100, 250] },
    frameWidth: 400,
    frameHeight: 400,
  }), null);
});
