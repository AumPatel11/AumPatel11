#!/usr/bin/env python3
"""Lumora - local controller for Tuya WiFi RGB+CW (RGBCW) smart bulbs.

Run:  python server.py        then open http://localhost:8787
Works in demo mode (virtual bulb) until you add your bulb in Settings.
"""
import colorsys
import json
import os
import platform
import socket
import ssl
import sys
import threading
import time
import uuid
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
# Libraries unpacked by ios_install.py (iPhone can't run pip's installers).
# Appended last so anything the system already has wins.
if os.path.isdir(os.path.join(ROOT, "vendor")):
    sys.path.append(os.path.join(ROOT, "vendor"))

import desk  # noqa: E402
import effects  # noqa: E402

try:
    import tinytuya
except ImportError:  # demo mode still works without it
    tinytuya = None

STATIC = os.path.join(ROOT, "static")
CONFIG_PATH = os.path.join(ROOT, "config.json")
SCENE_SLOT = 10  # custom scene number written to DP 25
DATA_PATH = os.path.join(ROOT, "data.json")
WIZARD_PATH = os.path.join(ROOT, "devices.json")


def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def white_preview(brightness, temp):
    warm, cool = (255, 166, 77), (205, 225, 255)
    c = effects.mix(warm, cool, temp / 100)
    return effects.scale(c, 0.15 + 0.85 * brightness / 100)


# --------------------------------------------------------------------- light

