"""Lumora effect engine: pure functions that turn time -> RGB.

Every effect is a function ``fn(t, p, state) -> (r, g, b)`` where
  t      seconds since the effect started (already multiplied by speed)
  p      the effect params dict (colors, etc.)
  state  a per-run dict the effect may use to remember things (random seeds...)
and r, g, b are floats in 0..255. Global brightness is applied afterwards.
"""
import colorsys
import math
import random


def hex_to_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(c)))) for c in rgb)


def lerp(a, b, k):
    return a + (b - a) * k


def mix(c1, c2, k):
    return tuple(lerp(a, b, k) for a, b in zip(c1, c2))


def scale(c, k):
    return tuple(x * k for x in c)


def hsv(h, s=1.0, v=1.0):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return (r * 255, g * 255, b * 255)


def smooth(k):
    return k * k * (3 - 2 * k)


def palette(p, default):
    cols = [hex_to_rgb(c) for c in (p.get("colors") or []) if isinstance(c, str)]
    return cols or [hex_to_rgb(c) for c in default]


def noise1(x, seed=0):
    """Cheap smooth 1D value noise in 0..1."""
    def rnd(i):
        n = (i * 374761393 + seed * 668265263) & 0xFFFFFFFF
        n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
        return (n & 0xFFFF) / 65535.0
    i = math.floor(x)
    f = x - i
    return lerp(rnd(i), rnd(i + 1), smooth(f))


def flow(cols, pos):
    """Walk smoothly around a closed loop of colours. pos in 'colour units'."""
    n = len(cols)
    if n == 1:
        return cols[0]
    i = int(math.floor(pos)) % n
    k = smooth(pos - math.floor(pos))
    return mix(cols[i], cols[(i + 1) % n], k)


# ---------------------------------------------------------------- effects

def fx_solid(t, p, s):
    return palette(p, ["#ff3cac"])[0]


