# DetectionBox

One presentational React component for a detector bounding box. Pass the original detection object (`class`, `confidence`, `box: [x1, y1, x2, y2]`) plus the source frame's pixel width and height. Render it inside a `position: relative` container that displays the full frame at the same aspect ratio. The component converts box coordinates to percentages and does not change the supplied detection.

Open `index.html` for a visual study. It uses React 18 from a pinned CDN URL and illustrative data; no model runs. Run `node --test DetectionBox.test.js` for the placement check.
