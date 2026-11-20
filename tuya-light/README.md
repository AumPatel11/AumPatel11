# Lumora: your own app for Tuya RGBCW smart bulbs

Lumora controls a Tuya WiFi RGB+CW bulb (it also works for Smart Life, Tuya, Gosund, Teckin and other "Tuya-inside" bulbs) **directly over your home WiFi**. It doesn't talk to the cloud while it runs and has no lag. It runs on a spare iPhone or a computer, and you control it from any phone on the same WiFi or hotspot.

## What it can do

| | |
|---|---|
| 🎨 **Colour** | Colour wheel, hex input, swatches, plus **colour harmonies** (complementary, triadic and more) that you tap to play as a moving gradient |
| 💡 **White** | Warm ↔ cool slider and Candle, Relax, Read and Focus presets, plus a **Circadian mode** that follows the sun through the day |
| ✨ **Effects** | 16 effects rendered live on your computer: Gradient Flow, Aurora, Candle, Fireplace, Ocean, Lava Lamp, Galaxy, Sunset, Thunderstorm, Heartbeat, Party, Police, Strobe and more. You can set the speed and **build your own palette** (or start from Synthwave, Forest, Cyberpunk and others) |
| 🎵 **Music sync** | Uses the microphone to react to music, in Spectrum, Pulse or Beat-drop styles, with a live visualiser |
| 🖼 **Photo mood** | Pick a photo and Lumora pulls out its palette and plays it on the bulb. Tap the photo to grab an exact colour |
| ⏰ **Timers** | A sleep fade that dims slowly and then switches off, and a **sunrise wake-up alarm** (deep red → warm white) |
| ⭐ **Presets** | Save any look, including effects with your palette, and get it back with one tap |
| 💎 **Save into bulb** | Stores your palette as a scene **inside the bulb**, so it animates perfectly smoothly on its own, even with every phone asleep |
| 📳 **Shake** | Shake your phone for a surprise colour |
| 📱 **Demo mode** | Try everything with a virtual bulb before you connect the real one |

## 📱 Just one iPhone (it's also the hotspot)

iOS pauses apps you switch away from, so on a single iPhone Lumora runs **inside a-Shell** as a tap-and-type menu. You don't need a browser.

1. Install **a-Shell** (the full one, not *a-Shell mini*) from the App Store.
2. Turn on **Personal Hotspot → Maximize Compatibility**, and move the bulb onto the hotspot WiFi in Smart Life.
3. In a-Shell, paste this one line to install:
   ```bash
   python3 -c "import urllib.request as u;exec(u.urlopen('https://raw.githubusercontent.com/AumPatel11/AumPatel11/claude/compassionate-archimedes-ceyhlg/tuya-light/ios_install.py').read())"
   ```
4. Start it:
   ```bash
   cd ~/Documents/lumora
   ```
   ```bash
   python3 lumo.py
   ```
5. Choose **s** for Setup. Paste your Tuya Access ID and Secret (see "Get your key" below), and Lumora finds the bulb on your hotspot by itself.

| Menu | What it does |
|---|---|
| 2 Colour | 16 named colours or any `#hex` |
| 3 White | candle / warm / neutral / day / cool |
| 4 💎 Bulb scene | Saves a palette **into the bulb** (synthwave, sunset, aurora, diwali, and more, or your own). It keeps animating smoothly after you close a-Shell |
| 5 Live effect | Aurora, Candle, Fireplace, Storm, Heartbeat… while a-Shell is open |
| 7 Sleep fade | Dims slowly, then switches off |

Quick commands also work: `python3 lumo.py color purple`, `python3 lumo.py scene diwali breathe 60`, `python3 lumo.py white warm 40`, `python3 lumo.py off`.

Music sync needs the browser version, which needs a second phone (below).

## 📱📱 Two iPhones (hub + remote, with music sync)

You need **two iPhones**. The spare one becomes the **light hub**, and your main phone is the **remote** (with mic music sync).

```
 Main iPhone (hotspot + remote, Safari)  ──WiFi hotspot──  Bulb
                     │                                       │
                     └──────────── Spare iPhone (hub) ───────┘
                                   runs Lumora in a-Shell
```

**On both phones:** the bulb and the spare iPhone must join the main iPhone's hotspot. In the Smart Life app, set the bulb's WiFi to the hotspot (re-pair it if needed). On the main iPhone, turn on **Settings → Personal Hotspot → Maximize Compatibility**, because most bulbs only speak 2.4 GHz.

**On the spare iPhone (the hub):**

1. Install **a-Shell** (free, App Store).
2. In a-Shell, type these two lines (they download and install Lumora):
   ```bash
   curl -L https://raw.githubusercontent.com/AumPatel11/AumPatel11/claude/compassionate-archimedes-ceyhlg/tuya-light/ios_install.py -o install.py
   ```
   ```bash
   python3 install.py
   ```
3. Start it:
   ```bash
   cd ~/Documents/lumora
   ```
   ```bash
   python3 server.py
   ```
   If iOS asks to allow a-Shell to find devices on your **local network**, tap **Allow**.
4. **Leave a-Shell open on screen.** iPhones pause apps you switch away from. Plug the phone in and set *Settings → Display → Auto-Lock → Never* while it's acting as the hub.

