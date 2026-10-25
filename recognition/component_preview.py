"""Presentation metadata only; never expands detector classes or infers attributes."""

_MODELS = {
    "arduino uno r3": "uno", "arduino_uno_r3": "uno",
    "breadboard": "breadboard", "solderless breadboard": "breadboard",
    "led": "led", "red led": "led",
    "resistor": "resistor", "330 ohm resistor": "resistor", "330ω resistor": "resistor",
    "male-to-male jumper wire": "jumper", "male_to_male_jumper_wire": "jumper",
}


def component_preview(label):
    """Only exact supported observations map to illustrative reference geometry.

    A generic resistor observation does not establish its resistance; a generic
    LED does not establish color. The reference model is explicitly illustrative.
    """
    if not isinstance(label, str):
        return None
    model = _MODELS.get(label.strip().lower())
    return {"model_id": model, "observed_label": label, "illustrative": True} if model else None
