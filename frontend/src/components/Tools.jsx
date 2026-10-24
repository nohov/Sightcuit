// Brass hand tools drawn on the corners of a detection box. Each is drawn
// upright in a 24×24 box with its working end at the top; CSS rotates it so
// that end points out of the corner. Fill is currentColor, outline is dark.

import { useId } from "react";

const OUTLINE = { stroke: "#2a1d13", strokeWidth: 1, strokeLinejoin: "round" };

export function Wrench() {
  const maskId = `wrench-jaws-${useId().replace(/:/g, "")}`;
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <defs>
        <mask id={maskId}>
          <rect width="24" height="24" fill="#fff" />
          <rect x="10" y="-1" width="4" height="5.5" fill="#000" />
          <rect x="10" y="19.5" width="4" height="5.5" fill="#000" />
        </mask>
      </defs>
      <g mask={`url(#${maskId})`} fill="currentColor" {...OUTLINE}>
        <circle cx="12" cy="4.6" r="4.4" />
        <circle cx="12" cy="19.4" r="4.4" />
        <rect x="10.4" y="6" width="3.2" height="12" rx="1" />
      </g>
      <circle cx="12" cy="12" r="0.9" fill="#2a1d13" />
    </svg>
  );
}

export function Hammer() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <g {...OUTLINE}>
        <rect x="10.6" y="6" width="2.8" height="17" rx="1.2" fill="#7a5530" />
        <rect x="10.6" y="18" width="2.8" height="5" rx="1.2" fill="#4a3420" />
        <path d="M4 2.5h11.5l2 1.2v3.6l-2 1.2H4z" fill="currentColor" />
        <path d="M17.5 3.7c2.2-.4 3.6.6 4 2.3-1.3-.6-2.6-.7-4-.3z" fill="currentColor" />
      </g>
    </svg>
  );
}

export function Screwdriver() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <g {...OUTLINE}>
        <path d="M11.3 1h1.4l.5 2.5v8h-2.4v-8z" fill="#cfc6b4" />
        <rect x="10.2" y="11" width="3.6" height="2.2" rx=".5" fill="currentColor" />
        <rect x="9" y="13" width="6" height="10" rx="2.6" fill="#7a5530" />
        <path d="M10.5 15.5v5M12 15.5v5M13.5 15.5v5" stroke="#4a3420" strokeWidth=".8" />
      </g>
    </svg>
  );
}
