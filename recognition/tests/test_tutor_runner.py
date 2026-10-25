import base64
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

import cv2
import numpy as np

from recognition import tutor_runner as runner


PROJECT = runner.load_project(runner.HERE.parent / "projects" / "led_resistor.json")
PROMPT = (runner.HERE / "prompt-tutor-v5.txt").read_text(encoding="utf-8")
TIERS = [{"provider": "gemini", "model": "cheap"}, {"provider": "openai", "model": "strong"}]
JPEG = b"fake-jpeg"


def reply(answer="ok", step_done=None, uncertain=False, component=None):
    return {"answer": answer, "step_done": step_done, "component": component, "uncertain": uncertain}


def plan(uncertain=False, code="", steps=({"say": "Put the LED in row 5.", "check": "LED in row 5."},
                                 {"say": "Add the resistor.", "check": "Resistor from row 5."})):
    return {"answer": "That's a night light that turns on in the dark.", "title": "Night light",
            "parts": ["red LED", "220 ohm resistor", "photoresistor"], "missing": ["photoresistor"] if steps else [], "code": code,
            "steps": list(steps), "uncertain": uncertain}


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

    def test_resistor_question_asks_for_bands_without_model_call(self):
        t, fakes = tutor()
        say, fields = t.handle("which resistor is this", JPEG)
        self.assertEqual((say, fields["command"]), (runner.ASK_BANDS, "ask_bands"))
        self.assertEqual(fakes["gemini"].calls, [])

    def test_spoken_bands_decoded_by_code_and_matched_to_bom(self):
        t, fakes = tutor()
        say, fields = t.handle("red red brown gold", None)
        self.assertIn("220 ohms", say)
        self.assertIn("R1", say)
        self.assertEqual(fields["bands"], ["red", "red", "brown", "gold"])
        self.assertIn("220 ohms", t.handle("Gold, brown, red, red.", None)[0])
        self.assertEqual(fakes["gemini"].calls, [])

    def test_spoken_bands_not_in_bom_report_both_directions(self):
        t, _ = tutor()
        say, _ = t.handle("brown black orange brown", None)
        self.assertIn("10 kilohms", say)
        self.assertIn("other end", say)
        self.assertIn("not in this project", say)
        self.assertIn("220 ohms for R1", say)

    def test_spoken_invalid_bands_ask_again(self):
        t, _ = tutor()
        say, _ = t.handle("black red brown", None)
        self.assertIn("colors are wrong", say)
        self.assertIn("colors are wrong", t.handle("red red purple gold", None)[0])
        self.assertIn("Tell me its band colors", say)

    def test_what_is_this_goes_to_model(self):
        t, fakes = tutor([reply("That's a resistor. Read me its band colors.")])
        self.assertIn("band colors", t.handle("what is this", JPEG)[0])
        self.assertEqual(len(fakes["gemini"].calls), 1)

    def test_uncertain_everywhere_never_guesses(self):
        t, _ = tutor([reply(uncertain=True)], [reply("maybe 220", uncertain=True)])
        say, _ = t.handle("what part is this", JPEG)
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


