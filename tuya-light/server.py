#!/usr/bin/env python3
"""Lumora - local controller for Tuya WiFi RGB+CW (RGBCW) smart bulbs.

Run:  python server.py        then open http://localhost:8787
Works in demo mode (virtual bulb) until you add your bulb in Settings.
"""
import colorsys
import json
import os
import socket
import threading
import time
import uuid
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import effects

try:
    import tinytuya
except ImportError:  # demo mode still works without it
    tinytuya = None

ROOT = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(ROOT, "static")
CONFIG_PATH = os.path.join(ROOT, "config.json")
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
                self.music_ok = bool(d.bulb_has_capability("music"))
                self._read_device_state(st)
            except Exception as e:  # noqa: BLE001
                self.dev = None
                self.dev_error = str(e)

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
            if self.dev:
                self._call(self.dev.set_white_percentage, st["brightness"], st["temp"])

    def set_brightness(self, brightness):
        st = self.state
        if st["mode"] == "white":
            self.set_white(brightness, st["temp"])
        elif st["mode"] == "colour":
            self.set_colour(st["h"], st["s"], brightness)
        elif st["mode"] == "effect" and st["effect"]:
            st["effect"]["brightness"] = clamp(brightness, 1, 100)
            st["brightness"] = clamp(brightness, 1, 100)

    def stream(self, rgb):
        """Fast fire-and-forget frame (effects, music sync)."""
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
                self._call(d.set_music_colour, d.MUSIC_TRANSITION_JUMP, r, g, b, nowait=True)
            else:
                self._call(d.set_colour, r, g, b, nowait=True)
            self.frames += 1
            now = time.time()
            if now - self.last_drain > 1.5:
                self.last_drain = now
                self._drain()

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

    def live(self, rgb):
        with self.light.lock:
            self.light.state["mode"] = "live"
            self.light.state["effect"] = None
            self.last_live = time.time()
        self.light.stream(rgb)

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
            light.stream(rgb)
            time.sleep(1 / self.fps)
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

    def save_data(self):
        save_json(DATA_PATH, self.data)

    def state(self):
        s = self.light.snapshot()
        s["sleep"] = self.engine.sleep_info()
        return s


APP = None


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
        try:
            if path == "/api/power":
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
                E.live((float(b["r"]), float(b["g"]), float(b["b"])))
                return self.send_json({"ok": True})
            elif path == "/api/sleep":
                E.start_sleep(float(b.get("minutes", 0)))
            elif path == "/api/presets":
                p = {"id": uuid.uuid4().hex[:8], "name": (b.get("name") or "Preset")[:40],
                     "state": {k: L.state[k] for k in ("mode", "h", "s", "brightness", "temp", "effect", "preview")}}
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


def apply_preset(s):
    L, E = APP.light, APP.engine
    if s.get("mode") == "white":
        L.set_white(s["brightness"], s["temp"])
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


def main():
    global APP
    APP = App()
    port = int(os.environ.get("PORT") or APP.config.get("port") or 8787)
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    srv.daemon_threads = True
    mode = "connected to bulb" if APP.light.dev else ("DEMO mode (no bulb configured)"
                                                     if not APP.light.device_cfg else f"bulb error: {APP.light.dev_error}")
    print(f"\n  Lumora is running - {mode}")
    print(f"  This computer:  http://localhost:{port}")
    print(f"  Your phone:     http://{lan_ip()}:{port}  (same WiFi)\n")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
