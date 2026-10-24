# Object-detection labeling guide

## Task rule

Draw one rectangular box around every visible instance of a supported target
class. Boxes use original-image pixel `xyxy` coordinates and cover the visible
device extent as tightly as practical. They are object-detection boxes, not
instance masks. A partially occluded device may be boxed when its class remains
visually defensible; do not guess the hidden extent.

The five target class IDs are `laptop`, `desktop_computer_tower`, `monitor`,
`printer`, and `projector`. The scene-level review outcomes are `ambiguous`,
`unsupported`, and `unreadable`; they are not detector classes. Do not create
masks, parts, brands, exact models, internal-component labels, material estimates,
or copper estimates.

Use `unreadable` when image quality prevents identification. Use `unsupported`
when readable objects are outside the five classes. Use `ambiguous` when a
candidate object is visible but its target class cannot be resolved. A clear
image with no supported instances is a valid negative and has zero target boxes.

## Target classes

### `laptop`

Include:

- Notebook computers with a visible, permanently attached hinged display and
  keyboard base.
- Permanently hinged convertible laptops, whether shown in laptop, tent, or
  tablet-folded mode, when the attached base is evident.
- Open or closed laptops when the overall device form is recognizable.

Exclude:

- Tablets, phones, handheld game systems, and e-readers.
- Tablets paired with detachable or separate keyboard covers; label these
  `unsupported` when clearly identifiable as tablets.
- A detached laptop screen or keyboard alone.

Ambiguous cases:

- A tightly cropped screen that could belong to a laptop or monitor.
- A closed thin device without enough ports, hinge, keyboard, or context to
  distinguish a laptop from a tablet.
- A two-in-one device whose keyboard attachment cannot be determined.

### `desktop_computer_tower`

Include:

- Full, mid, mini, and small-form-factor desktop computer chassis.
- Workstation or gaming PC chassis when they are standalone computers rather
  than rack systems or external enclosures.

Exclude:

- All-in-one computers, because the computer and display form one device.
- Rack servers, network appliances, game consoles, UPS units, external drives,
  eGPU enclosures, and empty cases that are clearly not functioning computers.
- Loose motherboards or internal components.

Ambiguous cases:

- An unlabeled black box lacking visible computer-specific structure.
- A case that might be an empty chassis.
- A compact computer hidden behind a monitor when it cannot be distinguished
  from a dock or external drive.

### `monitor`

Include:

- Standalone flat-panel or CRT displays intended primarily for computer or
  external display use.
- A monitor photographed without its stand when the complete display enclosure
  is visible.

Exclude:

- Televisions that are clearly identifiable as televisions.
- Laptop screens, tablet displays, projector screens, digital signs, and bare
  display panels.
- All-in-one computers that are clearly identifiable; use `unsupported` because
  there is no all-in-one target class.

Ambiguous cases:

- A display with no visible controls, ports, stand, context, or metadata that
  distinguishes a monitor from a television.
- A display-shaped device that may be an all-in-one computer.

### `printer`

Include:

- Inkjet, laser, thermal, label, receipt, photo, and dot-matrix printers.
- Multifunction devices that can print as well as scan, copy, or fax.
- Large-format printers when printing is their primary function.

Exclude:

- Standalone scanners, copiers known not to print, fax-only machines, shredders,
  laminators, and 3D printers.
- Loose toner cartridges, ink cartridges, paper trays, and printer parts.

Ambiguous cases:

- An office machine whose printing capability cannot be distinguished from a
  scanner-only device.
- A tightly cropped output slot or paper tray without the full device.

### `projector`

Include:

- Portable, classroom, conference-room, ceiling-mounted, short-throw, and
  home-theater digital video or data projectors.
- A projector seen from an unusual angle when its projection lens and enclosure
  remain identifiable.

Exclude:

- Cameras, webcams, security cameras, document cameras, camera lenses, projector
  screens, stage lights, flashlights, and smart speakers.
- Overhead transparency and slide projectors under the current digital-projector
  definition.

Ambiguous cases:

- A ceiling-mounted optical device without enough detail to distinguish a
  projector from a camera or sensor.
- A cropped lens and enclosure with no evidence of projection direction,
  mounting, controls, or ventilation.

## Example decisions

| Image content | Detection or scene decision | Reason |
| --- | --- | --- |
| Open notebook with attached keyboard and screen | `laptop` | Recognizable hinged portable computer |
| Tablet resting on a removable keyboard cover | `unsupported` | Tablet is outside the target classes |
| Thin closed device that could be a tablet or laptop | `ambiguous` | Readable image, unresolved device type |
| PC chassis beside a monitor | Box both supported devices | Detection labels every defensible target instance |
| Clearly identifiable all-in-one computer | `unsupported` | All-in-one is not a tower or standalone monitor |
| Standalone display at a desk with computer connections visible | `monitor` | Computer-display context resolves TV ambiguity |
| Wall-mounted display with no distinguishing context | `ambiguous` | Monitor versus television cannot be resolved |
| Multifunction printer-scanner with paper input and output | `printer` | Printing capability makes it a printer |
| Flatbed scanner with no evidence of printing | `unsupported` | Scanner-only devices are outside scope |
| Ceiling-mounted device with projection lens and ventilation | `projector` | Projection hardware is visually supported |
| Ceiling-mounted optical device that could be a camera | `ambiguous` | Projector versus camera cannot be resolved |
| Security camera with a visible camera mount | `unsupported` | Camera is identifiable and outside scope |
| Two clearly identifiable target devices | Box both devices | Detection is not limited to one primary object |
| Severe blur showing only an unidentifiable rectangular object | `unreadable` | Quality prevents reliable identification |
| Empty room | `unsupported` | Readable image with no target device |

## Unresolved policy decisions

The current rules are usable, but the project owner should confirm these choices
before locking evaluation labels:

1. Whether detachable-keyboard tablets should remain `unsupported` or count as
   laptops.
2. Whether clearly identifiable all-in-one computers should remain `unsupported`
   or be folded into `monitor`.
3. Whether a television used as a computer display should count as `monitor`; the
   current rule follows device type, not temporary use.
4. Whether overhead transparency and slide projectors should join the digital
   `projector` class.

Until those decisions change, apply the defaults in this guide consistently and
record uncertainty as `ambiguous` rather than guessing.
