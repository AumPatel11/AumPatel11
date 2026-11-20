"""Run: python -m unittest test_lumora -v"""
import json
import threading
import time
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

import desk
import effects
import server


class EffectTests(unittest.TestCase):
    def test_every_effect_renders_valid_rgb(self):
        for eid in effects.EFFECTS:
            state = {}
            for i in range(300):
                rgb = effects.render(eid, i * 0.1, {"colors": ["#ff0000", "#00ff00"]}, state, 0.8)
                self.assertEqual(len(rgb), 3)
                for c in rgb:
                    self.assertTrue(0 <= c <= 255, (eid, rgb))

    def test_brightness_scales(self):
        full = effects.render("heartbeat", 0.1, {"colors": ["#ff8000"]}, {}, 1.0)
        half = effects.render("heartbeat", 0.1, {"colors": ["#ff8000"]}, {}, 0.5)
        self.assertAlmostEqual(half[0], full[0] / 2)

    def test_circadian_warm_at_night_cool_at_noon(self):
        self.assertEqual(effects.circadian_temp(2), 0)
        self.assertGreater(effects.circadian_temp(13), 90)


class SceneAndCertTests(unittest.TestCase):
    def test_scene_data_format(self):
        d = effects.scene_data(["#ff0000", "#0000ff"], "gradient", 50)
        self.assertEqual(len(d), 2 * 26)          # 2 units x 13 bytes
        self.assertEqual(d[4:6], "02")             # gradient mode
        self.assertEqual(d[6:18], "000003e803e8")  # red = H0 S1000 V1000
        self.assertEqual(d[26 + 6:26 + 10], "00f0")  # blue hue 240
        self.assertEqual(effects.scene_data(["#fff"], "jump")[4:6], "01")
        self.assertEqual(len(effects.scene_data(["#f00", "#0f0"], "breathe")), 4 * 26)
        self.assertEqual(len(effects.scene_data(["#123456"] * 20)), 8 * 26)  # bulb max 8 units

    def test_paint_data_matches_real_strip_echo(self):
        # echoed by the real 20-segment strip for "segments 1,3,5 blue"
        self.assertEqual(effects.paint_data((0, 0, 255), [5, 3, 1]), "AAEAFAEA8APoA+iDAQMF")
        self.assertEqual(effects.paint_data((255, 0, 0)), "AAEAFAAAAAPoA+g=")  # whole strip

    def test_dream_scene_matches_strip_accepted_bytes(self):
        import base64
        cols = [effects.rgb_to_hex(effects.hsv(h / 360)) for h in (0, 40, 80, 140, 200, 260, 310)]
        raw = base64.b64decode(effects.dream_data(cols, "flow", 70, 100))
        # the flowing rainbow the real strip accepted and showed
        self.assertEqual(raw.hex(), "01000a464660000064000064002864005064008c6400c86401046401366" "4")

    def test_zones_stretch_and_reverse(self):
        z = desk.zones_to_segments([(1, 0, 0), (2, 0, 0)], total=4)
        self.assertEqual([c[0] for c in z], [1, 1, 2, 2])
        z = desk.zones_to_segments([(1, 0, 0), (2, 0, 0)], total=4, reverse=True)
        self.assertEqual([c[0] for c in z], [2, 2, 1, 1])

    def test_self_signed_cert_loads(self):
        import os
        import ssl
        import tempfile
        import certgen
        cert, key = certgen.make_self_signed(ips=("127.0.0.1", "172.20.10.2"))
        with tempfile.TemporaryDirectory() as d:
            c, k = os.path.join(d, "c.pem"), os.path.join(d, "k.pem")
            open(c, "w").write(cert)
            open(k, "w").write(key)
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(c, k)


