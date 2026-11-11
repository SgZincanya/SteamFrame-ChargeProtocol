"""Build the Framey install ZIP from the project sources."""

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "backend.py", "bluetooth.py", "charging.py", "history.py", "overlay.py", "preferences.py", "texture.py",
    "main.js", "plugin.json", "locales.json", "logo.svg", "charging-stopped.wav", "LICENSE", "README.txt",
    "stopped-en.png", "stopped-ja.png", "stopped-ko.png", "stopped-zh-Hans.png", "stopped-zh-Hant.png",
    "usb-pd.png", "usb-pd-pps.png", "usb-power-delivery.png", "usb-power-delivery-pps.png",
)


def main():
    version = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))["version"]
    target = ROOT / "dist" / f"SteamFrame-ChargeProtocol-v{version}.zip"
    target.parent.mkdir(exist_ok=True)
    with ZipFile(target, "w", ZIP_DEFLATED, compresslevel=9) as archive:
        for name in FILES:
            archive.write(ROOT / name, name)
    print(target.relative_to(ROOT))


if __name__ == "__main__":
    main()
