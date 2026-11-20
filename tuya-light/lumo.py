#!/usr/bin/env python3
"""Lumora for ONE iPhone: control the bulb straight from a-Shell.

    python3 lumo.py                  menu (easiest)
    python3 lumo.py color purple     one-shot commands, e.g.
    python3 lumo.py scene synthwave fade 60
    python3 lumo.py white warm 70
    python3 lumo.py effect aurora
    python3 lumo.py off

No browser or second phone needed. Bulb scenes ("scene ...") are stored in
the bulb and keep animating after you close a-Shell.
"""
import colorsys
import concurrent.futures as cf
import ipaddress
import os
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import server  # noqa: E402  (reuses Lumora's bulb code, config and libraries)
import effects  # noqa: E402

CONFIG = server.CONFIG_PATH

COLOURS = {
    "red": "#ff0000", "orange": "#ff7a00", "yellow": "#ffd000", "lime": "#9dff00",
    "green": "#00ff40", "mint": "#3dffb0", "cyan": "#00e5ff", "sky": "#2aa8ff",
    "blue": "#0030ff", "purple": "#8e24ff", "violet": "#c400ff", "magenta": "#ff00d4",
    "pink": "#ff3cac", "rose": "#ff3c6f", "peach": "#ff9e6b", "white": "#ffffff",
}
PALETTES = {
    "synthwave": ["#ff2a6d", "#d300c5", "#7a04eb", "#05d9e8"],
    "sunset": ["#ffd56b", "#ff8c42", "#ff3c38", "#a23b72"],
    "ocean": ["#00d2d3", "#0080ff", "#0030a0", "#00ffa3"],
    "aurora": ["#00ffa3", "#00b3ff", "#7a00ff", "#00ff6a"],
    "forest": ["#0b6e4f", "#73a942", "#2d6a4f", "#b7e4c7"],
    "candy": ["#ffafcc", "#cdb4db", "#a2d2ff", "#ff8fab"],
    "cyberpunk": ["#fcee0a", "#ff003c", "#00f0ff"],
    "fire": ["#ff4800", "#ff9e00", "#9d0208", "#ffba08"],
    "rainbow": ["#ff0000", "#ff8000", "#ffff00", "#00ff00", "#00ffff", "#0000ff", "#8000ff", "#ff00ff"],
    "galaxy": ["#2a0845", "#6441a5", "#ff00cc", "#3333ff"],
    "diwali": ["#ff9933", "#ffd700", "#ff0066", "#ff6600"],
    "love": ["#ff1744", "#ff4081", "#d500f9"],
}
WHITES = {"candle": 0, "warm": 15, "neutral": 50, "day": 80, "cool": 100}

B = "\033[1m"
D = "\033[2m"
R = "\033[0m"


def swatch(hex_):
    r, g, b = effects.hex_to_rgb(hex_)
    return f"\033[48;2;{r};{g};{b}m   {R}"


def say(msg):
    print(msg, flush=True)


# ------------------------------------------------------------------ bulb

def load_light(quiet=False):
    cfg = server.load_json(CONFIG, {})
    dev = cfg.get("device") or {}
    light = server.Light()
    if not dev.get("id"):
        say(f"{B}No bulb set up yet.{R} Choose 's' (Setup) in the menu first.")
        return light, cfg
    if not quiet:
        say(f"{D}Connecting to your bulb...{R}")
    light.connect(dev)
    if light.dev is None:
        say(f"⚠️  Couldn't reach the bulb: {light.dev_error}")
        say("   Is the bulb on? Is it on this iPhone's hotspot? Try Setup > find bulb.")
    return light, cfg


def check(light, ok_msg):
    if light.dev is None:
        return
    if light.dev_error:
        say(f"⚠️  Bulb said: {light.dev_error}")
    else:
        say(f"✅ {ok_msg}")


def parse_colour(s):
    s = s.strip().lower()
    if s in COLOURS:
        return COLOURS[s]
    if not s.startswith("#"):
        s = "#" + s
    effects.hex_to_rgb(s)  # validates
    return s


def do_colour(light, name, bright=None):
    hx = parse_colour(name)
    r, g, b = effects.hex_to_rgb(hx)
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    light.set_colour(h, s, float(bright) if bright else max(1, round(v * 100)))
    check(light, f"Colour {swatch(hx)} {hx}")


def do_white(light, temp="warm", bright=80):
    t = WHITES.get(str(temp).lower(), None)
    if t is None:
        t = max(0, min(100, int(temp)))
    light.set_white(float(bright), t)
    check(light, f"White light, warmth {100 - t}%, brightness {bright}%")