class FakeBulb:
    """Stands in for tinytuya.BulbDevice and records calls."""
    MUSIC_TRANSITION_JUMP = 0
    MUSIC_TRANSITION_FADE = 1

    def __init__(self):
        self.calls = []

    def bulb_has_capability(self, feature, nowait=False):
        return True

    def __getattr__(self, name):
        def rec(*a, **kw):
            self.calls.append((name, a, kw))
            return {}
        return rec


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server.CONFIG_PATH = "/nonexistent/config.json"
        server.save_json = lambda *a, **k: None
        server.APP = server.App()
        cls.bulb = FakeBulb()
        server.APP.light.dev = cls.bulb
        server.APP.light.device_cfg = {"id": "x"}
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def req(self, path, body=None, method=None):
        data = json.dumps(body).encode() if body is not None else None
        r = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, method=method,
                                   headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(r) as resp:
            return json.loads(resp.read())

    def names(self):
        return [c[0] for c in self.bulb.calls]

    def test_colour_white_power(self):
        st = self.req("/api/colour", {"hex": "#00ff00"})
        self.assertEqual(st["mode"], "colour")
        self.assertIn("set_hsv", self.names())
        st = self.req("/api/white", {"brightness": 50, "temp": 100})
        self.assertEqual(st["mode"], "white")
        self.assertIn("set_white_percentage", self.names())
        st = self.req("/api/power", {"on": False})
        self.assertFalse(st["on"])
        self.assertIn("turn_off", self.names())

    def test_effect_streams_frames_via_music_mode(self):
        self.bulb.calls.clear()
        self.req("/api/effect", {"id": "rainbow", "speed": 2})
        time.sleep(0.6)
        self.assertIn("set_mode", self.names())
        self.assertGreater(self.names().count("set_music_colour"), 3)
        self.req("/api/colour", {"h": 0.5, "s": 1})

    def test_presets_round_trip(self):
        self.req("/api/colour", {"h": 0.1, "s": 1, "brightness": 60})
        p = self.req("/api/presets", {"name": "Warm"})
        self.req("/api/white", {"brightness": 30, "temp": 0})
        st = self.req(f"/api/presets/{p['id']}/apply", {})
        self.assertEqual(st["mode"], "colour")
        self.assertEqual(st["brightness"], 60)

    def test_native_scene_sent_to_bulb(self):
        self.bulb.calls.clear()
        st = self.req("/api/scene", {"colors": ["#ff0000", "#00ff00"], "mode": "breathe", "speed": 80})
        self.assertEqual(st["mode"], "scene")
        call = next(c for c in self.bulb.calls if c[0] == "set_scene")
        self.assertEqual(call[1][0], server.SCENE_SLOT)
        self.assertEqual(len(call[1][1]), 4 * 26)

    def test_music_frames_fade_or_jump(self):
        self.bulb.calls.clear()
        self.req("/api/live", {"r": 255, "g": 0, "b": 0, "smooth": True})
        self.req("/api/live", {"r": 0, "g": 0, "b": 255, "smooth": False})
        trans = [c[1][0] for c in self.bulb.calls if c[0] == "set_music_colour"]
        self.assertEqual(trans, [1, 0])

    def test_rgbic_scene_goes_to_dp51(self):
        L = server.APP.light
        L.rgbic = True
        try:
            self.bulb.calls.clear()
            self.req("/api/scene", {"colors": ["#ff0000", "#0000ff"], "mode": "flow", "speed": 60})
            dps = [c[1][0] for c in self.bulb.calls if c[0] == "set_value"]
            self.assertEqual(dps, [21, 51])
            self.assertNotIn("set_scene", [c[0] for c in self.bulb.calls])
        finally:
            L.rgbic = False

    def test_bad_input_is_400(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.req("/api/effect", {"id": "nope"})
        self.assertEqual(cm.exception.code, 400)

    def test_static_index(self):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/") as r:
            self.assertIn(b"Lumora", r.read())


    def test_segments_only_resend_what_changed(self):
        server.SEG_GAP = 0
        L = server.APP.light
        L.set_colour(0.5, 1, 50)
        self.bulb.calls.clear()
        red, blue = (255, 0, 0), (0, 0, 255)
        L.paint_segments([red] * 10 + [blue] * 10)
        dp61 = lambda: [c for c in self.bulb.calls if c[0] == "set_value" and c[1][0] == 61]
        self.assertEqual(len(dp61()), 2)
        L.paint_segments([red] * 10 + [blue] * 10)          # nothing changed
        self.assertEqual(len(dp61()), 2)
        L.paint_segments([red] * 10 + [(0, 255, 0)] * 10)   # only the right half
        self.assertEqual(len(dp61()), 3)
        self.assertEqual(L.state["mode"], "segments")

    def test_desk_mode_and_manual_takeover(self):
        started = []

        class Dummy(threading.Thread):
            MODES = desk.DeskSync.MODES

            def __init__(self, engine, mode, intensity=1.0, use_mic=False, reverse=False):
                super().__init__(daemon=True)
                self.mode, self.intensity, self.use_mic, self.running = mode, intensity, use_mic, True
                started.append(self)

            def run(self):
                while self.running:
                    time.sleep(0.01)

            def stop(self):
                self.running = False

            def info(self):
                return {"mode": self.mode, "intensity": self.intensity}

        real, server.desk.DeskSync = server.desk.DeskSync, Dummy
        real_miss, server.desk.missing_deps = server.desk.missing_deps, lambda *a: []
        try:
            st = self.req("/api/desk", {"mode": "both", "intensity": 1.5})
            self.assertEqual(st["desk"], {"mode": "both", "intensity": 1.5})
            st = self.req("/api/desk", {"mode": "both", "intensity": 0.5})
            self.assertEqual(len(started), 1)  # slider move keeps the same capture
            self.assertEqual(st["desk"]["intensity"], 0.5)
            st = self.req("/api/colour", {"hex": "#ff0000"})
            self.assertEqual(st["desk"], {"mode": "off"})
            self.assertFalse(started[0].running)
        finally:
            server.desk.DeskSync, server.desk.missing_deps = real, real_miss
            server.APP.stop_desk()


@unittest.skipIf(desk.np is None, "numpy not installed")
class DeskAnalysisTests(unittest.TestCase):
    def test_vivid_pixels_win_over_grey(self):
        np = desk.np
        img = np.full((60, 100, 3), 40, np.uint8)  # dark grey scene
        img[:10, :10] = (255, 0, 0)                 # small neon red sign
        rgb, lum = desk.screen_colour(img)
        self.assertGreater(rgb[0], 200)
        self.assertLess(max(rgb[1], rgb[2]), 120)
        self.assertLess(lum, 0.2)

    def test_zones_left_to_right(self):
        np = desk.np
        img = np.zeros((30, 90, 3), np.uint8)
        img[:, :30] = (255, 0, 0)
        img[:, 30:60] = (0, 255, 0)
        img[:, 60:] = (0, 0, 255)
        z = desk.screen_zones(img, 3)
        self.assertEqual([max(range(3), key=lambda i: c[i]) for c in z], [0, 1, 2])

    def test_kick_drum_beats_and_pitch(self):
        np = desk.np
        an = desk.AudioAnalyser()
        t = np.arange(1024) / an.rate
        hat = 0.05 * np.sin(2 * np.pi * 6000 * t)
        kick = 0.8 * np.sin(2 * np.pi * 60 * t) + hat
        beats, now = 0, 0.0
        for i in range(80):  # ~23 ms blocks, a kick every 0.5 s
            now += 1024 / an.rate
            an.feed(kick if i % 21 == 0 else hat, now)
            beats += an.beat
        self.assertGreaterEqual(beats, 3)
        high = desk.AudioAnalyser()
        low = desk.AudioAnalyser()
        for _ in range(40):
            high.feed(0.3 * np.sin(2 * np.pi * 5000 * t))
            low.feed(0.3 * np.sin(2 * np.pi * 120 * t))
        self.assertGreater(high.centroid, low.centroid + 0.3)

    def test_silence_is_dim_not_crash(self):
        an = desk.AudioAnalyser()
        an.feed(desk.np.zeros(1024))
        self.assertFalse(an.beat)
        self.assertEqual(an.level, 0.0)


if __name__ == "__main__":
    unittest.main()
