"""Run: python -m unittest test_lumora -v"""
import json
import threading
import time
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

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

    def test_bad_input_is_400(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.req("/api/effect", {"id": "nope"})
        self.assertEqual(cm.exception.code, 400)

    def test_static_index(self):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/") as r:
            self.assertIn(b"Lumora", r.read())


if __name__ == "__main__":
    unittest.main()