def do_scene(light, pal, mode="fade", speed=50):
    cols = PALETTES.get(pal.lower()) if isinstance(pal, str) else pal
    if cols is None:
        cols = [parse_colour(c) for c in pal.split(",")]
    mode = {"fade": "gradient", "smooth": "gradient"}.get(mode, mode)
    if mode not in ("gradient", "breathe", "jump"):
        mode = "gradient"
    try:
        light.native_scene(cols, mode, int(speed))
    except ValueError as e:
        say(f"⚠️  {e}")
        return
    check(light, "Saved into the bulb: " + "".join(swatch(c) for c in cols)
          + f"  ({mode}, speed {speed}). It keeps running after you close a-Shell.")


def do_effect(light, eid, speed=1.0, bright=100, colours=None):
    if eid not in effects.EFFECTS:
        say("Unknown effect. Options: " + ", ".join(effects.EFFECTS))
        return
    fps = float(server.load_json(CONFIG, {}).get("fps", 12))
    smooth = eid not in effects.HARD_EFFECTS
    say(f"{B}{effects.EFFECTS[eid][2]} {effects.EFFECTS[eid][1]}{R} running. Keep a-Shell open. "
        f"{B}Ctrl+C{R} (or the ⌃ key then C) to stop.")
    state, t0, last = {}, time.time(), time.time()
    clock = 0.0
    try:
        while True:
            now = time.time()
            clock += (now - last) * speed
            last = now
            rgb = effects.render(eid, clock, {"colors": colours or []}, state, bright / 100)
            light.stream(rgb, smooth)
            sys.stdout.write("\r  " + swatch(effects.rgb_to_hex(rgb)) + f" {int(now - t0)}s ")
            sys.stdout.flush()
            time.sleep(1 / fps)
    except KeyboardInterrupt:
        say("\nStopped.")


def do_sleep(light, minutes=30):
    st = light.state
    start_b = st["brightness"]
    steps = max(1, int(minutes * 6))  # every 10 seconds
    say(f"😴 Fading to off over {minutes} min. Keep a-Shell open. Ctrl+C to cancel.")
    try:
        for i in range(steps, 0, -1):
            b = max(1, round(start_b * i / steps))
            if st["mode"] == "white":
                light.set_white(b, st["temp"])
            else:
                light.set_colour(st["h"], st["s"], b)
            sys.stdout.write(f"\r  brightness {b}%   ")
            sys.stdout.flush()
            time.sleep(10)
        light.power(False)
        say("\nGood night 🌙")
    except KeyboardInterrupt:
        say("\nCancelled.")


# ------------------------------------------------------------------ setup

def candidate_hosts():
    """Hosts to probe: the iPhone hotspot range plus this phone's own /24."""
    hosts = [f"172.20.10.{i}" for i in range(2, 15)]
    try:
        net = ipaddress.ip_network(server.lan_ip() + "/24", strict=False)
        hosts += [str(h) for h in net.hosts() if str(h) not in hosts]
    except ValueError:
        pass
    return hosts


def port_open(host):
    try:
        with socket.create_connection((host, 6668), timeout=0.6):
            return host
    except OSError:
        return None


def find_bulb(dev):
    """Find which IP answers with this bulb's key."""
    say(f"{D}Looking for Tuya devices on the hotspot (up to a minute)...{R}")
    with cf.ThreadPoolExecutor(32) as ex:
        found = [h for h in ex.map(port_open, candidate_hosts()) if h]
    if not found:
        say("No Tuya devices answered. Is the bulb powered on and joined to this iPhone's hotspot?")
        return None
    say(f"Found device(s) at: {', '.join(found)}")
    for ip in found:
        for ver in ([dev.get("version")] if dev.get("version") else []) + ["3.3", "3.4", "3.5", "3.1"]:
            light = server.Light()
            light.connect({**dev, "ip": ip, "version": ver})
            if light.dev is not None:
                light.close()
                say(f"✅ Your bulb is at {ip} (protocol {ver})")
                return {**dev, "ip": ip, "version": ver}
    say("Found devices, but none accepted this Local Key. Re-fetch the key in Setup.")
    return None


def ask(prompt, default=""):
    v = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return v or default


