"""Desk Sync: drive the strip from what the computer shows and plays.

Sources
  screen  - the screen's dominant colour (ambient / bias lighting)
  music   - the computer's own sound output (not the mic): beats, bass, pitch
  both    - screen colours that pulse with the music

Optional extras (only on the computer):  pip install -r requirements-desk.txt
  mss        screen capture (Windows / macOS / Linux)
  soundcard  system-audio loopback (Windows works as-is; macOS needs BlackHole)
  numpy
"""
import colorsys
import math
import threading
import time

try:
    import numpy as np
except ImportError:  # the iPhone build doesn't need any of this
    np = None


def missing_deps(need_screen, need_audio):
    miss = []
    if np is None:
        miss.append("numpy")
    if need_screen:
        try:
            import mss  # noqa: F401
        except ImportError:
            miss.append("mss")
    if need_audio:
        try:
            import soundcard  # noqa: F401
        except Exception:  # soundcard raises odd errors when no audio system exists
            miss.append("soundcard")
    return miss


# ------------------------------------------------------------ pure analysis

def screen_colour(img):
    """img: HxWx3 uint8 RGB. Returns (rgb 0..255 tuple, brightness 0..1).

    Vivid pixels count far more than grey ones, so a mostly-dark game with a
    neon sign lights the desk in the sign's colour instead of muddy grey.
    """
    f = img.astype(np.float32) / 255.0
    mx = f.max(axis=2)
    mn = f.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    w = (sat ** 2) * mx + 0.02
    total = w.sum()
    col = (f * w[..., None]).reshape(-1, 3).sum(axis=0) / total
    lum = float((0.2126 * f[..., 0] + 0.7152 * f[..., 1] + 0.0722 * f[..., 2]).mean())
    h, s, v = colorsys.rgb_to_hsv(*col)
    s = min(1.0, s * 1.25 + 0.05)  # LEDs look washed out without a little boost
    r, g, b = colorsys.hsv_to_rgb(h, s, 1.0)
    return (r * 255, g * 255, b * 255), lum