**On the main iPhone (the remote):**

1. In Safari, open the `https://172.20.10.x:8787` address that a-Shell printed.
2. Safari says *"This Connection Is Not Private"*. That's expected, because Lumora made its own certificate. Tap **Show Details → visit this website → Visit Website**.
3. Tap **Share → Add to Home Screen** so Lumora opens like a normal app.
4. In **Setup**, use *Step 1* to fetch your bulb's key from Tuya (see "Get your key" below), tap your bulb, then tap **Connect**.

The `https` matters because iPhone Safari only allows the **microphone** (music sync) and **shake** on secure pages.

**Tips for seamless light:**
- **💎 Save into the bulb** (Effects tab) is the smoothest option. The bulb animates the scene itself, so the hub can even sleep.
- Live effects and music sync use the bulb's fade transition, so it blends between frames. Turn off *Silky mode* on the Music tab for snappier beats.
- To update Lumora later, run `python3 install.py` again. Your bulb settings and presets are kept.

## 💻 Computer setup (Windows / Mac / Linux / Raspberry Pi)

Lumora must run on a computer **at home, on the same WiFi as the bulb** (Windows, Mac, Linux or a Raspberry Pi). You need Python 3.9 or newer from python.org; on Windows, tick **"Add Python to PATH"** while installing.

**Easiest:** download this folder, then double-click **`start-windows.bat`** (Windows) or run **`./start-mac-linux.sh`** (Mac/Linux). Your browser opens Lumora automatically. Keep the black window open while you use it.

Or by hand:

```bash
cd tuya-light
```

```bash
pip install -r requirements.txt
```

```bash
python server.py
```

Open **http://localhost:8787**. The terminal also prints a link for your phone.

### 🖥 Desk Sync (screen + system audio)

On the computer, also run `pip install -r requirements-desk.txt`. The **Desk** tab then offers **Screen** (ambient light from your screen), **Music** (follows whatever the computer plays, not the mic), **Zones** (left/middle/right of the screen along an RGBIC strip), and **Both** (screen colours pulsing to the beat). Touching any other control stops it. Windows works as-is.

RGBIC strips: segment colours go through DP 61 (20 segments, numbered 1-20). These strips drop writes sent faster than ~2/s, so Zones refreshes every 1.5 s. If the zones come out mirrored, set `"segments_reversed": true` (or false) in `config.json`. Segments only worked with the strip length left at the app's own setting. On a Mac, install [BlackHole](https://github.com/ExistentialAudio/BlackHole) and route output through a Multi-Output Device that includes it.

## Get your key: the bulb's Device ID and Local Key (one time, ~10 min)

Tuya bulbs encrypt local traffic with a per-device **Local Key**, so you need to get it once.

**Easy way (works on iPhone):**
1. On iot.tuya.com, sign up for free and go to **Cloud → Development → Create Cloud Project**. Pick **Smart Home** and your data centre (India users: *India*).
2. Open the project, go to **Devices → Link App Account → Add App Account**, and scan the QR code with **Smart Life → Me → scan icon** (top right).
3. Copy the project's **Access ID** and **Access Secret** from the *Overview* tab.
4. In Lumora's **Setup → Step 1**, pick the same data centre, paste both values and tap **Get my bulbs**. Tap your bulb, then tap **Connect**.

**Terminal way (computer):**

1. Set the bulb up in the **Smart Life** or **Tuya Smart** app as usual. Make sure it works over WiFi, not only Bluetooth.
2. Create a free account at **iot.tuya.com**. Then go to *Cloud → Create Cloud Project* and pick your region's data centre. Under *Devices → Link App Account*, scan the QR code with the Smart Life app.
3. Copy the project's **Access ID** and **Access Secret**, then run:
   ```bash
   python -m tinytuya wizard
   ```
   Answer the prompts. This creates `devices.json` with your bulb's `id` and `key`.
4. Put `devices.json` inside the `tuya-light` folder. In Lumora's **Setup** tab, tap your bulb, then tap **Connect**.

Tips:
- Leave IP blank to auto-find, or press **Scan WiFi**.
- If it won't connect, try protocol version **3.4** or **3.5** (newer bulbs). On iPhone, versions 3.1–3.4 work. Version 3.5 needs a crypto library that iPhones can't install.
- Close the Smart Life app on your phone. Some bulbs only accept one local connection at a time.
- Re-pairing the bulb in Smart Life changes its Local Key, so you'll need to run the wizard again.

## About Bluetooth

Your bulb has both WiFi and Bluetooth. Tuya's Bluetooth mode uses a different encrypted protocol tied to its cloud account, so Lumora uses the **WiFi** connection. That one is faster, works from any device in the house, and makes effects and music sync smooth.

## Notes

- Effects and music sync use the bulb's real-time "music" channel, sending about 12 frames per second (you can change this in Setup). If your bulb flickers or lags, lower the FPS.
- The microphone needs https on phones. On iPhone Lumora uses https automatically; on a computer, start it with `python server.py --https`.
- Keep `server.py` running for effects, timers and alarms. A Raspberry Pi or an always-on PC is a good home for it.
- `config.json`, `devices.json` and `data.json` hold your key and settings, and they are git-ignored.

## Tests

```bash
python -m unittest test_lumora -v
```
