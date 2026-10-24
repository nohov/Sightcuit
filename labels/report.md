# Class-definition report

Defined an object-detection task with five stable string class IDs and three
scene-review outcomes that are not detector classes. `classes.json` is the
canonical class map; `guide.md` supplies box policy, operational boundaries, and
example decisions.

The guide resolves the required comparisons with conservative visual rules:
detachable tablets are unsupported, clearly identifiable all-in-one computers are
unsupported, multifunction devices with printing capability are printers, and a
projector needs evidence beyond a generic camera-like lens. Four policy choices
remain for owner confirmation and are listed in `guide.md`.

No images were collected or labeled, and no model behavior or recognition accuracy
was evaluated.
