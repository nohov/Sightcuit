# Amber hologram collection

Open `index.html` directly in a browser. Everything is local; no package installation, server, CDN, external fonts, or model files are needed.

Five self-contained Web Components: smartwatch, headphones, laptop, phone, and speaker. Include `hologram-display.js`, then use:

```html
<script src="hologram-display.js" defer></script>
<hologram-display device="smartwatch"></hologram-display>
```

Use any supported device ID and place components individually or in a CSS grid. Component styles are isolated in a Shadow DOM. `gallery.css` styles only the sample gallery. Changing the `device` attribute rebuilds that component.

SVG wireframes are projected from 3D vertices with perspective, tilt, a 20-second rotation, and independent part drift. Hover or keyboard focus spreads parts and shows leader labels. Click, Enter, or Space pins expansion. Reduced-motion mode removes rotation, drift, flicker, and animated transitions. Offscreen components skip geometry updates.

Three.js is not installed in this repository, and repository instructions prohibit new dependencies; this uses the requested SVG alternative. `requestAnimationFrame` follows the display refresh rate, targeting smooth 60 Hz animation. Actual frame rate depends on device/browser and is not guaranteed. Illustrative parts and assemblies are not dimensionally accurate engineering models.

The original frontend and earlier `design-library-local` extraction are unchanged. No recognition models run and no data leaves the browser.
