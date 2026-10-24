# Object-detection labelling guide

## Task rule

Draw one rectangular box around every visible instance of a target class. Boxes
use original-image pixel `xyxy` coordinates and cover the visible device as
tightly as practical. They are detection boxes, not masks. A partly occluded
device may be boxed when its class is still visually defensible; do not guess
the hidden extent.

The five target classes are `laptop`, `phone`, `headphones`, `smartwatch` and
`speaker`. The scene-level outcomes `ambiguous`, `unsupported` and `unreadable`
are not detector classes. Do not label parts, brands, exact models, internal
components or material estimates.

Use `unreadable` when image quality prevents identification, `unsupported` when
readable objects are outside the five classes, and `ambiguous` when a candidate
object is visible but its class cannot be resolved. A clear image with no target
devices is a valid negative with zero boxes.

## Target classes

### `laptop`

Include:

- Notebook computers with a visible, permanently attached hinged display and
  keyboard base.
- Permanently hinged convertibles in laptop, tent or folded mode, when the
  attached base is evident.
- Open or closed laptops when the overall form is recognisable.

Exclude:

- Tablets, including tablets on detachable keyboard covers (`unsupported`).
- Desktop monitors, all-in-one computers, e-readers and handheld game systems.
- A detached laptop screen or keyboard on its own.

Ambiguous:

- A closed thin slab without a visible hinge, ports or keyboard.
- A two-in-one whose keyboard attachment cannot be determined.

### `phone`

Include:

- Smartphones, face up or face down, with or without a case.
- Feature phones and flip phones, open or closed.
- A phone held in a hand, when the device itself is visible.

Exclude:

- Tablets and e-readers, judged by size against nearby objects.
- Cordless and desk landline handsets.
- Phone cases, chargers or power banks on their own.

Ambiguous:

- A small slab with no scale cue that could be a phone or a small tablet.
- A dark rectangle that could be a phone, a remote or a power bank.

### `headphones`

Include:

- Over-ear and on-ear headphones with a headband joining two ear cups.
- Gaming and office headsets, including ones with a boom microphone.
- Headphones being worn, when the headband and ear cups are visible.

Exclude:

- In-ear earbuds and their charging cases.
- Ear defenders and hearing protection with no audio hardware.
- Loose ear cushions or cables on their own.

Ambiguous:

- Folded headphones in a case where only part of the band shows.
- Worn headphones mostly hidden by hair or a hood.

### `smartwatch`

Include:

- Wrist-worn watches with a digital touch display, worn or lying flat.
- Smartwatches on a charger, when the watch body is visible.

Exclude:

- Analog watches and digital watches without a touch display.
- Wall clocks, desk clocks and alarm clocks. COCO's `clock` is never a
  smartwatch.
- Screenless fitness bands and smart rings.

Ambiguous:

- A watch face too small or blurred to show whether it is a touch display.
- A band whose body is turned away from the camera.

### `speaker`

Include:

- Portable Bluetooth speakers and smart speakers.
- Bookshelf and desktop computer speakers.
- A speaker grille and enclosure seen from an unusual angle, when still
  identifiable.

Exclude:

- Speakers built into another device, such as a laptop, TV, phone or monitor.
- Microphones, routers, air purifiers and other cylinders without speaker
  evidence.
- Soundbars, large PA and stage speakers, and car audio. Mark these
  `unsupported` until the owner decides otherwise.

Ambiguous:

- A fabric-covered cylinder that could be a smart speaker or an air freshener.
- A box with no visible grille, driver or controls.

## Example decisions

| Image content | Decision | Reason |
| --- | --- | --- |
| Open notebook with attached keyboard | `laptop` | Recognisable hinged portable computer |
| Tablet on a removable keyboard cover | `unsupported` | Tablets are outside the classes |
| Phone lying on a closed laptop | Box both | Detection labels every target instance |
| Small slab with no scale cue | `ambiguous` | Phone versus small tablet unresolved |
| Desk landline handset | `unsupported` | Landlines are excluded from `phone` |
| Over-ear headphones on a stand | `headphones` | Headband joins both ear cups |
| Earbuds in an open charging case | `unsupported` | Earbuds are excluded |
| Smartwatch with a lit touch display, on a wrist | `smartwatch` | Wrist-worn digital touch display |
| Analog wristwatch | `unsupported` | No digital touch display |
| Wall clock | `unsupported` | A clock is not a smartwatch |
| Portable Bluetooth speaker on a table | `speaker` | Standalone speaker enclosure |
| Laptop with visible speaker grilles | `laptop` only | Built-in speakers are not `speaker` |
| Severe blur, unidentifiable small object | `unreadable` | Quality prevents identification |
| Empty desk | `unsupported` | Readable image, no target device |

## Open policy questions

These defaults are usable, but the owner should confirm them before evaluation
labels are locked:

1. Should detachable-keyboard tablets count as `laptop`?
2. Should screenless fitness bands count as `smartwatch`?
3. Should soundbars and large PA speakers count as `speaker`?
4. Should in-ear earbuds join `headphones`?

Until they change, apply these defaults consistently and record genuine
uncertainty as `ambiguous` rather than guessing.
