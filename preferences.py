"""Persistent settings shared by the Framey panel and the overlay worker."""

from pathlib import Path
import json
import os
import re


PATH = Path.home() / ".config" / "framey" / "frame-charge-protocol.json"
LOCALES = json.loads(Path(__file__).with_name("locales.json").read_text(encoding="utf-8"))
POSITIONS = ("top-left", "top", "top-right", "left", "center", "right", "bottom-left", "bottom", "bottom-right")
HISTORY_LIMITS = (10, 25, 50, 100)
DEFAULTS = {
    "hide_slow_popup": True, "mute_slow_sound": True, "show": True, "seconds": 5,
    "fade": True, "full_name": True, "show_watts": True, "stop_popup": True, "stop_sound": True,
    "position": "top", "language": "auto", "steam_locale": "zh-Hans", "headphone_provider": "bluez",
    "record_history": False, "history_limit": 25, "case_low_popup": True,
}


def valid(key, value):
    if key == "seconds":
        return type(value) is int and value in (3, 5, 8)
    if key == "history_limit":
        return type(value) is int and value in HISTORY_LIMITS
    if key == "position":
        return value in POSITIONS
    if key == "language":
        return value == "auto" or (isinstance(value, str) and value in LOCALES)
    if key == "steam_locale":
        return isinstance(value, str) and value in LOCALES
    if key == "headphone_provider":
        return isinstance(value, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]{0,31}", value) is not None
    return key in DEFAULTS and type(value) is bool


def load(path=PATH):
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        stored = {}
    if not isinstance(stored, dict):
        return DEFAULTS.copy()
    if type(stored.get("suppress")) is bool:
        stored.setdefault("hide_slow_popup", stored["suppress"])
        stored.setdefault("mute_slow_sound", stored["suppress"])
    return {**DEFAULTS, **{key: value for key, value in stored.items() if valid(key, value)}}


def language(settings):
    return settings["steam_locale"] if settings["language"] == "auto" else settings["language"]


def save(key, value, path=PATH):
    if not valid(key, value):
        raise ValueError("Invalid setting")
    settings = load(path)
    settings[key] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(".tmp")
    pending.write_text(json.dumps(settings) + "\n", encoding="utf-8")
    os.replace(pending, path)
    return settings
