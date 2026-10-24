from concurrent.futures import Future
import json
from pathlib import Path
import tempfile
import unittest

from recognition import narrator


WAV = b"RIFF\x24\x00\x00\x00WAVEfmt "


class SyncExecutor:
    def submit(self, fn, *args):
        future = Future()
        try:
            future.set_result(fn(*args))
        except Exception as exc:
            future.set_exception(exc)
        return future

    def shutdown(self, **_):
        pass


class FakeProcess:
    def __init__(self):
        self.terminated = False

    def poll(self):
        return None

    def terminate(self):
        self.terminated = True


class NarratorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.cache = Path(self.directory.name)
        self.described, self.spoken, self.played = [], [], []

    def tearDown(self):
        self.directory.cleanup()

    def make(self, describe=None):
        def default_describe(label):
            self.described.append(label)
            return f"The {label} is a device."

        def speak(text):
            self.spoken.append(text)
            return WAV

        def play(path):
            self.played.append(path)
            return FakeProcess()

        return narrator.Narrator(self.cache, describe or default_describe, speak, self.cache / "voice", play,
                                 SyncExecutor())

    def test_clip_is_made_once_kept_on_disk_and_played(self):
        n = self.make()
        n.prepare("Apple iPhone")
        n.prepare("Apple iPhone")
        self.assertEqual(self.described, ["Apple iPhone"])
        self.assertEqual(self.spoken, ["The Apple iPhone is a device."])
        self.assertEqual(n.wav("Apple iPhone").read_bytes(), WAV)
        self.assertEqual(n.description("Apple iPhone"), "The Apple iPhone is a device.")
        self.assertEqual(n.click("Apple iPhone"), "playing")
        self.assertEqual(self.played, [self.cache / "voice" / "apple-iphone.wav"])
        # A new run reuses the clip on disk without calling Gemini or ElevenLabs.
        again = self.make()
        again.prepare("Apple iPhone")
        self.assertTrue(again.ready("Apple iPhone"))
        self.assertEqual(len(self.described), 1)

    def test_new_click_stops_the_clip_already_playing(self):
        n = self.make()
        n.prepare("Apple iPhone")
        n.prepare("JBL speaker")
        n.click("Apple iPhone")
        first = n.playing
        n.click("JBL speaker")
        self.assertTrue(first.terminated)

    def test_failure_is_retried_only_on_click(self):
        calls = []

        def flaky(label):
            calls.append(label)
            if len(calls) == 1:
                raise RuntimeError("Gemini HTTP 503")
            return "Earbuds are small wireless headphones."

        n = self.make(flaky)
        with self.assertLogs(level="ERROR"):
            n.prepare("wireless earbuds")
        n.prepare("wireless earbuds")
        self.assertEqual(len(calls), 1)
        self.assertEqual(n.click("wireless earbuds"), "retrying")
        self.assertTrue(n.ready("wireless earbuds"))
        self.assertEqual(n.click("wireless earbuds"), "playing")

    def test_unready_click_while_making_is_pending(self):
        n = narrator.Narrator(self.cache, lambda label: "x",
                              executor=type("Held", (), {"submit": lambda self, *a: Future()})())
        n.prepare("laptop")
        self.assertEqual(n.click("laptop"), "pending")

    def test_text_only_until_audio_is_turned_on_then_text_is_reused(self):
        text_only = narrator.Narrator(self.cache, lambda label: self.described.append(label) or "A laptop.",
                                      executor=SyncExecutor())
        text_only.prepare("laptop")
        self.assertTrue(text_only.ready("laptop"))
        self.assertEqual(text_only.click("laptop"), "shown")
        self.assertEqual(text_only.description("laptop"), "A laptop.")
        voiced = self.make()
        self.assertFalse(voiced.ready("laptop"))
        voiced.prepare("laptop")
        self.assertEqual(self.described, ["laptop"])  # Gemini not asked again
        self.assertEqual(self.spoken, ["A laptop."])
        self.assertEqual(voiced.click("laptop"), "playing")

    def test_slug_is_safe_for_any_label(self):
        self.assertEqual(narrator.slug("Apple MacBook / Pro?"), "apple-macbook-pro")
        self.assertEqual(narrator.slug("../.."), "item")


class DescribeTests(unittest.TestCase):
    def test_sends_only_text_and_flattens_answer(self):
        sent = []

        def transport(payload, model, timeout):
            sent.append(payload)
            return {"candidates": [{"content": {"parts": [{"text": "The iPhone\n  is Apple's phone.  "}]}}]}

        text = narrator.gemini_describe("Apple iPhone", "test-model", transport=transport)
        self.assertEqual(text, "The iPhone is Apple's phone.")
        parts = sent[0]["contents"][0]["parts"]
        self.assertEqual(len(parts), 1)
        self.assertIn('"Apple iPhone"', parts[0]["text"])
        self.assertNotIn("inline_data", json.dumps(sent[0]))

    def test_overlong_description_is_rejected(self):
        def transport(payload, model, timeout):
            return {"candidates": [{"content": {"parts": [{"text": "word " * 200}]}}]}

        with self.assertRaises(ValueError):
            narrator.gemini_describe("laptop", "test-model", transport=transport)


if __name__ == "__main__":
    unittest.main()
