"""Build the Framey install ZIP or the standalone Air 4 SE provider ZIP."""

from argparse import ArgumentParser
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "backend.py", "bluetooth.py", "charging.py", "history.py", "overlay.py", "preferences.py", "texture.py",
    "main.js", "plugin.json", "locales.json", "logo.svg", "charging-stopped.wav", "LICENSE", "README.txt",
    "stopped-en.png", "stopped-ja.png", "stopped-ko.png", "stopped-zh-Hans.png", "stopped-zh-Hant.png",
    "case-low-en.png", "case-low-ja.png", "case-low-ko.png", "case-low-zh-Hans.png", "case-low-zh-Hant.png",
    "usb-pd.png", "usb-pd-pps.png", "usb-power-delivery.png", "usb-power-delivery-pps.png",
)
AIR4_SE_FILES = (
    ("providers/air4-se/plugin.json", "plugin.json"),
    ("providers/air4-se/air4-se.py", "air4-se.py"),
    ("providers/air4-se/README.md", "README.md"),
    ("LICENSE", "LICENSE"),
)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--air4-se", action="store_true", help="Build only the optional Air 4 SE provider.")
    args = parser.parse_args()
    if args.air4_se:
        version = json.loads((ROOT / "providers/air4-se/plugin.json").read_text(encoding="utf-8"))["version"]
        name = f"Air4-SE-Provider-v{version}.zip"
        files = AIR4_SE_FILES
    else:
        version = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))["version"]
        name = f"SteamFrame-ChargeProtocol-v{version}.zip"
        files = ((filename, filename) for filename in FILES)
    target = ROOT / "dist" / name
    target.parent.mkdir(exist_ok=True)
    with ZipFile(target, "w", ZIP_DEFLATED, compresslevel=9) as archive:
        for source, filename in files:
            archive.write(ROOT / source, filename)
    print(target.relative_to(ROOT))


if __name__ == "__main__":
    main()
