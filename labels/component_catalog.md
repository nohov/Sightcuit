# Proposed component recognition catalog

Design catalog for the circuit-building pivot. This is not the active runtime
class contract; `classes.json` remains legacy until prompts, schemas, configs,
and tests migrate together. Listed identities are targets to evaluate, not
claims of model support.

## Two names

- `identity`: most specific name supported by evidence, e.g. male-to-male jumper
  wire; may fall back to jumper wire, or remain null.
- `classification`: broad category such as wire, resistor, LED, or development
  board; use a stable machine-readable identifier.

Keep `instance_id` separate: it identifies an observed physical object, not its
category. Keep expected project requirements separate from observed attributes.
A planned 330Ω resistor is not an observed 330Ω resistor without evidence.
Attributes carry an evidence source (vision, user confirmation, or documentation)
and may be unresolved. Unknown/ambiguous/unreadable are outcomes, not components.

## LED demo targets

| Identity (when supported) | Classification | Expected quantity |
| --- | --- | --- |
| Arduino UNO R3; otherwise development board | development_board | 1 |
| Solderless breadboard | breadboard | 1 |
| Red LED; otherwise LED | led | 1 |
| 330Ω resistor; otherwise resistor | resistor | 1 |
| Male-to-male jumper wire; otherwise jumper wire | wire | 2 |
| USB cable with observed connector types | cable | 1 |

The USB source is setup equipment beyond the seven-piece inventory. Visual
cable detection and user-confirmed cable availability must remain distinct.

## Expansion candidates for other beginner projects

Add only after examples and evaluation exist; do not make these demo blockers.

| Identity examples | Classification |
| --- | --- |
| Male-to-female jumper wire | wire |
| Female-to-female jumper wire | wire |
| Preformed solid-core breadboard jumper | wire |
| Hookup wire with exposed ends | wire |
| Alligator-clip lead | test_lead |
| USB-A, USB-B, USB-C, or Micro-USB cable, endpoints specified separately | cable |
| Tactile pushbutton, slide switch | switch |
| Potentiometer | variable_resistor |
| Ceramic capacitor, electrolytic capacitor | capacitor |
| Diode, transistor | diode / transistor |
| Buzzer; active/passive only with supporting evidence | buzzer |
| Photoresistor | light_sensor |
| Battery holder | battery_holder |
| Breadboard power module | power_module |
| Hobby servo, small DC motor | actuator |
| Integrated circuit; part number only when supported | integrated_circuit |
| Sensor module; exact function only when supported | sensor_module |

## Wire evidence rules

Represent endpoint A and endpoint B independently, with connector type, visible
region, and evidence state. Do not infer male/female configuration unless both
ends are supported. Record visible color as appearance, never as proof of
voltage, polarity, or connection. Separate cables bundled together from a
single physical wire; do not invent a count through occlusion. A jumper ribbon
is not automatically one wire or a known number of individual wires.

Unknown endpoints must still permit a generic wire identity. Distinguish the
two observed jumpers by instance ID; track identity may be unresolved after
occlusion. Category recognition does not establish electrical continuity.
