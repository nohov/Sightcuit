// One entry per detector label. Keys must match the labels the backend sends
// (`gemini_label` in recognition/live_runner.py frames) letter for letter.
//
// dims are [width, height, depth] in mm, weight in g, metals in g.
// ALL NUMBERS BELOW ARE PLACEHOLDERS for layout work. Replace them with
// sourced values before showing them to anyone.

export const DEVICES = {
  laptop: {
    label: "Laptop",
    dims: [304, 212, 15.6],
    weight: 1240,
    metals: { Aluminum: 410, Steel: 180, Copper: 95, Magnesium: 40, Cobalt: 28, Gold: 0.2 },
  },
  phone: {
    label: "Phone",
    dims: [71.5, 147.6, 7.8],
    weight: 171,
    metals: { Steel: 32, Aluminum: 24, Copper: 14, Cobalt: 7, Silver: 0.3, Gold: 0.03 },
  },
  headphones: {
    label: "Headphones",
    dims: [168, 187, 83],
    weight: 254,
    metals: { Steel: 58, Aluminum: 36, Copper: 11, Neodymium: 4.2, Nickel: 2.1, Gold: 0.01 },
  },
  speaker: {
    label: "Speaker",
    dims: [183, 72, 72],
    weight: 540,
    metals: { Steel: 150, Aluminum: 80, Copper: 34, Neodymium: 11, Nickel: 3.1, Silver: 0.1 },
  },
  watch: {
    label: "Watch",
    dims: [41, 45, 9.7],
    weight: 30,
    metals: { Aluminum: 8.6, Steel: 3.2, Copper: 1.7, Cobalt: 1.0, Silver: 0.02, Gold: 0.01 },
  },
};

export const DEVICE_IDS = Object.keys(DEVICES);

export const UNKNOWN = {
  label: "Unrecognized device",
  dims: null,
  weight: null,
  metals: {},
};

export function lookup(label) {
  return (label && DEVICES[label]) || UNKNOWN;
}