def fx_breathe(t, p, s):
    cols = palette(p, ["#ff3cac", "#784ba0", "#2b86c5"])
    cycle = 4.0
    idx = int(t // cycle) % len(cols)
    phase = (t % cycle) / cycle
    level = 0.08 + 0.92 * (0.5 - 0.5 * math.cos(phase * 2 * math.pi)) ** 1.6
    return scale(cols[idx], level)


def fx_rainbow(t, p, s):
    return hsv(t / 12.0)


def fx_gradient(t, p, s):
    cols = palette(p, ["#ff6a00", "#ee0979", "#7b2ff7", "#00c6ff"])
    return flow(cols, t / 3.0)


def fx_candle(t, p, s):
    base = palette(p, ["#ff8a1f"])[0]
    n = 0.55 * noise1(t * 3.1, 1) + 0.3 * noise1(t * 9.7, 2) + 0.15 * noise1(t * 23.0, 3)
    level = 0.45 + 0.55 * n
    warm = mix(base, (255, 60, 0), (1 - n) * 0.35)
    return scale(warm, level)


def fx_fireplace(t, p, s):
    n = noise1(t * 2.2, 7) * 0.6 + noise1(t * 7.5, 8) * 0.4
    col = mix((180, 20, 0), (255, 150, 20), n)
    return scale(col, 0.5 + 0.5 * noise1(t * 5.0, 9))


def fx_aurora(t, p, s):
    cols = palette(p, ["#00ffa3", "#00b3ff", "#7a00ff", "#00ff6a"])
    pos = noise1(t * 0.25, 11) * len(cols) * 2
    level = 0.55 + 0.45 * noise1(t * 0.7, 12)
    return scale(flow(cols, pos), level)


def fx_ocean(t, p, s):
    wave = 0.5 + 0.5 * math.sin(t * 0.9) * math.sin(t * 0.37 + 1)
    col = mix((0, 40, 140), (0, 200, 200), wave)
    return scale(col, 0.6 + 0.4 * noise1(t * 0.8, 21))


def fx_lava(t, p, s):
    cols = palette(p, ["#ff0080", "#ff4d00", "#ffb300", "#c400ff"])
    return flow(cols, noise1(t * 0.15, 31) * len(cols) * 3)


def fx_storm(t, p, s):
    base = (10, 14, 60)
    nxt = s.setdefault("next", t + random.uniform(1.5, 5))
    if t >= nxt:
        s["flash_start"] = t
        s["flashes"] = random.choice([1, 2, 3])
        s["next"] = t + random.uniform(2, 7)
    fs = s.get("flash_start")
    if fs is not None:
        dt = t - fs
        if dt < 0.12 * s.get("flashes", 1) * 2:
            if int(dt / 0.12) % 2 == 0:
                return (230, 230, 255)
            return base
    return scale(base, 0.7 + 0.3 * noise1(t, 41))


def fx_heartbeat(t, p, s):
    col = palette(p, ["#ff1744"])[0]
    ph = t % 1.2

    def bump(x, c, w):
        return math.exp(-((x - c) / w) ** 2)
    level = 0.12 + 0.88 * max(bump(ph, 0.10, 0.06), 0.7 * bump(ph, 0.33, 0.07))
    return scale(col, level)


def fx_police(t, p, s):
    ph = t % 1.0
    if ph < 0.5:
        return (255, 0, 0) if int(ph * 12) % 2 == 0 else (8, 0, 0)
    return (0, 40, 255) if int(ph * 12) % 2 == 0 else (0, 0, 8)


def fx_party(t, p, s):
    beat = int(t * 2.5)
    if s.get("beat") != beat:
        s["beat"] = beat
        s["hue"] = (s.get("hue", 0) + random.uniform(0.2, 0.5)) % 1
    return hsv(s["hue"])


def fx_strobe(t, p, s):
    col = palette(p, ["#ffffff"])[0]
    return col if (t * 10) % 1 < 0.35 else scale(col, 0.02)


def fx_sunset(t, p, s):
    cols = [hex_to_rgb(c) for c in ["#ffd56b", "#ff8c42", "#ff3c38", "#a23b72", "#2e1f6b"]]
    pos = (0.5 - 0.5 * math.cos(t / 40.0 * math.pi)) * (len(cols) - 1)
    i = min(int(pos), len(cols) - 2)
    return mix(cols[i], cols[i + 1], smooth(pos - i))


def fx_galaxy(t, p, s):
    cols = palette(p, ["#2a0845", "#6441a5", "#ff00cc", "#3333ff"])
    twinkle = 1.0 if noise1(t * 6, 51) > 0.9 else 0.0
    base = flow(cols, t / 6.0)
    return mix(base, (255, 255, 255), twinkle * 0.6)


def fx_sunrise(t, p, s):
    """Wake-up light: dim red -> orange -> bright warm white over `duration` seconds."""
    dur = max(30.0, float(p.get("duration", 900)))
    k = min(1.0, t / dur)
    stops = [(0.0, (40, 0, 0)), (0.3, (180, 30, 0)), (0.6, (255, 120, 20)),
             (0.85, (255, 190, 110)), (1.0, (255, 235, 200))]
    for (k0, c0), (k1, c1) in zip(stops, stops[1:]):
        if k <= k1:
            return mix(c0, c1, smooth((k - k0) / (k1 - k0)))
    return stops[-1][1]


EFFECTS = {
    # id: (function, label, emoji, uses_custom_colors)
    "gradient": (fx_gradient, "Gradient Flow", "🌈", True),
    "breathe": (fx_breathe, "Breathe", "🫁", True),
    "rainbow": (fx_rainbow, "Rainbow", "🦄", False),
    "aurora": (fx_aurora, "Aurora", "🌌", True),
    "candle": (fx_candle, "Candle", "🕯️", True),
    "fireplace": (fx_fireplace, "Fireplace", "🔥", False),
    "ocean": (fx_ocean, "Ocean", "🌊", False),
    "lava": (fx_lava, "Lava Lamp", "🫠", True),
    "galaxy": (fx_galaxy, "Galaxy", "✨", True),
    "sunset": (fx_sunset, "Sunset", "🌇", False),
    "storm": (fx_storm, "Thunderstorm", "⛈️", False),
    "heartbeat": (fx_heartbeat, "Heartbeat", "❤️", True),
    "party": (fx_party, "Party", "🎉", False),
    "police": (fx_police, "Police", "🚨", False),
    "strobe": (fx_strobe, "Strobe", "⚡", True),
    "sunrise": (fx_sunrise, "Sunrise", "🌅", False),
}


def effect_list():
    return [{"id": k, "label": v[1], "icon": v[2], "colors": v[3]} for k, v in EFFECTS.items()]


def render(effect_id, t, params, state, brightness=1.0):
    fn = EFFECTS[effect_id][0]
    r, g, b = fn(t, params, state)
    k = max(0.0, min(1.0, brightness))
    return tuple(max(0.0, min(255.0, c * k)) for c in (r, g, b))


def circadian_temp(hour):
    """Colour-temperature percentage (0 warm .. 100 cool) for a time of day."""
    # warm at night, coolest around 13:00
    if hour < 5 or hour >= 22:
        return 0
    if hour < 13:
        return round(100 * smooth((hour - 5) / 8))
    return round(100 * smooth(1 - (hour - 13) / 9))


def circadian_brightness(hour):
    if hour < 5 or hour >= 23:
        return 20
    if hour < 8:
        return round(lerp(30, 100, (hour - 5) / 3))
    if hour < 19:
        return 100
    return round(lerp(100, 35, (hour - 19) / 4))


# Effects with hard cuts are sent with the bulb's "jump" transition;
# everything else uses "fade" so the bulb blends between frames itself.
HARD_EFFECTS = {"police", "strobe", "party", "storm", "heartbeat"}


def scene_units(colors, mode="gradient"):
    """Expand a palette into native scene units (list of (rgb, change_mode))."""
    cols = [hex_to_rgb(c) for c in colors if isinstance(c, str)][:8] or [(255, 0, 128)]
    if mode == "breathe":
        units = []
        for c in cols[:4]:
            units += [(c, "gradient"), (scale(c, 0.06), "gradient")]
        return units
    return [(c, mode if mode in ("jump", "gradient") else "gradient") for c in cols]


def scene_data(colors, mode="gradient", speed=50):
    """Build Tuya v2 (DP 25) scene data, without the leading scene number.

    Each unit: switch-interval, change-time, change-mode (00 static, 01 jump,
    02 gradient), then H(0-360) S(0-1000) V(0-1000), white bright, white temp.
    """
    speed = max(1, min(100, int(speed)))
    t = int(round(lerp(100, 10, (speed - 1) / 99)))  # bigger = slower
    out = ""
    for rgb, m in scene_units(colors, mode):
        h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
        out += "%02x%02x%02x" % (t, t, 1 if m == "jump" else 2)
        out += "%04x%04x%04x" % (round(h * 360) % 360, round(s * 1000), max(10, round(v * 1000)))
        out += "00000000"
    return out


def scene_preview(t, colors, mode="gradient", speed=50):
    """Approximate what the bulb's native scene looks like (for the UI)."""
    units = scene_units(colors, mode)
    step = lerp(4.0, 0.5, (max(1, min(100, speed)) - 1) / 99)
    pos = t / step
    i = int(pos) % len(units)
    c0, m = units[i]
    if m == "jump" or len(units) == 1:
        return c0
    return mix(c0, units[(i + 1) % len(units)][0], smooth(pos - int(pos)))


# ---- RGBIC segments (DP 61 paint_colour_data, confirmed on a 20-segment strip)
SEGMENTS = 20


def paint_data(rgb, segments=None, total=SEGMENTS):
    """Base64 DP 61 frame painting `segments` (1-based) one colour; None = whole strip.

    Layout: version 00, mode 01 colour, effect 00, segment total, action
    (00 bucket / 01 pencil), H S V (2 bytes each, S/V 0-1000), then for
    pencil 0x80|count + the segment numbers.
    """
    import base64
    h, s, v = colorsys.rgb_to_hsv(*(max(0, min(255, c)) / 255 for c in rgb))
    hsv_b = (round(h * 360) % 360).to_bytes(2, "big") + round(s * 1000).to_bytes(2, "big") \
        + max(10, round(v * 1000)).to_bytes(2, "big")
    if segments is None:
        raw = bytes([0, 1, 0, total, 0]) + hsv_b
    else:
        segs = sorted(set(segments))
        raw = bytes([0, 1, 0, total, 1]) + hsv_b + bytes([0x80 | len(segs)] + segs)
    return base64.b64encode(raw).decode()


def group_segments(colours):
    """[rgb per segment] -> {hex: [1-based segment numbers]}, coarsened so
    tiny shifts don't cost a (slow) write. ponytail: 5-bit quantise, tune if banding shows."""
    groups = {}
    for i, c in enumerate(colours, 1):
        q = rgb_to_hex(tuple(min(255, (int(x) >> 3 << 3) + 4) if x > 6 else 0 for x in c))
        groups.setdefault(q, []).append(i)
    return groups
