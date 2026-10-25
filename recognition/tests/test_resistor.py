import unittest

from recognition.resistor import decode_bands, readings, spoken_ohms


class DecodeBandsTest(unittest.TestCase):
    def test_known_values(self):
        cases = [
            (["red", "red", "brown", "gold"], 220, 5),
            (["yellow", "violet", "red", "gold"], 4700, 5),
            (["brown", "black", "orange", "gold"], 10_000, 5),
            (["brown", "black", "green", "silver"], 1_000_000, 10),
            (["orange", "orange", "gold", "gold"], 3.3, 5),
            (["brown", "black", "silver", "gold"], 0.1, 5),
            (["brown", "black", "black", "black", "brown"], 100, 1),
            (["red", "red", "black", "black", "brown"], 220, 1),
            (["yellow", "violet", "black", "brown", "red"], 4700, 2),
        ]
        for bands, ohms, tolerance in cases:
            with self.subTest(bands=bands):
                self.assertEqual(decode_bands(bands), {"ohms": ohms, "tolerance_pct": tolerance})

    def test_invalid_codes_raise(self):
        for bands in (
            ["red", "red", "brown"],                    # too few bands
            ["gold", "red", "brown", "red"],            # gold is not a digit
            ["black", "red", "brown", "gold"],          # leading zero
            ["red", "red", "brown", "orange"],          # orange is not a tolerance here
            ["red", "red", "pink", "gold"],             # not a color
        ):
            with self.subTest(bands=bands):
                with self.assertRaises(ValueError):
                    decode_bands(bands)

    def test_readings_tries_reversed_order(self):
        # Read from the gold end, this is only valid reversed: red red brown gold = 220.
        self.assertEqual(readings(["gold", "brown", "red", "red"]), [{"ohms": 220, "tolerance_pct": 5}])
        # Both directions valid: brown black red red (1 kΩ ±2%) and red red black brown (220 Ω ±1%).
        self.assertEqual(len(readings(["brown", "black", "red", "red"])), 2)
        self.assertEqual(readings(["pink", "pink", "pink", "pink"]), [])
        # A violet multiplier is valid IEC but means a misread band here.
        self.assertEqual(readings(["red", "red", "violet", "gold"]), [])

    def test_spoken(self):
        self.assertEqual(spoken_ohms(220), "220 ohms")
        self.assertEqual(spoken_ohms(4700), "4.7 kilohms")
        self.assertEqual(spoken_ohms(1_000_000), "1 megohm")
        self.assertEqual(spoken_ohms(1000), "1 kilohm")


if __name__ == "__main__":
    unittest.main()