class Light:
    """Tracks the bulb's state and (if configured) drives the real device."""

    def __init__(self):
        self.lock = threading.RLock()
        self.dev = None
        self.dev_error = None
        self.device_cfg = None
        self.music_ok = True
        self.in_stream_mode = False
        self.frames = 0
        self.last_drain = 0
        self.state = {
            "on": True,
            "mode": "colour",       # colour | white | effect | live
            "h": 0.92, "s": 0.8,    # hue / saturation 0..1
            "brightness": 80,       # 0..100
            "temp": 40,             # 0 warm .. 100 cool
            "effect": None,         # {id, speed, colors, brightness}
            "circadian": False,
            "scene": None,          # native bulb scene {colors, mode, speed}
            "preview": [255, 60, 170],
        }

    # ---- device connection
    def connect(self, cfg):
        with self.lock:
            self.close()
            self.device_cfg = cfg
            self.dev_error = None
            if not cfg or not cfg.get("id") or not cfg.get("key"):
                return
            if tinytuya is None:
                self.dev_error = "tinytuya not installed: pip install tinytuya"
                return
            try:
                d = tinytuya.BulbDevice(
                    cfg["id"], cfg.get("ip") or "Auto", cfg["key"],
                    version=float(cfg.get("version") or 3.3), persist=True,
                    connection_timeout=3, connection_retry_limit=2,
                    connection_retry_delay=1)
                d.set_socketPersistent(True)
                st = d.status()
                if isinstance(st, dict) and st.get("Error"):
                    raise RuntimeError(st.get("Error"))
                self.dev = d
                self.music_ok = self.has("music")
                self._read_device_state(st)
            except Exception as e:  # noqa: BLE001
                self.dev = None
                self.dev_error = str(e)

    def has(self, feature):
        # tinytuya raises KeyError for features a strip doesn't list at all
        try:
            return bool(self.dev.bulb_has_capability(feature))
        except Exception:  # noqa: BLE001
            return False

    def close(self):
        if self.dev:
            try:
                self.dev.close()
            except Exception:  # noqa: BLE001
                pass
        self.dev = None
        self.in_stream_mode = False

    def _read_device_state(self, st):
        try:
            d = self.dev
            on = d.state().get("is_on")
            if on is not None:
                self.state["on"] = bool(on)
            mode = d.get_mode()
            if mode == "white":
                self.state["mode"] = "white"
                self.state["brightness"] = round(d.get_brightness_percentage())
                self.state["temp"] = round(d.get_colourtemp_percentage())
            elif mode == "colour":
                h, s, v = d.colour_hsv()
                self.state.update(mode="colour", h=h, s=s, brightness=round(v * 100))
            self._update_preview()
        except Exception:  # noqa: BLE001
            pass

    def _call(self, fn, *a, **kw):
        if not self.dev:
            return
        try:
            r = fn(*a, **kw)
            if isinstance(r, dict) and r.get("Error"):
                self.dev_error = r.get("Error")
            else:
                self.dev_error = None
            return r
        except Exception as e:  # noqa: BLE001
            self.dev_error = str(e)

    def _drain(self):
        """Discard queued replies so fire-and-forget frames never fill the socket."""
        sock = getattr(self.dev, "socket", None)
        if not isinstance(sock, socket.socket):
            return
        try:
            sock.setblocking(False)
            while sock.recv(4096):
                pass
        except (BlockingIOError, OSError):
            pass
        finally:
            try:
                sock.settimeout(3)
            except OSError:
                pass

    # ---- high level actions (all update local state; device optional)
    def _update_preview(self):
        s = self.state
        if s["mode"] == "white":
            s["preview"] = [round(c) for c in white_preview(s["brightness"], s["temp"])]
        elif s["mode"] == "colour":
            s["preview"] = [round(c) for c in effects.hsv(s["h"], s["s"], max(0.12, s["brightness"] / 100))]

    def power(self, on):
        with self.lock:
            self.state["on"] = bool(on)
            self.in_stream_mode = False
            if self.dev:
                self._call(self.dev.turn_on if on else self.dev.turn_off)

    def set_colour(self, h, s, brightness):
        with self.lock:
            st = self.state
            st.update(mode="colour", h=h % 1.0, s=clamp(s, 0, 1),
                      brightness=clamp(brightness, 1, 100), effect=None, on=True)
            self.in_stream_mode = False
            self._update_preview()
            if self.dev:
                self._call(self.dev.set_hsv, st["h"], st["s"], st["brightness"] / 100)

    def set_white(self, brightness, temp):
        with self.lock:
            st = self.state
            st.update(mode="white", brightness=clamp(brightness, 1, 100),
                      temp=clamp(temp, 0, 100), effect=None, on=True)
            self.in_stream_mode = False
            self._update_preview()
            if not self.dev:
                return
            if self.has("white"):
                self._call(self.dev.set_white_percentage, st["brightness"], st["temp"])
            else:  # RGB-only strips (no white LEDs): mix the white from RGB
                r, g, b = (round(c) for c in white_preview(st["brightness"], st["temp"]))
                self._call(self.dev.set_colour, r, g, b)

    def set_brightness(self, brightness):
        st = self.state
        if st["mode"] == "white":
            self.set_white(brightness, st["temp"])
        elif st["mode"] == "colour":
            self.set_colour(st["h"], st["s"], brightness)
        elif st["mode"] == "effect" and st["effect"]:
            st["effect"]["brightness"] = clamp(brightness, 1, 100)
            st["brightness"] = clamp(brightness, 1, 100)
        elif st["mode"] == "scene" and st["scene"]:
            st["brightness"] = clamp(brightness, 1, 100)
            sc = st["scene"]
            self.native_scene(sc["colors"], sc["mode"], sc["speed"])

    def stream(self, rgb, smooth=True):
        """Fast fire-and-forget frame (effects, music sync).

        smooth=True asks the bulb to fade into the new colour itself, which
        hides the gaps between frames and makes effects look seamless.
        """
        with self.lock:
            r, g, b = (clamp(c, 0, 255) for c in rgb)
            if max(r, g, b) < 3:  # Tuya rejects V=0; keep a faint glow
                r, g, b = max(r, 3), max(g, 3), max(b, 3)
            self.state["preview"] = [round(r), round(g), round(b)]
            self.state["on"] = True
            if not self.dev:
                return
            d = self.dev
            if self.music_ok:
                if not self.in_stream_mode:
                    self._call(d.set_mode, "music")
                    self.in_stream_mode = True
                tr = d.MUSIC_TRANSITION_FADE if smooth else d.MUSIC_TRANSITION_JUMP
                self._call(d.set_music_colour, tr, r, g, b, nowait=True)
            else:
                self._call(d.set_colour, r, g, b, nowait=True)
            self.frames += 1
            now = time.time()
            if now - self.last_drain > 1.5:
                self.last_drain = now
                self._drain()

    def native_scene(self, colors, mode, speed):
        """Store an animated scene in the bulb. It then runs on its own,
        perfectly smooth, even with every phone asleep."""
        with self.lock:
            st = self.state
            st.update(mode="scene", on=True, effect=None,
                      scene={"colors": colors, "mode": mode, "speed": speed})
            self.in_stream_mode = False
            if not self.dev:
                return
            if not self.has("scene_data"):
                raise ValueError("This bulb doesn't accept custom scenes - use Effects instead")
            k = st["brightness"] / 100
            dimmed = [effects.rgb_to_hex(effects.scale(effects.hex_to_rgb(c), k)) for c in colors]
            self._call(self.dev.set_scene, SCENE_SLOT, effects.scene_data(dimmed, mode, speed))

    def snapshot(self):
        with self.lock:
            s = dict(self.state)
            s["effect"] = dict(s["effect"]) if s["effect"] else None
            s["connected"] = self.dev is not None
            s["demo"] = not (self.device_cfg and self.device_cfg.get("id"))
            s["error"] = self.dev_error
            return s