def screen_zones(img, n=3):
    """Dominant colour of n vertical slices, left to right (for segment strips)."""
    w = img.shape[1]
    return [screen_colour(img[:, i * w // n:(i + 1) * w // n])[0] for i in range(n)]


class AudioAnalyser:
    """Turns blocks of audio samples into level / bass / beat / pitch."""

    def __init__(self, rate=44100):
        self.rate = rate
        self.bass_avg = 0.05
        self.level_avg = 0.05
        self.peak = 0.1
        self.level = 0.0
        self.bass = 0.0
        self.centroid = 0.3
        self.beat = False
        self.last_beat = 0.0

    def feed(self, block, now=None):
        now = time.time() if now is None else now
        mono = block.mean(axis=1) if block.ndim == 2 else block
        if len(mono) < 64:
            return
        spec = np.abs(np.fft.rfft(mono * np.hanning(len(mono))))
        freqs = np.fft.rfftfreq(len(mono), 1 / self.rate)
        rms = float(np.sqrt(np.mean(mono ** 2)))
        bass = float(spec[(freqs > 30) & (freqs < 160)].mean()) if len(spec) else 0.0
        # auto-gain: adapt to whatever volume is playing
        self.peak = max(rms, self.peak * 0.995, 1e-4)
        level = min(1.0, rms / self.peak)
        band = spec[(freqs > 60) & (freqs < 8000)]
        bf = freqs[(freqs > 60) & (freqs < 8000)]
        if band.sum() > 0:
            c = float((band * bf).sum() / band.sum())
            self.centroid = 0.85 * self.centroid + 0.15 * min(1.0, math.log2(max(c, 60) / 60) / 7)
        self.beat = (bass > self.bass_avg * 1.45 and level > 0.25 and now - self.last_beat > 0.18)
        if self.beat:
            self.last_beat = now
        self.bass_avg = 0.93 * self.bass_avg + 0.07 * bass
        self.level = max(level, self.level * 0.82)  # fast attack, smooth release
        self.bass = bass


# ------------------------------------------------------------ sources

class ScreenSource(threading.Thread):
    def __init__(self, fps=20):
        super().__init__(daemon=True)
        self.fps = fps
        self.rgb = (255, 255, 255)
        self.lum = 0.5
        self.zones = []
        self.error = None
        self.running = True

    def run(self):
        try:
            import mss
            with mss.mss() as sct:
                mon = sct.monitors[1]  # primary screen
                while self.running:
                    shot = sct.grab(mon)
                    a = np.frombuffer(shot.raw, dtype=np.uint8).reshape(shot.height, shot.width, 4)
                    step = max(1, shot.width // 96)
                    img = a[::step, ::step, 2::-1]  # BGRA -> RGB, downsampled
                    self.rgb, self.lum = screen_colour(img)
                    self.zones = screen_zones(img)
                    time.sleep(1 / self.fps)
        except Exception as e:  # noqa: BLE001
            self.error = f"screen capture failed: {e}"


class AudioSource(threading.Thread):
    def __init__(self, use_mic=False):
        super().__init__(daemon=True)
        self.an = AudioAnalyser()
        self.error = None
        self.device = None
        self.use_mic = use_mic
        self.running = True

    def run(self):
        try:
            import soundcard as sc
            if self.use_mic:
                mic = sc.default_microphone()
            else:
                spk = sc.default_speaker()
                mic = sc.get_microphone(id=str(spk.name), include_loopback=True)
            self.device = mic.name
            with mic.recorder(samplerate=self.an.rate, blocksize=1024) as rec:
                while self.running:
                    self.an.feed(rec.record(numframes=1024))
        except Exception as e:  # noqa: BLE001
            self.error = (f"sound capture failed: {e}. On a Mac install BlackHole and set "
                          "it as output (see README), or use the 'mic' option.")


# ------------------------------------------------------------ desk sync

class DeskSync(threading.Thread):
    """Mixes the sources and streams frames to the strip."""

    MODES = ("screen", "music", "both")

    def __init__(self, engine, mode="screen", fps=15, intensity=1.0, use_mic=False):
        super().__init__(daemon=True)
        self.engine = engine
        self.mode = mode
        self.fps = fps
        self.intensity = intensity
        self.running = True
        self.screen = ScreenSource(fps=max(fps, 15)) if mode in ("screen", "both") else None
        self.audio = AudioSource(use_mic) if mode in ("music", "both") else None
        self.hue = 0.0
        self.out = (0.0, 0.0, 0.0)

    def error(self):
        for s in (self.screen, self.audio):
            if s is not None and s.error:
                return s.error
        return None

    def info(self):
        return {"mode": self.mode, "intensity": self.intensity, "error": self.error(),
                "audio_device": self.audio.device if self.audio else None}

    def stop(self):
        self.running = False
        for s in (self.screen, self.audio):
            if s is not None:
                s.running = False

    def frame(self):
        """Return (rgb, smooth) for this instant."""
        k = self.intensity
        if self.mode == "screen":
            rgb, lum = self.screen.rgb, self.screen.lum
            level = 0.25 + 0.75 * min(1.0, lum * 1.8)  # dark scenes dim the desk
            return tuple(c * level for c in rgb), True
        an = self.audio.an
        if self.mode == "music":
            # hue follows the music's brightness of tone; beats kick it round the wheel
            self.hue = (self.hue + 0.002 + (0.18 if an.beat else 0)) % 1
            hue = (self.hue + an.centroid * 0.35) % 1
            r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 0.06 + 0.94 * min(1.0, an.level * k))
            return (r * 255, g * 255, b * 255), not an.beat
        # both: screen colour, brightness rides the music, flash on the beat
        rgb = self.screen.rgb
        level = 0.18 + 0.82 * min(1.0, an.level * k)
        if an.beat:
            level = 1.0
        return tuple(c * level for c in rgb), not an.beat

    def run(self):
        for s in (self.screen, self.audio):
            if s is not None:
                s.start()
        time.sleep(0.3)
        while self.running:
            if self.error():
                time.sleep(0.5)
                continue
            rgb, smooth = self.frame()
            # light smoothing on top of the bulb's own fade keeps colour shifts silky
            a = 1.0 if not smooth else 0.55
            self.out = tuple(o + (n - o) * a for o, n in zip(self.out, rgb))
            self.engine.live(self.out, smooth)
            time.sleep(1 / self.fps)
