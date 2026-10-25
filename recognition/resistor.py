"""Decode 4- and 5-band resistor color codes (IEC 60062) so no model ever does the arithmetic."""

from __future__ import annotations


DIGITS = ("black", "brown", "red", "orange", "yellow", "green", "blue", "violet", "grey", "white")
# Power-of-ten exponent for each multiplier band.
MULTIPLIERS = {**{color: exponent for exponent, color in enumerate(DIGITS)}, "gold": -1, "silver": -2}
TOLERANCES = {"brown": 1, "red": 2, "green": 0.5, "blue": 0.25, "violet": 0.1, "grey": 0.05, "gold": 5, "silver": 10}
COLORS = (*DIGITS, "gold", "silver")


def decode_bands(colors: list[str]) -> dict[str, float]:
    """Return {ohms, tolerance_pct} for bands listed from the end farthest from the tolerance band."""
    if len(colors) not in (4, 5):
        raise ValueError(f"expected 4 or 5 bands, got {len(colors)}")
    *digit_bands, multiplier, tolerance = colors
    for color in digit_bands:
        if color not in DIGITS:
            raise ValueError(f"{color!r} is not a digit color")
    if digit_bands[0] == "black":
        raise ValueError("first band cannot be black")
    if multiplier not in MULTIPLIERS:
        raise ValueError(f"{multiplier!r} is not a multiplier color")
    if tolerance not in TOLERANCES:
        raise ValueError(f"{tolerance!r} is not a tolerance color")
    digits = int("".join(str(DIGITS.index(color)) for color in digit_bands))
    exponent = MULTIPLIERS[multiplier]
    ohms = digits * 10 ** exponent if exponent >= 0 else round(digits * 10 ** exponent, 2)
    return {"ohms": ohms, "tolerance_pct": TOLERANCES[tolerance]}


def readings(colors: list[str]) -> list[dict[str, float]]:
    """Valid decodes of the bands as given and reversed; models sometimes read from the wrong end."""
    found = []
    for order in (colors, colors[::-1]):
        try:
            reading = decode_bands(list(order))
        except ValueError:
            continue
        if reading not in found:
            found.append(reading)
    return found


def spoken_ohms(ohms: float) -> str:
    for scale, unit in ((1e6, "megohms"), (1e3, "kilohms")):
        if ohms >= scale:
            return f"{ohms / scale:g} {unit}"
    return f"{ohms:g} ohms"