# -------------------------------------------------------------------- engine

class Engine(threading.Thread):
    """Renders effects, runs sleep timers, sunrise alarms and circadian white."""

    def __init__(self, light, data, fps):
        super().__init__(daemon=True)
        self.light = light
        self.data = data
        self.fps = clamp(float(fps), 2, 25)
        self.effect_started = 0.0
        self.effect_clock = 0.0
        self.effect_state = {}
        self.last_tick = time.time()
        self.sleep = None          # {start, end, from}
        self.last_live = 0.0
        self.last_circadian = 0.0
        self.fired = set()

    def start_effect(self, eid, speed=1.0, colors=None, brightness=None, extra=None):
        if eid not in effects.EFFECTS:
            raise ValueError("unknown effect")
        with self.light.lock:
            st = self.light.state
            st["mode"] = "effect"
            st["on"] = True
            st["effect"] = {
                "id": eid, "speed": clamp(float(speed), 0.1, 5),
                "colors": colors or [],
                "brightness": clamp(brightness if brightness is not None else st["brightness"], 1, 100),
                **(extra or {}),
            }
            self.effect_clock = 0.0
            self.effect_state = {}

    def update_effect(self, **kw):
        with self.light.lock:
            e = self.light.state.get("effect")
            if e:
                for k, v in kw.items():
                    if v is not None:
                        e[k] = v

    def live(self, rgb, smooth=True):
        with self.light.lock:
            self.light.state["mode"] = "live"
            self.light.state["effect"] = None
            self.last_live = time.time()
        self.light.stream(rgb, smooth)

    def start_sleep(self, minutes):
        if minutes <= 0:
            self.sleep = None
            return
        now = time.time()
        self.sleep = {"start": now, "end": now + minutes * 60,
                      "from": self.light.state["brightness"]}

    def sleep_info(self):
        if not self.sleep:
            return None
        return {"remaining": max(0, round(self.sleep["end"] - time.time()))}

    def run(self):
        while True:
            try:
                self.tick()
            except Exception as e:  # noqa: BLE001 - keep the engine alive
                print("engine error:", e)
                time.sleep(0.5)

    def tick(self):
        now = time.time()
        dt = now - self.last_tick
        self.last_tick = now
        light = self.light
        st = light.state

        self.check_alarms()
        dim = self.apply_sleep(now)

        if st["mode"] == "effect" and st["effect"] and st["on"]:
            e = st["effect"]
            self.effect_clock += dt * e.get("speed", 1)
            params = {"colors": e.get("colors"), "duration": e.get("duration", 900)}
            k = e.get("brightness", 100) / 100 * dim
            rgb = effects.render(e["id"], self.effect_clock, params, self.effect_state, k)
            light.stream(rgb, smooth=e["id"] not in effects.HARD_EFFECTS)
            time.sleep(1 / self.fps)
            return

        if st["mode"] == "scene" and st.get("scene"):
            sc = st["scene"]
            self.effect_clock += dt
            rgb = effects.scene_preview(self.effect_clock, sc["colors"], sc["mode"], sc["speed"])
            st["preview"] = [round(c * st["brightness"] / 100) for c in rgb]
            time.sleep(0.1)
            return

        if st["mode"] == "white" and st.get("circadian") and now - self.last_circadian > 60:
            self.last_circadian = now
            h = datetime.now().hour + datetime.now().minute / 60
            light.set_white(effects.circadian_brightness(h), effects.circadian_temp(h))
            light.state["circadian"] = True
        time.sleep(0.1)

    def apply_sleep(self, now):
        sl = self.sleep
        if not sl:
            return 1.0
        k = (now - sl["start"]) / (sl["end"] - sl["start"])
        if k >= 1:
            self.sleep = None
            self.light.power(False)
            return 1.0
        st = self.light.state
        if st["mode"] in ("colour", "white") and int(now) % 10 == 0 and sl.get("last") != int(now):
            sl["last"] = int(now)
            b = max(1, round(sl["from"] * (1 - k)))
            if st["mode"] == "white":
                self.light.set_white(b, st["temp"])
            else:
                self.light.set_colour(st["h"], st["s"], b)
        return 1 - k

    def check_alarms(self):
        now = datetime.now()
        key_base = now.strftime("%Y-%m-%d %H:%M")
        for a in self.data.get("alarms", []):
            if not a.get("enabled"):
                continue
            dur = int(a.get("duration", 15))
            # start early so the light is fully up at the alarm time
            start = datetime.strptime(a["time"], "%H:%M")
            start_min = (start.hour * 60 + start.minute - dur) % 1440
            if now.hour * 60 + now.minute != start_min:
                continue
            days = a.get("days") or list(range(7))
            if now.weekday() not in days:
                continue
            key = a["id"] + key_base
            if key in self.fired:
                continue
            self.fired.add(key)
            self.start_effect("sunrise", 1.0, brightness=100, extra={"duration": dur * 60})