class SessionTests(unittest.TestCase):
    """Mocked session checks; no model inference runs."""

    def test_parts_seen_feed_what_can_i_make(self):
        t, fakes = tutor([reply("That's an LED.", component="LED"), reply("A battery.", component="9V battery"),
                          reply("Again an LED.", component="led"), reply("Build a flashlight.")])
        for _ in range(3):
            t.handle("what is this", JPEG)
        self.assertEqual(t.components, ["LED", "9V battery"])
        say, fields = t.handle("What can I make with these components?", JPEG)
        self.assertEqual((say, fields["command"]), ("Build a flashlight.", "ideas"))
        prompt = fakes["gemini"].calls[-1][0]["contents"][0]["parts"][1]["text"]
        self.assertIn("LED, 9V battery", prompt)

    def test_uncertain_and_check_replies_are_not_remembered(self):
        t, _ = tutor([reply(uncertain=True, component="LED"), reply(step_done=False, component="LED")],
                     [reply(uncertain=True, component="LED")])
        t.handle("what is this", JPEG)
        t.handle("check it", JPEG)
        self.assertEqual(t.components, [])

    def test_ideas_without_parts_cost_no_model_call(self):
        t, fakes = tutor()
        self.assertIn("Show me some parts", t.handle("what could I build", JPEG)[0])
        self.assertEqual(fakes["gemini"].calls, [])

    def test_spoken_bands_are_remembered(self):
        t, _ = tutor()
        t.handle("red red brown gold", None)
        self.assertEqual(t.components, ["220 ohms resistor"])

    def test_plan_lists_missing_parts_and_waits_for_yes(self):
        t, fakes = tutor([plan()])
        say, fields = t.handle("I want to make a night light", JPEG)
        self.assertEqual(fields["command"], "plan")
        self.assertIn("It uses red LED, 220 ohm resistor, photoresistor. You still need photoresistor.", say)
        self.assertIn("Say yes to start it, or no to keep building Light an LED from a 5 volt supply.", say)
        self.assertIs(t.project, PROJECT)
        self.assertIn("missing", fakes["gemini"].calls[0][0]["generationConfig"]["responseSchema"]["properties"])
        say, fields = t.handle("yes", JPEG)
        self.assertEqual((say, fields["command"]), ("Starting Night light. Step 1 of 2. Put the LED in row 5.", "confirm"))
        self.assertIsNone(t.pending)
        self.assertIn("Step 2 of 2. Add the resistor.", t.handle("next", JPEG)[0])
        self.assertIn("last step", t.handle("next", JPEG)[0])
        self.assertNotIn("not in this project", t.handle("brown black orange gold", None)[0])

    def test_confirmed_plan_saves_its_sketch(self):
        with tempfile.TemporaryDirectory() as folder:
            fakes = {"gemini": FakeProvider("gemini", [plan(code="void setup() {}\nvoid loop() {}\n")]),
                     "openai": FakeProvider("openai", [])}
            t = runner.Tutor(None, TIERS, PROMPT, fakes, sketch_dir=Path(folder) / "sketches")
            t.handle("can I make a night light", JPEG)
            self.assertEqual(list(Path(folder).rglob("*.ino")), [])  # nothing saved before yes
            say, _ = t.handle("yes", JPEG)
            self.assertIn("night_light.ino", say)
            self.assertIn("void loop()", (Path(folder) / "sketches" / "night_light" / "night_light.ino").read_text())

    def test_step_prompt_lists_session_part_names(self):
        t, fakes = tutor([reply(component="Arduino Uno"), reply(component="Arduino Uno")])
        t.handle("what is this", JPEG)
        t.handle("what is this", JPEG)
        self.assertIn("named in this session: Arduino Uno", fakes["gemini"].calls[1][0]["contents"][0]["parts"][1]["text"])

    def test_no_backs_out_and_keeps_the_current_build(self):
        t, fakes = tutor([plan()])
        t.handle("next", JPEG)
        t.handle("let's make the night light", JPEG)
        say, fields = t.handle("no, go back", JPEG)
        self.assertEqual(fields["command"], "decline")
        self.assertIn("Okay, not building Night light. Back to Light an LED from a 5 volt supply. Step 2 of 5", say)
        self.assertEqual((t.project, t.step, t.pending), (PROJECT, 1, None))
        self.assertIn("Step 1 of 5", t.handle("back", JPEG)[0])
        self.assertEqual(len(fakes["gemini"].calls), 1)

    def test_uncertain_or_invalid_plan_escalates_and_keeps_project(self):
        t, fakes = tutor([plan(uncertain=True, steps=())], [plan(steps=())])
        say, _ = t.handle("help me build a mains heater", JPEG)
        self.assertIn("can't reach", say)
        self.assertIs(t.project, PROJECT)
        self.assertEqual(len(fakes["openai"].calls), 1)
        t, _ = tutor([plan(uncertain=True, steps=())], [plan(uncertain=True, steps=())])
        self.assertIn("can't plan that", t.handle("how do I make a taser", JPEG)[0])

    def test_build_words_do_not_trigger_step_commands(self):
        t, _ = tutor([plan()])
        t.handle("how can I build a back-up alarm", JPEG)
        self.assertEqual((t.step, t.pending["title"]), (0, "Night light"))

    def test_new_session_resets(self):
        t, _ = tutor([reply(component="LED"), plan()])
        t.handle("what is this", JPEG)
        t.handle("let's build a night light", JPEG)
        t.handle("yes", JPEG)
        say, _ = t.handle("new session", JPEG)
        self.assertIn("Step 1 of 5", say)
        self.assertEqual((t.components, t.step), ([], 0))
        self.assertIs(t.project, PROJECT)
        self.assertIsNone(t.pending)


