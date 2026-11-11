"""Run the OpenVR client outside the Framey loader process."""

import asyncio
import base64
from functools import lru_cache
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys
import time


WORKER = Path(__file__).resolve().with_name("overlay.py")
preferences_spec = spec_from_file_location("frame_charge_preferences", WORKER.with_name("preferences.py"))
preferences = module_from_spec(preferences_spec)
preferences_spec.loader.exec_module(preferences)
charging_spec = spec_from_file_location("frame_charge_readings", WORKER.with_name("charging.py"))
charging = module_from_spec(charging_spec)
charging_spec.loader.exec_module(charging)
bluetooth_spec = spec_from_file_location("frame_charge_bluetooth", WORKER.with_name("bluetooth.py"))
bluetooth = module_from_spec(bluetooth_spec)
bluetooth_spec.loader.exec_module(bluetooth)
history_spec = spec_from_file_location("frame_charge_history", WORKER.with_name("history.py"))
history = module_from_spec(history_spec)
history_spec.loader.exec_module(history)
PROVIDER_DIR = preferences.PATH.parent / "frame-charge-protocol-providers"
PLUGINS_DIR = WORKER.parent.parent
FRAMEY_SETTINGS = preferences.PATH.with_name("settings.json")
PROVIDER_PREFIX = "fcp-provider-"
headphones_lock = asyncio.Lock()
logo = "data:image/svg+xml;base64," + base64.b64encode(WORKER.with_name("logo.svg").read_bytes()).decode("ascii")
supervisor = None
case_monitor = None
case_alert_until = 0.0
last_headphone_read = float("-inf")
low_cases = set()


def observe_case_levels(devices):
    global case_alert_until
    for device in devices:
        name, level = device.get("name"), device.get("case")
        if (not name or not device.get("connected") or "case" in (device.get("stale") or ())
                or type(level) is not int or not 0 <= level <= 100):
            continue
        if level >= 20:
            low_cases.discard(name)
        elif name not in low_cases:
            low_cases.add(name)
            case_alert_until = time.monotonic() + 30


async def refresh_headphones(background=False):
    global last_headphone_read
    async with headphones_lock:
        if background and time.monotonic() - last_headphone_read < 20:
            return
        devices = await asyncio.to_thread(read_headphones)
        last_headphone_read = time.monotonic()
        if preferences.load()["case_low_popup"]:
            observe_case_levels(devices)
        return devices


async def watch_case():
    while still_loaded():
        try:
            if preferences.load()["case_low_popup"]:
                await refresh_headphones(background=True)
        except OSError as error:
            print(f"[frame-charge-protocol] case battery: {error}", file=sys.stderr)
        await asyncio.sleep(2)


def still_loaded():
    module = sys.modules.get(__name__)
    return getattr(module, "still_loaded", None) is still_loaded


async def supervise():
    global case_alert_until
    while still_loaded():
        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable, "-B", str(WORKER), stdin=asyncio.subprocess.PIPE,
            )
            while still_loaded() and process.returncode is None:
                if case_alert_until > time.monotonic():
                    process.stdin.write(b"c")
                    await process.stdin.drain()
                    case_alert_until = 0.0
                await asyncio.sleep(0.5)
            if still_loaded():
                print(f"[frame-charge-protocol] overlay worker exited ({process.returncode})", file=sys.stderr)
        except OSError as error:
            print(f"[frame-charge-protocol] {error}", file=sys.stderr)
        finally:
            if process is not None:
                process.stdin.close()
                try:
                    await asyncio.wait_for(process.wait(), 2)
                except asyncio.TimeoutError:
                    if process.returncode is None:
                        try:
                            process.kill()
                        except ProcessLookupError:
                            pass
                    await process.wait()
        if still_loaded():
            await asyncio.sleep(3)


def provider_paths():
    paths = {
        path.stem: path for path in PROVIDER_DIR.glob("*.py")
        if path.is_file() and path.stem != "bluez" and preferences.valid("headphone_provider", path.stem)
    }
    try:
        settings = json.loads(FRAMEY_SETTINGS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        settings = {}
    disabled = settings.get("disabled") if isinstance(settings, dict) else None
    disabled = disabled if isinstance(disabled, list) else []
    for folder in PLUGINS_DIR.glob(f"{PROVIDER_PREFIX}*"):
        provider = folder.name.removeprefix(PROVIDER_PREFIX)
        if provider == "bluez" or not preferences.valid("headphone_provider", provider):
            continue
        path = folder / f"{provider}.py"
        if path.is_file() and (folder / "plugin.json").is_file():
            # The Framey installation controls this ID while installed.
            paths.pop(provider, None)
            if folder.name not in disabled:
                paths[provider] = path
    return paths


def provider_ids():
    return ["bluez", *sorted(provider_paths())]


@lru_cache(maxsize=8)
def load_provider(path):
    spec = spec_from_file_location(f"frame_charge_provider_{path.stem}", path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.read


def read_headphones():
    selected = preferences.load()["headphone_provider"]
    if selected != "bluez":
        path = provider_paths().get(selected)
        if path is not None:
            try:
                device = load_provider(path)()
                if isinstance(device, dict) and any(
                    type(device.get(part)) is int and 0 <= device[part] <= 100
                    for part in ("percent", "left", "right", "case")
                ):
                    return [device]
            except Exception as error:
                print(f"[frame-charge-protocol] headphone provider {selected}: {error}", file=sys.stderr)
    return bluetooth.audio_batteries(bluetooth.read_objects())


async def call(method, arg):
    global supervisor, case_monitor, case_alert_until
    if method == "start":
        if supervisor is None or supervisor.done():
            supervisor = asyncio.create_task(supervise())
        if case_monitor is None or case_monitor.done():
            case_monitor = asyncio.create_task(watch_case())
        return {"ok": True, "settings": preferences.load(), "locales": preferences.LOCALES, "logo": logo,
                "headphone_providers": provider_ids(), "history_limits": preferences.HISTORY_LIMITS}
    if method == "save" and isinstance(arg, dict):
        key = arg.get("key")
        settings = preferences.save(key, arg.get("value"))
        if key == "case_low_popup" and not settings[key]:
            low_cases.clear()
            case_alert_until = 0.0
        if key == "history_limit":
            await asyncio.to_thread(history.prune, settings["history_limit"])
        return {"settings": settings}
    if method == "history":
        return {"sessions": await asyncio.to_thread(history.sessions, preferences.load()["history_limit"])}
    if method == "clear_history":
        await asyncio.to_thread(history.clear)
        return {"sessions": []}
    if method == "details":
        return charging.read_details()
    if method == "headphones":
        return {"devices": await refresh_headphones()}
    return {"error": "Unknown method"}