# ---------------------------------------------------------------------- http

class App:
    def __init__(self):
        self.config = load_json(CONFIG_PATH, {})
        self.data = load_json(DATA_PATH, {"presets": [], "alarms": []})
        self.data.setdefault("presets", [])
        self.data.setdefault("alarms", [])
        self.light = Light()
        self.light.connect(self.config.get("device"))
        self.engine = Engine(self.light, self.data, self.config.get("fps", 12))
        self.engine.start()
        self.desk = None
        self.desk_lock = threading.Lock()

    def start_desk(self, mode, intensity=1.0, mic=False):
        if mode not in desk.DeskSync.MODES:
            raise ValueError("mode must be off, screen, music or both")
        miss = desk.missing_deps(mode != "music", mode != "screen")
        if miss:
            raise ValueError("Desk Sync needs: pip install -r requirements-desk.txt (missing "
                             + ", ".join(miss) + ")")
        intensity = clamp(float(intensity), 0.2, 2.0)
        with self.desk_lock:
            d = self.desk
            if d and d.running and d.mode == mode and d.use_mic == bool(mic):
                d.intensity = intensity  # just a slider move: keep the capture threads
                return
            self._stop_desk()
            self.desk = desk.DeskSync(self.engine, mode, intensity=intensity, use_mic=bool(mic))
            self.desk.start()

    def _stop_desk(self):
        if self.desk:
            self.desk.stop()
            self.desk.join(0.5)  # so its last frame can't land after a manual colour
            self.desk = None

    def stop_desk(self):
        with self.desk_lock:
            self._stop_desk()

    def save_data(self):
        save_json(DATA_PATH, self.data)

    def state(self):
        s = self.light.snapshot()
        s["sleep"] = self.engine.sleep_info()
        d = self.desk
        s["desk"] = d.info() if d else {"mode": "off"}
        return s