class NoProjectTests(unittest.TestCase):
    """Mocked checks of a tutor started without a project; no model inference runs."""

    def test_starts_with_no_build_and_steps_cost_nothing(self):
        t, fakes = tutor()
        t = runner.Tutor(None, TIERS, PROMPT, fakes)
        for text in ("next", "back", "repeat", "I'm done"):
            self.assertEqual(t.handle(text, JPEG)[0], runner.NO_BUILD)
        self.assertEqual(fakes["gemini"].calls, [])
        self.assertTrue(t.handle("red red brown gold", None)[0].endswith("220 ohms, plus or minus 5 percent."))

    def test_what_is_this_then_plan_then_reset(self):
        fakes = {"gemini": FakeProvider("gemini", [reply("An LED.", component="LED"), plan()]),
                 "openai": FakeProvider("openai", [])}
        t = runner.Tutor(None, TIERS, PROMPT, fakes)
        self.assertEqual(t.handle("what is this", JPEG)[0], "An LED.")
        self.assertIn("none, no build chosen yet", fakes["gemini"].calls[0][0]["contents"][0]["parts"][1]["text"])
        self.assertIn("or no to back out", t.handle("I want to make a night light", JPEG)[0])
        self.assertEqual(t.handle("nope", JPEG)[0], "Okay, not building Night light. " + runner.NO_BUILD)
        self.assertEqual(t.handle("new session", JPEG)[0], "New session. " + runner.NO_BUILD)


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
        self.assertEqual(body["model"], self.records[0]["attempts"][-1]["model"])
        self.assertIsNone(self.post("/ask", json.dumps({"text": "next"}).encode())[1]["model"])
        self.assertEqual(self.records[0]["question"], "what is this")
        self.assertEqual(self.records[0]["image_size_hw_pixels"], [20, 30])
        self.assertEqual(self.records[0]["components"], [])
        self.assertEqual((self.records[0]["project_id"], self.records[0]["pending_plan"]), ("led_resistor", None))

    def test_reply_carries_speech_or_falls_back(self):
        tutor_, _ = tutor([reply("Hi."), reply("Again.")])
        spoken = iter([b"RIFFwav", RuntimeError("ElevenLabs down")])

        def speak(text):
            result = next(spoken)
            if isinstance(result, Exception):
                raise result
            return result

        server = runner.make_tutor_server(("127.0.0.1", 0), "secret", tutor_, self.state, self.records.append,
                                          {}, speak=speak)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.server = server
        self.assertEqual(base64.b64decode(self.post("/ask", b'{"text":"hi"}')[1]["audio_wav_base64"]), b"RIFFwav")
        status, body = self.post("/ask", b'{"text":"again"}')
        self.assertEqual((status, body["audio_wav_base64"]), (200, None))

    def test_spoken_ask_is_transcribed_or_handed_back(self):
        tutor_, _ = tutor([reply("A breadboard.")])
        heard = iter(["Tutor, what is this?", RuntimeError("ElevenLabs down"), "tutor"])

        def transcribe(wav):
            self.assertEqual(wav, b"RIFFwav")
            result = next(heard)
            if isinstance(result, Exception):
                raise result
            return result

        server = runner.make_tutor_server(("127.0.0.1", 0), "secret", tutor_, self.state, self.records.append,
                                          {}, transcribe=transcribe)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        port = server.server_address[1]

        def ask(port):
            request = urllib.request.Request(f"http://127.0.0.1:{port}/ask", data=b"RIFFwav", headers={
                "Authorization": "Bearer secret", "Content-Type": "audio/wav"})
            try:
                with urllib.request.urlopen(request, timeout=5) as response:
                    return response.status
            except urllib.error.HTTPError as error:
                return error.code

        self.assertEqual([ask(port), ask(port), ask(port)], [200, 503, 503])
        self.assertEqual([(r["question"], r["question_source"]) for r in self.records],
                         [("what is this", "elevenlabs")])
        self.assertEqual(ask(self.server.server_address[1]), 503)  # no transcriber configured

    def test_wake_question(self):
        self.assertEqual(runner.wake_question("Um, tutor, next step."), "next step")
        self.assertEqual(runner.wake_question("what is this"), "what is this")
        self.assertEqual(runner.wake_question("Tutorial please"), "Tutorial please")

    def test_bad_bodies_rejected(self):
        self.assertEqual(self.post("/frame", b"not a jpeg")[0], 400)
        self.assertEqual(self.post("/ask", b"not json")[0], 400)
        self.assertEqual(self.post("/ask", b'{"text": ""}')[0], 400)
        self.assertEqual(self.post("/nope", b"x")[0], 404)


class CachedSpeakTests(unittest.TestCase):
    def test_each_text_is_voiced_once(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "voice"
            speak = lambda text: calls.append(text) or b"RIFF" + text.encode()
            first = runner.cached_speak("Looks good.", directory, speak)
            self.assertEqual(runner.cached_speak("Looks good.", directory, speak), first)
            self.assertEqual(calls, ["Looks good."])
            self.assertEqual([p.suffix for p in directory.iterdir()], [".wav"])


class ConfigTests(unittest.TestCase):
    def test_shipped_config_and_project_load(self):
        tiers = runner.load_tiers(runner.DEFAULT_CONFIG)
        self.assertEqual(tiers[0]["model"], "gemini-3.5-flash-lite")
        self.assertEqual(PROJECT["bom"][0]["value_ohms"], 220)


if __name__ == "__main__":
    unittest.main()
