"""Run the OpenVR client outside the Framey loader process."""

import asyncio
import base64
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


WORKER = Path(__file__).resolve().with_name("overlay.py")
preferences_spec = spec_from_file_location("frame_charge_preferences", WORKER.with_name("preferences.py"))
preferences = module_from_spec(preferences_spec)
preferences_spec.loader.exec_module(preferences)
charging_spec = spec_from_file_location("frame_charge_readings", WORKER.with_name("charging.py"))
charging = module_from_spec(charging_spec)
charging_spec.loader.exec_module(charging)
headphones_spec = spec_from_file_location("frame_charge_headphones", WORKER.with_name("headphones.py"))
headphones = module_from_spec(headphones_spec)
headphones_spec.loader.exec_module(headphones)
bluetooth_spec = spec_from_file_location("frame_charge_bluetooth", WORKER.with_name("bluetooth.py"))
bluetooth = module_from_spec(bluetooth_spec)
bluetooth_spec.loader.exec_module(bluetooth)
HEADPHONE_PROVIDERS = {"air4-se": headphones.Air4Reader()}
headphones_lock = asyncio.Lock()
logo = "data:image/svg+xml;base64," + base64.b64encode(WORKER.with_name("logo.svg").read_bytes()).decode("ascii")
supervisor = None


def still_loaded():
    module = sys.modules.get(__name__)
    return getattr(module, "still_loaded", None) is still_loaded


async def supervise():
    while still_loaded():
        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable, "-B", str(WORKER), stdin=asyncio.subprocess.PIPE,
            )
            while still_loaded() and process.returncode is None:
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


def read_headphones():
    provider = HEADPHONE_PROVIDERS.get(preferences.load()["headphone_provider"])
    if provider is not None:
        device = provider.read()
        if device is not None:
            return [device]
    return bluetooth.audio_batteries(bluetooth.read_objects())


async def call(method, arg):
    global supervisor
    if method == "start":
        if supervisor is None or supervisor.done():
            supervisor = asyncio.create_task(supervise())
        return {"ok": True, "settings": preferences.load(), "locales": preferences.LOCALES, "logo": logo,
                "headphone_providers": ["bluez", *HEADPHONE_PROVIDERS]}
    if method == "save" and isinstance(arg, dict):
        return {"settings": preferences.save(arg.get("key"), arg.get("value"))}
    if method == "details":
        return charging.read_details()
    if method == "headphones":
        async with headphones_lock:
            return {"devices": await asyncio.to_thread(read_headphones)}
    return {"error": "Unknown method"}