APP = None
MANUAL_PATHS = {"/api/power", "/api/colour", "/api/white", "/api/brightness",
                "/api/effect", "/api/live", "/api/scene"}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=STATIC, **kw)

    def log_message(self, fmt, *args):  # quiet
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        return json.loads(self.rfile.read(n) or b"{}")

    # ---- GET
    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/state":
            return self.send_json(APP.state())
        if path == "/api/stream":
            return self.sse()
        if path == "/api/effects":
            return self.send_json(effects.effect_list())
        if path == "/api/presets":
            return self.send_json(APP.data["presets"])
        if path == "/api/alarms":
            return self.send_json(APP.data["alarms"])
        if path == "/api/config":
            dev = dict(APP.config.get("device") or {})
            if dev.get("key"):
                dev["key"] = dev["key"][:2] + "•" * 10 + dev["key"][-2:]
            return self.send_json({"device": dev, "fps": APP.engine.fps,
                                   "tinytuya": tinytuya is not None,
                                   "lan": lan_ip()})
        if path == "/api/wizard-devices":
            devs = load_json(WIZARD_PATH, [])
            return self.send_json([{"name": d.get("name"), "id": d.get("id"), "key": d.get("key"),
                                    "ip": d.get("ip", ""), "version": d.get("version", "3.3")}
                                   for d in devs if d.get("id") and d.get("key")])
        if path == "/api/scan":
            if tinytuya is None:
                return self.send_json({"error": "tinytuya not installed"}, 400)
            found = tinytuya.deviceScan(False, 2)
            return self.send_json([{"ip": ip, "id": d.get("gwId"), "version": d.get("version"),
                                    "product": d.get("productKey")} for ip, d in found.items()])
        if path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            while True:
                self.wfile.write(b"data: " + json.dumps(APP.state()).encode() + b"\n\n")
                self.wfile.flush()
                time.sleep(0.12)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    # ---- POST
    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            b = self.body()
        except ValueError:
            return self.send_json({"error": "bad json"}, 400)
        L, E = APP.light, APP.engine
        if path in MANUAL_PATHS or path.startswith("/api/presets/"):
            APP.stop_desk()  # touching the light by hand takes over from Desk Sync
        try:
            if path == "/api/desk":
                if b.get("mode", "off") == "off":
                    APP.stop_desk()
                else:
                    APP.start_desk(b["mode"], b.get("intensity", 1.0), b.get("mic", False))
            elif path == "/api/power":
                L.power(b.get("on", not L.state["on"]))
            elif path == "/api/colour":
                if "hex" in b:
                    r, g, bb = effects.hex_to_rgb(b["hex"])
                    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, bb / 255)
                    L.set_colour(h, s, b.get("brightness", max(1, round(v * 100))))
                else:
                    L.set_colour(float(b["h"]), float(b["s"]), float(b.get("brightness", L.state["brightness"])))
            elif path == "/api/white":
                L.set_white(float(b.get("brightness", L.state["brightness"])), float(b.get("temp", L.state["temp"])))
                L.state["circadian"] = bool(b.get("circadian", False))
                E.last_circadian = 0
            elif path == "/api/brightness":
                L.set_brightness(float(b["value"]))
            elif path == "/api/effect":
                if b.get("id"):
                    E.start_effect(b["id"], b.get("speed", 1), b.get("colors"), b.get("brightness"))
                else:
                    E.update_effect(speed=b.get("speed"), colors=b.get("colors"), brightness=b.get("brightness"))
            elif path == "/api/live":
                E.live((float(b["r"]), float(b["g"]), float(b["b"])), bool(b.get("smooth", True)))
                return self.send_json({"ok": True})
            elif path == "/api/cloud-devices":
                return self.send_json(cloud_devices(b))
            elif path == "/api/scene":
                cols = [c for c in (b.get("colors") or []) if isinstance(c, str)][:8]
                if not cols:
                    raise ValueError("pick at least one colour")
                mode = b.get("mode") if b.get("mode") in ("gradient", "jump", "breathe") else "gradient"
                L.native_scene(cols, mode, int(b.get("speed", 50)))
            elif path == "/api/sleep":
                E.start_sleep(float(b.get("minutes", 0)))
            elif path == "/api/presets":
                p = {"id": uuid.uuid4().hex[:8], "name": (b.get("name") or "Preset")[:40],
                     "state": {k: L.state[k] for k in ("mode", "h", "s", "brightness", "temp", "effect", "scene", "preview")}}
                APP.data["presets"].append(p)
                APP.save_data()
                return self.send_json(p)
            elif path.startswith("/api/presets/") and path.endswith("/apply"):
                pid = path.split("/")[3]
                p = next((x for x in APP.data["presets"] if x["id"] == pid), None)
                if not p:
                    return self.send_json({"error": "not found"}, 404)
                apply_preset(p["state"])
            elif path == "/api/alarms":
                a = {"id": b.get("id") or uuid.uuid4().hex[:8], "time": b["time"],
                     "duration": int(b.get("duration", 15)), "days": b.get("days") or list(range(7)),
                     "enabled": bool(b.get("enabled", True))}
                datetime.strptime(a["time"], "%H:%M")
                APP.data["alarms"] = [x for x in APP.data["alarms"] if x["id"] != a["id"]] + [a]
                APP.save_data()
            elif path == "/api/config":
                dev = b.get("device") or {}
                old = APP.config.get("device") or {}
                if dev.get("key", "").count("•"):
                    dev["key"] = old.get("key", "")
                APP.config["device"] = {k: str(dev.get(k, "")).strip() for k in ("id", "ip", "key", "version")}
                if "fps" in b:
                    APP.config["fps"] = APP.engine.fps = clamp(float(b["fps"]), 2, 25)
                save_json(CONFIG_PATH, APP.config)
                L.connect(APP.config["device"])
            else:
                return self.send_json({"error": "not found"}, 404)
        except (KeyError, TypeError, ValueError) as e:
            return self.send_json({"error": str(e)}, 400)
        except Exception as e:  # noqa: BLE001 - always answer the phone
            return self.send_json({"error": f"{type(e).__name__}: {e}"}, 500)
        return self.send_json(APP.state())

    def do_DELETE(self):
        path = self.path.split("?")[0]
        parts = path.strip("/").split("/")
        if len(parts) == 3 and parts[1] in ("presets", "alarms"):
            APP.data[parts[1]] = [x for x in APP.data[parts[1]] if x["id"] != parts[2]]
            APP.save_data()
            return self.send_json({"ok": True})
        if path == "/api/config":
            APP.config.pop("device", None)
            save_json(CONFIG_PATH, APP.config)
            APP.light.connect(None)
            return self.send_json({"ok": True})
        self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)


