import unittest
from recognition.component_preview import component_preview


class ComponentPreviewTests(unittest.TestCase):
    def test_supported_observations_preserve_actual_label(self):
        for label, model in [("Arduino UNO R3", "uno"), ("breadboard", "breadboard"),
                             ("LED", "led"), ("resistor", "resistor"),
                             ("male-to-male jumper wire", "jumper")]:
            self.assertEqual(component_preview(label), {
                "model_id": model, "observed_label": label, "illustrative": True})

    def test_no_specific_identity_from_unknown_or_broad_categories(self):
        for label in [None, "none", "phone", "wire", "development_board", "USB cable",
                      "maybe a resistor", "female-to-female jumper wire", {}]:
            self.assertIsNone(component_preview(label))


if __name__ == "__main__":
    unittest.main()