def setup():
    cfg = server.load_json(CONFIG, {})
    say(f"\n{B}Setup{R}")
    say("  1) Get my bulb's key from Tuya (needs iot.tuya.com Access ID + Secret)")
    say("  2) Type Device ID and Local Key myself")
    say("  3) Find my bulb on the hotspot again (if it stopped connecting)")
    c = ask("Choose", "1")
    dev = dict(cfg.get("device") or {})
    if c == "1":
        say("Data centres: in = India, us = Americas, eu = Europe, sg = Singapore, cn = China")
        region = ask("Data centre", cfg.get("region", "in"))
        key = ask("Access ID")
        secret = ask("Access Secret")
        try:
            devs = server.cloud_devices({"region": region, "apiKey": key, "apiSecret": secret})
        except ValueError as e:
            say(f"❌ {e}")
            return
        if not devs:
            say("No devices found. Did you link your Smart Life app to the Tuya project?")
            return
        for i, d in enumerate(devs, 1):
            say(f"  {i}) {d['name']}  ({d['id']})")
        pick = int(ask("Which one is your bulb", "1")) - 1
        dev = {k: str(devs[pick].get(k) or "") for k in ("id", "key", "version")}
        dev["ip"] = ""
        cfg["region"] = region
    elif c == "2":
        dev["id"] = ask("Device ID", dev.get("id", ""))
        dev["key"] = ask("Local Key", dev.get("key", ""))
        dev["version"] = ask("Protocol version (3.3 / 3.4)", dev.get("version") or "3.3")
        dev["ip"] = ask("Bulb IP (leave blank to search)", dev.get("ip", ""))
    if not dev.get("id") or not dev.get("key"):
        say("Need a Device ID and Local Key first.")
        return
    if not dev.get("ip") or c == "3":
        found = find_bulb(dev)
        if not found:
            cfg["device"] = dev
            server.save_json(CONFIG, cfg)
            return
        dev = found
    cfg["device"] = dev
    server.save_json(CONFIG, cfg)
    say("Saved. Try a colour now! 🎨")


# ------------------------------------------------------------------ menu

def menu():
    light, cfg = load_light()
    while True:
        on = "ON" if light.state["on"] else "off"
        say(f"\n{B}✨ Lumora{R}  {D}(bulb {'connected' if light.dev else 'not connected'}, {on}){R}")
        say("  1 Power on/off      2 Colour         3 White light")
        say("  4 💎 Bulb scene     5 Live effect    6 Brightness")
        say("  7 😴 Sleep fade     s Setup          q Quit")
        c = ask("Choose").lower()
        try:
            if c == "q":
                break
            if c == "s":
                setup()
                light.close()
                light, cfg = load_light()
            elif c == "1":
                light.power(not light.state["on"])
                check(light, "Light " + ("on" if light.state["on"] else "off"))
            elif c == "2":
                say("  " + "  ".join(f"{swatch(h)} {n}" for n, h in COLOURS.items()))
                do_colour(light, ask("Colour name or #hex", "pink"), ask("Brightness 1-100", "80"))
            elif c == "3":
                say("  candle · warm · neutral · day · cool   (or 0-100)")
                do_white(light, ask("Warmth", "warm"), ask("Brightness 1-100", "80"))
            elif c == "4":
                for n, cols in PALETTES.items():
                    say(f"  {n:<10} " + "".join(swatch(x) for x in cols))
                say(f"  {D}or your own colours, like red,#00ffaa,purple{R}")
                pal = ask("Palette", "synthwave")
                mode = ask("Style: fade / breathe / jump", "fade")
                do_scene(light, pal, mode, ask("Speed 1-100", "50"))
            elif c == "5":
                say("  " + "  ".join(f"{v[2]} {k}" for k, v in effects.EFFECTS.items()))
                eid = ask("Effect", "aurora")
                pal = None
                if effects.EFFECTS.get(eid, (0, 0, 0, False))[3]:
                    p = ask("Palette name (blank = default)", "")
                    pal = PALETTES.get(p.lower()) if p else None
                do_effect(light, eid, float(ask("Speed (0.2-4)", "1")), 100, pal)
            elif c == "6":
                light.set_brightness(float(ask("Brightness 1-100", "60")))
                check(light, "Brightness set")
            elif c == "7":
                do_sleep(light, float(ask("Minutes", "30")))
        except (ValueError, IndexError) as e:
            say(f"⚠️  {e}")
        except KeyboardInterrupt:
            say("")
    light.close()


def main(argv):
    if not argv:
        return menu()
    cmd, *a = argv
    if cmd == "setup":
        return setup()
    light, _ = load_light(quiet=True)
    if cmd in ("on", "off"):
        light.power(cmd == "on")
        check(light, f"Light {cmd}")
    elif cmd in ("color", "colour"):
        do_colour(light, a[0], a[1] if len(a) > 1 else None)
    elif cmd == "white":
        do_white(light, a[0] if a else "warm", a[1] if len(a) > 1 else 80)
    elif cmd == "scene":
        do_scene(light, a[0] if a else "synthwave", a[1] if len(a) > 1 else "fade", a[2] if len(a) > 2 else 50)
    elif cmd == "effect":
        do_effect(light, a[0] if a else "aurora", float(a[1]) if len(a) > 1 else 1.0)
    elif cmd in ("bright", "brightness"):
        light.set_brightness(float(a[0]))
        check(light, "Brightness set")
    elif cmd == "sleep":
        do_sleep(light, float(a[0]) if a else 30)
    else:
        say(__doc__)
    light.close()


if __name__ == "__main__":
    os.chdir(server.ROOT)
    main(sys.argv[1:])