def cloud_devices(b):
    """Fetch device IDs + local keys from the Tuya IoT cloud (one time)."""
    if tinytuya is None:
        raise ValueError("tinytuya not installed")
    region = (b.get("region") or "us").strip()
    key, secret = (b.get("apiKey") or "").strip(), (b.get("apiSecret") or "").strip()
    if not key or not secret:
        raise ValueError("enter your Access ID and Access Secret")
    try:
        c = tinytuya.Cloud(apiRegion=region, apiKey=key, apiSecret=secret,
                           configFile=os.path.join(ROOT, "tinytuya-cloud.json"))
        if c.error:
            raise ValueError(str(c.error.get("Payload") or c.error))
        devs = c.getdevices()
    except ValueError:
        raise
    except Exception as e:  # noqa: BLE001 - network problems etc.
        raise ValueError(f"Couldn't reach Tuya ({type(e).__name__}). Is this phone online?") from e
    if isinstance(devs, dict):
        raise ValueError(str(devs.get("Payload") or devs.get("Error") or devs))
    out = [{"name": d.get("name"), "id": d.get("id"), "key": d.get("key"),
            "ip": d.get("ip", ""), "version": d.get("version", "3.3")}
           for d in devs if d.get("id") and d.get("key")]
    save_json(WIZARD_PATH, out)
    return out


