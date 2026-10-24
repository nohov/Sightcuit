/* Presentational overlay only. The caller supplies a detector result and frame dimensions. */
function DetectionBox({ detection, frameWidth, frameHeight }) {
  const box = detection?.box;
  if (!Array.isArray(box) || box.length !== 4 ||
      !box.every(Number.isFinite) ||
      !Number.isFinite(frameWidth) || frameWidth <= 0 ||
      !Number.isFinite(frameHeight) || frameHeight <= 0 ||
      typeof detection.class !== "string" || !detection.class ||
      !Number.isFinite(detection.confidence) || detection.confidence < 0 || detection.confidence > 1 ||
      box[2] <= box[0] || box[3] <= box[1]) return null;

  const [x1, y1, x2, y2] = box;
  const style = {
    left: `${x1 / frameWidth * 100}%`,
    top: `${y1 / frameHeight * 100}%`,
    width: `${(x2 - x1) / frameWidth * 100}%`,
    height: `${(y2 - y1) / frameHeight * 100}%`,
  };
  const score = `${Math.round(detection.confidence * 100)}%`;

  return React.createElement("div", {
    className: "detection-box",
    style,
    role: "img",
    "aria-label": `${detection.class}, ${score} confidence`,
  },
    React.createElement("div", { className: "detection-box__label" },
      React.createElement("span", { className: "detection-box__marker", "aria-hidden": "true" }),
      React.createElement("span", { className: "detection-box__class" }, detection.class),
      React.createElement("span", { className: "detection-box__score" }, score)
    ),
    React.createElement("span", { className: "detection-box__corner detection-box__corner--tl", "aria-hidden": "true" }),
    React.createElement("span", { className: "detection-box__corner detection-box__corner--tr", "aria-hidden": "true" }),
    React.createElement("span", { className: "detection-box__corner detection-box__corner--bl", "aria-hidden": "true" }),
    React.createElement("span", { className: "detection-box__corner detection-box__corner--br", "aria-hidden": "true" })
  );
}

window.DetectionBox = DetectionBox;
