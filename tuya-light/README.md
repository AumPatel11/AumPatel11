# Lumora: your own app for Tuya RGBCW smart bulbs

Lumora controls a Tuya WiFi RGB+CW bulb (it also works for Smart Life, Tuya, Gosund, Teckin and other "Tuya-inside" bulbs) **directly over your home WiFi**. It doesn't talk to the cloud while it runs and has no lag. It runs on your computer, and you open it on any phone or laptop on the same WiFi.

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
| 📱 **Demo mode** | Try everything with a virtual bulb before you connect the real one |

## 1. Install & run

You need Python 3.9 or newer.

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

## 2. Get your bulb's Device ID and Local Key (one time, ~5 min)

Tuya bulbs encrypt local traffic with a per-device **Local Key**, so you need to get it once:

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
- If it won't connect, try protocol version **3.4** or **3.5** (newer bulbs).
- Close the Smart Life app on your phone. Some bulbs only accept one local connection at a time.
- Re-pairing the bulb in Smart Life changes its Local Key, so you'll need to run the wizard again.

## About Bluetooth

Your bulb has both WiFi and Bluetooth. Tuya's Bluetooth mode uses a different encrypted protocol tied to its cloud account, so Lumora uses the **WiFi** connection. That one is faster, works from any device in the house, and makes effects and music sync smooth.

## Notes

- Effects and music sync use the bulb's real-time "music" channel, sending about 12 frames per second (you can change this in Setup). If your bulb flickers or lags, lower the FPS.
- The microphone works in the browser on the computer running Lumora (`localhost`). Phones only allow mic access over https.
- Keep `server.py` running for effects, timers and alarms. A Raspberry Pi or an always-on PC is a good home for it.
- `config.json`, `devices.json` and `data.json` hold your key and settings, and they are git-ignored.

## Tests

```bash
python -m unittest test_lumora -v
```
