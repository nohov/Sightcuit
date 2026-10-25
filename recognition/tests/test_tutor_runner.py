import json
import threading
import unittest
import urllib.error
import urllib.request

import cv2
import numpy as np

from recognition import tutor_runner as runner


PROJECT = runner.load_project(runner.HERE.parent / "projects" / "led_resistor.json")
PROMPT = (runner.HERE / "prompt-tutor-v1.txt").read_text(encoding="utf-8")
TIERS = [{"provider": "gemini", "model": "cheap"}, {"provider": "openai", "model": "strong"}]
JPEG = b"fake-jpeg"


def reply(answer="ok", bands=None, step_done=None, uncertain=False):
    return {"answer": answer, "resistor_bands": bands, "step_done": step_done, "uncertain": uncertain}


class FakeProvider:
    """Returns canned replies in the provider's own response shape; no model inference runs."""

    def __init__(self, provider, replies):
        self.provider, self.replies, self.calls = provider, list(replies), []

    def __call__(self, payload, model, timeout):
        self.calls.append((payload, model))
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        text = json.dumps(item)
        if self.provider == "gemini":
            return {"candidates": [{"content": {"parts": [{"text": text}]}}], "usageMetadata": {"totalTokenCount": 1}}
        return {"choices": [{"message": {"content": text}}], "usage": {"total_tokens": 1}, "model": model}


def tutor(cheap=(), strong=()):
    fakes = {"gemini": FakeProvider("gemini", cheap), "openai": FakeProvider("openai", strong)}
    return runner.Tutor(PROJECT, TIERS, PROMPT, fakes), fakes


class CascadeTests(unittest.TestCase):
    """Mocked cascade checks; no model inference runs."""

    def test_step_commands_cost_no_model_call(self):
        t, fakes = tutor()
        self.assertIn("Step 2 of 5", t.handle("next step", JPEG)[0])
        self.assertIn("Step 2 of 5", t.handle("repeat that", JPEG)[0])
        self.assertIn("Step 1 of 5", t.handle("go back", JPEG)[0])
        self.assertEqual(fakes["gemini"].calls + fakes["openai"].calls, [])

    def test_bom_resistor_answered_by_cheap_tier_from_code_not_model(self):
        t, fakes = tutor([reply("It is 9000 ohms", ["red", "red", "brown", "gold"])])
        say, fields = t.handle("which resistor is this", JPEG)
        self.assertIn("220 ohms", say)
        self.assertNotIn("9000", say)
        self.assertEqual(fields["attempts"][0]["bom_match"], "R1")
        self.assertEqual(fakes["openai"].calls, [])
        self.assertIn("which resistor is this", fakes["gemini"].calls[0][0]["contents"][0]["parts"][1]["text"])

    def test_reversed_bands_still_match(self):
        t, _ = tutor([reply(bands=["gold", "brown", "red", "red"])])
        self.assertIn("220 ohms", t.handle("what is this", JPEG)[0])

    def test_value_not_in_bom_escalates_then_reports_honestly(self):
        bands = ["brown", "black", "orange", "gold"]
        t, fakes = tutor([reply(bands=bands)], [reply(bands=bands)])
        say, fields = t.handle("what resistor", JPEG)
        self.assertEqual([a["tier"] for a in fields["attempts"]], [1, 2])
        self.assertIn("10 kilohms", say)
        self.assertIn("not in this project", say)
        self.assertIn("220 ohms for R1", say)
        self.assertEqual(fakes["openai"].calls[0][1], "strong")

    def test_uncertain_everywhere_never_guesses(self):
        t, _ = tutor([reply(uncertain=True)], [reply("maybe 220", ["red"], uncertain=True)])
        say, _ = t.handle("what resistor", JPEG)
        self.assertEqual(say, runner.UNREADABLE)

    def test_tier_error_escalates(self):
        t, _ = tutor([RuntimeError("Gemini HTTP 503")], [reply("That is an LED.")])
        say, fields = t.handle("what is this part", JPEG)
        self.assertEqual(say, "That is an LED.")
        self.assertIn("503", fields["attempts"][0]["error"])
        self.assertIsNone(fields["attempts"][1]["confidence"])

    def test_invalid_reply_escalates(self):
        t, _ = tutor([{"answer": "x"}], [reply("fine")])
        self.assertEqual(t.handle("hello", JPEG)[0], "fine")

    def test_check_advances_only_when_done(self):
        t, _ = tutor([reply("The legs are on the same side of the gap.", step_done=False),
                      reply(step_done=True)])
        self.assertIn("same side", t.handle("I'm done", JPEG)[0])
        self.assertEqual(t.step, 0)
        self.assertIn("Step 2 of 5", t.handle("check it", JPEG)[0])
        self.assertEqual(t.step, 1)

    def test_all_tiers_fail(self):
        t, _ = tutor([RuntimeError("down")], [RuntimeError("down")])
        self.assertIn("can't reach", t.handle("hello", JPEG)[0])

    def test_no_frame(self):
        t, fakes = tutor()
        self.assertIn("camera frame", t.handle("what is this", None)[0])
        self.assertEqual(fakes["gemini"].calls, [])


class TutorServerTests(unittest.TestCase):
    """Mocked HTTP checks; no model inference runs."""

    def setUp(self):
        self.tutor, _ = tutor([reply("That is a breadboard.")])
        self.state = {"jpeg": None, "image_size": None}
        self.records = []
        self.server = runner.make_tutor_server(("127.0.0.1", 0), "secret", self.tutor, self.state,
                                               self.records.append, {"task": "circuit_tutor"})
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def post(self, path, body, token="secret"):
        request = urllib.request.Request(f"http://127.0.0.1:{self.server.server_address[1]}{path}", data=body,
                                         headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def test_wrong_token_is_rejected(self):
        self.assertEqual(self.post("/ask", b'{"text":"hi"}', token="wrong")[0], 401)
        self.assertEqual(self.records, [])

    def test_frame_then_ask(self):
        jpeg = cv2.imencode(".jpg", np.zeros((20, 30, 3), dtype=np.uint8))[1].tobytes()
        status, body = self.post("/frame", jpeg)
        self.assertEqual((status, body), (200, {"tracks": [], "image_size_hw_pixels": [20, 30]}))
        status, body = self.post("/ask", json.dumps({"text": "what is this"}).encode())
        self.assertEqual(status, 200)
        self.assertEqual(body["say"], "That is a breadboard.")
        self.assertEqual(self.records[0]["question"], "what is this")
        self.assertEqual(self.records[0]["image_size_hw_pixels"], [20, 30])

    def test_bad_bodies_rejected(self):
        self.assertEqual(self.post("/frame", b"not a jpeg")[0], 400)
        self.assertEqual(self.post("/ask", b"not json")[0], 400)
        self.assertEqual(self.post("/ask", b'{"text": ""}')[0], 400)
        self.assertEqual(self.post("/nope", b"x")[0], 404)


class ConfigTests(unittest.TestCase):
    def test_shipped_config_and_project_load(self):
        tiers = runner.load_tiers(runner.DEFAULT_CONFIG)
        self.assertEqual(tiers[0]["model"], "gemini-3.5-flash-lite")
        self.assertEqual(PROJECT["bom"][0]["value_ohms"], 220)


if __name__ == "__main__":
    unittest.main()