def apply_preset(s):
    L, E = APP.light, APP.engine
    if s.get("mode") == "white":
        L.set_white(s["brightness"], s["temp"])
    elif s.get("mode") == "scene" and s.get("scene"):
        sc = s["scene"]
        L.native_scene(sc["colors"], sc["mode"], sc["speed"])
    elif s.get("mode") == "effect" and s.get("effect"):
        e = s["effect"]
        E.start_effect(e["id"], e.get("speed", 1), e.get("colors"), e.get("brightness"))
    else:
        L.set_colour(s.get("h", 0), s.get("s", 1), s.get("brightness", 80))


def lan_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        # dropped connections / rejected certificates are normal on phones
        err = sys.exc_info()[1]
        if isinstance(err, (ssl.SSLError, ConnectionError, TimeoutError, OSError)):
            return
        super().handle_error(request, client_address)


def on_iphone():
    if APP and APP.config.get("ios"):  # set by ios_install.py
        return True
    return platform.machine().startswith(("iPhone", "iPad", "iPod"))


def https_context(ip):
    """Self-signed certificate so Safari allows the microphone (music sync)."""
    import certgen
    cert, key = os.path.join(ROOT, "cert.pem"), os.path.join(ROOT, "key.pem")
    stamp = os.path.join(ROOT, "cert.ip")
    if not (os.path.exists(cert) and os.path.exists(key)) or load_json(stamp, None) != ip:
        print("  Creating HTTPS certificate (one time, a few seconds)...")
        c, k = certgen.make_self_signed(ips=sorted({"127.0.0.1", ip}))
        with open(cert, "w") as f:
            f.write(c)
        with open(key, "w") as f:
            f.write(k)
        save_json(stamp, ip)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)
    return ctx


def main():
    global APP
    APP = App()
    port = int(os.environ.get("PORT") or APP.config.get("port") or 8787)
    os.chdir(ROOT)
    use_https = "--http" not in sys.argv and ("--https" in sys.argv or APP.config.get("https") or on_iphone())
    ip = lan_ip()
    try:
        srv = Server(("0.0.0.0", port), Handler)
    except OSError:
        print(f"\n  Port {port} is busy - Lumora is probably already running.")
        print("  Close the other copy (Ctrl+C there), or open the address it shows.\n")
        return
    if use_https:
        srv.socket = https_context(ip).wrap_socket(srv.socket, server_side=True,
                                                   do_handshake_on_connect=False)
    scheme = "https" if use_https else "http"
    mode = "connected to bulb" if APP.light.dev else ("DEMO mode (no bulb configured)"
                                                     if not APP.light.device_cfg else f"bulb error: {APP.light.dev_error}")
    print(f"\n  Lumora is running - {mode}")
    if on_iphone():
        print("\n  On your OTHER iPhone, open Safari and go to:\n")
        print(f"      {scheme}://{ip}:{port}\n")
        print("  (Not 'localhost' - that only means the phone you type it on.)")
        if ip.startswith("127.") or ip == "0.0.0.0":
            print("  !! This phone has no WiFi address. Join the hotspot, then restart Lumora.")
        print("  Keep THIS screen open: iPhone pauses Lumora if you leave a-Shell.")
    else:
        print(f"  On this device:      {scheme}://localhost:{port}")
        print(f"  From another phone:  {scheme}://{ip}:{port}   (same WiFi / hotspot)")
    if use_https:
        print("  Safari will warn 'Not Private' - tap Show Details > visit this website.")
    print()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
