"""Install / update Lumora on an iPhone inside the free a-Shell app.

In a-Shell run:
    curl -L https://raw.githubusercontent.com/AumPatel11/AumPatel11/claude/compassionate-archimedes-ceyhlg/tuya-light/ios_install.py -o install.py
    python3 install.py

iPhone apps can't run pip's build steps, so this unpacks pure-Python wheels
into lumora/vendor instead. Your settings, keys and presets are kept.
"""
import io
import json
import os
import shutil
import sys
import tarfile
import urllib.request
import zipfile

REPO = "AumPatel11/AumPatel11"
BRANCH = "claude/compassionate-archimedes-ceyhlg"
SUBDIR = "tuya-light/"
KEEP = {"config.json", "data.json", "devices.json", "cert.pem", "key.pem", "cert.ip", "tinytuya-cloud.json"}

# pypi name -> top-level import packages. All pure Python.
LIBS = {
    "tinytuya": ["tinytuya"],
    "pyaes": ["pyaes"],
    "requests": ["requests"],
    "urllib3": ["urllib3"],
    "idna": ["idna"],
    "charset-normalizer": ["charset_normalizer"],
    "certifi": ["certifi"],
    "colorama": ["colorama"],
}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "lumora-installer"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def install_app(target):
    print("Downloading Lumora...")
    data = get(f"https://codeload.github.com/{REPO}/zip/refs/heads/{BRANCH}")
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            parts = name.split("/", 1)
            if len(parts) < 2 or not parts[1].startswith(SUBDIR) or name.endswith("/"):
                continue
            rel = parts[1][len(SUBDIR):]
            if not rel or rel in KEEP or ".." in rel.split("/"):
                continue
            dest = os.path.join(target, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as f:
                f.write(z.read(name))


def pick(files):
    for f in files:
        if f["packagetype"] == "bdist_wheel" and f["filename"].endswith("-none-any.whl"):
            return f
    for f in files:
        if f["packagetype"] == "sdist" and f["filename"].endswith(".tar.gz"):
            return f
    return None


def install_lib(pypi_name, packages, vendor):
    meta = json.loads(get(f"https://pypi.org/pypi/{pypi_name}/json"))
    f = pick(meta["urls"])
    if not f:
        raise RuntimeError(f"no pure-Python download for {pypi_name}")
    print(f"  {pypi_name} {meta['info']['version']}")
    blob = get(f["url"])
    for p in packages:
        shutil.rmtree(os.path.join(vendor, p), ignore_errors=True)
    if f["filename"].endswith(".whl"):
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            for name in z.namelist():
                if name.split("/")[0] in packages and not name.endswith("/"):
                    dest = os.path.join(vendor, name)
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with open(dest, "wb") as out:
                        out.write(z.read(name))
    else:  # sdist: <name>-<ver>/<package>/...
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as t:
            for m in t.getmembers():
                parts = m.name.split("/")
                if len(parts) > 2 and parts[1] in packages and m.isfile() and ".." not in parts:
                    dest = os.path.join(vendor, *parts[1:])
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with open(dest, "wb") as out:
                        out.write(t.extractfile(m).read())


def main():
    home = os.path.expanduser("~")
    docs = os.path.join(home, "Documents")
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(docs if os.path.isdir(docs) else home, "lumora")
    os.makedirs(target, exist_ok=True)
    install_app(target)
    print("Downloading libraries...")
    vendor = os.path.join(target, "vendor")
    os.makedirs(vendor, exist_ok=True)
    for name, pkgs in LIBS.items():
        install_lib(name, pkgs, vendor)

    cfg_path = os.path.join(target, "config.json")
    cfg = {}
    if os.path.exists(cfg_path):
        with open(cfg_path) as f:
            cfg = json.load(f)
    cfg.setdefault("https", True)  # Safari needs https for the microphone
    with open(cfg_path, "w") as f:
        json.dump(cfg, f, indent=2)

    print("\nDone! Start Lumora with:\n")
    print(f"  cd {target}")
    print("  python3 server.py\n")


if __name__ == "__main__":
    main()
