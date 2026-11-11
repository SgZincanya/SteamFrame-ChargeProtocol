"""Read the Frame's negotiated USB input and show a local OpenVR overlay."""

from __future__ import annotations

import ctypes as c
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

from charging import read_charging
from preferences import DEFAULTS, language, load as load_preferences
from texture import contract_label, render_contract_texture


VR_LIBRARY = "/opt/steamvr/bin/linuxarm64/libopenvr_api.so"
TEXTURES = {"USB PD": "usb-pd.png", "USB PD PPS": "usb-pd-pps.png"}
FULL_TEXTURES = {"USB PD": ("usb-power-delivery.png", 0.46), "USB PD PPS": ("usb-power-delivery-pps.png", 0.51)}
STOPPED = "stopped"
FADE_SECONDS = 0.45
FADE_INTERVAL = 1 / 30
SAMPLE_SECONDS = 0.25
PAUSE_SECONDS = 1.5


class StopDetector:
    def __init__(self):
        self.state = None
        self.candidate = None
        self.candidate_since = 0.0
        self.last_pause = None

    def update(self, sample, now):
        if sample.connected is None:
            self.candidate = None
            return None
        if not sample.connected:
            reading = "disconnected"
        elif sample.charging is True:
            reading = "charging"
        elif sample.charging is False:
            reading = "paused"
        else:
            reading = self.state if self.state not in (None, "disconnected") else "connected"

        if reading != self.candidate:
            self.candidate = reading
            self.candidate_since = now
            return None
        stable_for = PAUSE_SECONDS if reading == "paused" and self.state == "charging" else SAMPLE_SECONDS
        if reading == self.state or now - self.candidate_since < stable_for:
            return None

        previous, self.state = self.state, reading
        if reading == "charging" or (reading != "disconnected" and previous in (None, "disconnected")):
            self.last_pause = None
            return "resumed"
        if reading == "paused" and previous == "charging":
            self.last_pause = now
            return STOPPED
        if reading == "disconnected" and previous is not None:
            if self.last_pause is None or now - self.last_pause > 1.0:
                return STOPPED
        return None


def play_stop_sound(retry=False):
    players = ("paplay", "pw-play") if retry else ("pw-play", "paplay")
    player = shutil.which(players[0]) or shutil.which(players[1])
    if not player:
        print("[frame-charge-protocol] stop sound player unavailable", file=sys.stderr, flush=True)
        return
    path = Path(__file__).with_name("charging-stopped.wav")
    options = ["--media-role=Notification"] if Path(player).name == "pw-play" else []
    try:
        return subprocess.Popen([player, *options, str(path)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
    except OSError as error:
        print(f"[frame-charge-protocol] stop sound: {error}", file=sys.stderr, flush=True)


class StopAudio:
    def __init__(self):
        self.process = None
        self.deadline = None
        self.next_attempt = None
        self.attempts = 0

    def request(self, now):
        if self.process is None and self.next_attempt is None:
            self.next_attempt = now
            self.attempts = 0

    def close(self):
        if self.process is not None and self.process.poll() is None:
            self.process.kill()
        self.process = self.deadline = self.next_attempt = None

    def update(self, now, enabled):
        if not enabled:
            self.close()
            return
        if self.process is not None:
            status = self.process.poll()
            if status is None:
                if self.deadline is not None and now >= self.deadline:
                    self.process.kill()
                    self.deadline = None
                return
            self.process = None
            if status == 0:
                print("[frame-charge-protocol] stop sound playback completed", file=sys.stderr, flush=True)
            elif self.attempts < 2:
                self.next_attempt = now + SAMPLE_SECONDS
            else:
                print(f"[frame-charge-protocol] stop sound failed ({status})", file=sys.stderr, flush=True)

        if self.next_attempt is not None and now >= self.next_attempt:
            self.next_attempt = None
            self.attempts += 1
            self.process = play_stop_sound(retry=self.attempts > 1)
            self.deadline = now + 2.5
            if self.process is None and self.attempts < 2:
                self.next_attempt = now + SAMPLE_SECONDS


class ProtocolNotice:
    def __init__(self):
        self.candidate = None
        self.last_shown = None
        self.hide_at = None
        self.fade_seconds = 0
        self.visible = None
        self.stops = StopDetector()
        self.stop_pending = False
        self.sound_pending_since = None
        self.sound = StopAudio()

    def hide(self, view):
        if self.hide_at is not None:
            if view is not None:
                view.hide()
            self.hide_at = None
            self.visible = None

    def present(self, view, notice, settings, clock, watts=None):
        self.hide(view)
        view.show(notice, settings, watts)
        self.visible = notice
        self.hide_at = clock() + settings["seconds"]
        self.fade_seconds = FADE_SECONDS if settings["fade"] else 0

    def update(self, sample, view, clock=time.monotonic, settings=DEFAULTS):
        now = clock()
        event = self.stops.update(sample, now)
        if event == STOPPED:
            self.stop_pending = settings["stop_popup"]
            if settings["stop_sound"]:
                self.sound_pending_since = now
            print(f"[frame-charge-protocol] charge stopped ({self.stops.state})", file=sys.stderr, flush=True)
        elif event == "resumed":
            self.stop_pending = False
            self.sound_pending_since = None
            if self.visible == STOPPED:
                self.hide(view)

        if not settings["stop_popup"]:
            self.stop_pending = False
            if self.visible == STOPPED:
                self.hide(view)
        if self.stop_pending and view is not None and view.is_in_use():
            self.present(view, STOPPED, settings, clock)
            self.stop_pending = False
        if not settings["stop_sound"]:
            self.sound_pending_since = None
        if self.sound_pending_since is not None:
            if not self.stop_pending or (view is None and now - self.sound_pending_since >= 1.5):
                self.sound.request(now)
                self.sound_pending_since = None
        self.sound.update(now, settings["stop_sound"])

        if sample.connected is False:
            if self.visible != STOPPED:
                self.hide(view)
            self.candidate = None
            self.last_shown = None
            return

        previous = self.candidate
        fixed = sample.protocol == "USB PD"
        self.candidate = (sample.protocol, sample.voltage_mv if fixed else None, sample.current_ma if fixed else None)
        if not settings["show"]:
            if self.visible != STOPPED:
                self.hide(view)
            return
        if self.visible == STOPPED or self.stop_pending:
            return
        if not sample.protocol or self.candidate != previous or sample.protocol == self.last_shown:
            return

        if view is not None and view.is_in_use():
            self.present(view, sample.protocol, settings, clock, sample.contract_watts)
            self.last_shown = sample.protocol

    def animate(self, view, now):
        if self.hide_at is None:
            return SAMPLE_SECONDS
        remaining = self.hide_at - now
        if remaining <= 0:
            self.hide(view)
            return SAMPLE_SECONDS
        if self.fade_seconds and remaining <= self.fade_seconds:
            ratio = remaining / self.fade_seconds
            view.set_opacity(ratio * ratio * (3 - 2 * ratio))
            return min(remaining, FADE_INTERVAL)
        return min(SAMPLE_SECONDS, remaining - self.fade_seconds)


class Matrix34(c.Structure):
    _fields_ = [("rows", (c.c_float * 4) * 3)]


def bind(table, index, result, *args):
    function = c.cast(table, c.POINTER(c.c_void_p))[index]
    if not function:
        raise RuntimeError(f"OpenVR interface slot {index} is unavailable")
    return c.CFUNCTYPE(result, *args)(function)


class OpenVROverlay:
    def __init__(self):
        self.lib = c.CDLL(VR_LIBRARY)
        self.lib.VR_InitInternal2.argtypes = (c.POINTER(c.c_int), c.c_int, c.c_char_p)
        self.lib.VR_InitInternal2.restype = c.c_uint32
        self.lib.VR_GetGenericInterface.argtypes = (c.c_char_p, c.POINTER(c.c_int))
        self.lib.VR_GetGenericInterface.restype = c.c_void_p
        self.lib.VR_ShutdownInternal.argtypes = ()
        self.lib.VR_ShutdownInternal.restype = None
        self.handle = c.c_uint64()
        self.textures = None
        error = c.c_int()
        self.lib.VR_InitInternal2(c.byref(error), 2, None)  # VRApplication_Overlay
        if error.value:
            raise RuntimeError(f"VR_InitInternal2: {error.value}")

        try:
            self.configure()
        except BaseException:
            self.close()
            raise

    def interface(self, version):
        error = c.c_int()
        table = self.lib.VR_GetGenericInterface(b"FnTable:" + version, c.byref(error))
        if not table or error.value:
            raise RuntimeError(f"{version.decode()}: {error.value}")
        return table

    def configure(self):
        # Slot indices are specific to these versioned Valve C API tables.
        system = self.interface(b"IVRSystem_022")
        overlay = self.interface(b"IVROverlay_027")
        handle = c.c_uint64
        self.activity = bind(system, 15, c.c_int, c.c_uint32)
        self.connected = bind(system, 20, c.c_bool, c.c_uint32)
        self.destroy = bind(overlay, 2, c.c_int, handle)
        self.show_overlay = bind(overlay, 41, c.c_int, handle)
        self.hide_overlay = bind(overlay, 42, c.c_int, handle)
        self.load_texture = bind(overlay, 61, c.c_int, handle, c.c_char_p)

        create = bind(overlay, 1, c.c_int, c.c_char_p, c.c_char_p, c.POINTER(handle))
        self.width = bind(overlay, 21, c.c_int, handle, c.c_float)
        self.alpha = bind(overlay, 15, c.c_int, handle, c.c_float)
        self.transform = bind(overlay, 34, c.c_int, handle, c.c_uint32, c.POINTER(Matrix34))
        self.position = None
        set_input = bind(overlay, 48, c.c_int, handle, c.c_int)
        set_order = bind(overlay, 19, c.c_int, handle, c.c_uint32)

        key = f"frame-charge-protocol.{os.getpid()}".encode("ascii")
        self.check("CreateOverlay", create(key, b"Charging protocol", c.byref(self.handle)))
        self.check("SetOverlayInputMethod", set_input(self.handle, 0))
        self.check("SetOverlaySortOrder", set_order(self.handle, 10))

    @staticmethod
    def check(operation, error):
        if error:
            raise RuntimeError(f"{operation}: {error}")

    def is_in_use(self):
        return self.activity(0) in {1, 2}  # UserInteraction / UserInteraction_Timeout

    def set_opacity(self, opacity):
        self.check("SetOverlayAlpha", self.alpha(self.handle, opacity))

    def set_position(self, position):
        if position == self.position:
            return
        x = -0.52 if "left" in position else 0.52 if "right" in position else 0.0
        y = 0.40 if "top" in position else -0.40 if "bottom" in position else 0.0
        matrix = Matrix34()
        for index, offset in enumerate((x, y, -1.25)):
            matrix.rows[index][index] = 1.0
            matrix.rows[index][3] = offset
        self.check("SetOverlayTransformTrackedDeviceRelative", self.transform(self.handle, 0, c.byref(matrix)))
        self.position = position

    def show(self, protocol, settings, watts=None):
        if protocol == STOPPED:
            filename, width = f"stopped-{language(settings)}.png", 0.43
        elif settings["full_name"]:
            filename, width = FULL_TEXTURES[protocol]
        else:
            filename, width = TEXTURES[protocol], 0.28
        path = Path(__file__).resolve().with_name(filename)
        label = protocol
        if protocol != STOPPED and settings["show_watts"] and watts is not None:
            try:
                if self.textures is None:
                    self.textures = TemporaryDirectory(prefix="frame-charge-")
                label = contract_label(protocol, settings["full_name"], watts)
                expanded_pps = protocol == "USB PD PPS" and settings["full_name"]
                dynamic = Path(self.textures.name) / f"{protocol.replace(' ', '-')}-{int(settings['full_name'])}-{watts:.1f}.png"
                if not dynamic.is_file():
                    render_contract_texture(dynamic, label, expanded_pps)
                path = dynamic
                width = 0.58 if settings["full_name"] else 0.48
            except (OSError, RuntimeError) as error:
                print(f"[frame-charge-protocol] wattage texture: {error}", file=sys.stderr, flush=True)
                label = protocol
        self.set_position(settings["position"])
        self.check("SetOverlayWidthInMeters", self.width(self.handle, width))
        self.set_opacity(1.0)
        self.check("SetOverlayFromFile", self.load_texture(self.handle, os.fsencode(path)))
        self.check("ShowOverlay", self.show_overlay(self.handle))
        print(f"[frame-charge-protocol] showed {label}", file=sys.stderr, flush=True)

    def hide(self):
        self.check("HideOverlay", self.hide_overlay(self.handle))

    def close(self):
        if self.handle.value:
            self.destroy(self.handle)
            self.handle.value = 0
        self.lib.VR_ShutdownInternal()
        if self.textures is not None:
            self.textures.cleanup()


def run():
    notice = ProtocolNotice()
    view = None
    retry_at = 0.0
    sample_at = 0.0
    last_error = None
    try:
        while True:
            now = time.monotonic()
            try:
                if now >= sample_at:
                    sample_at = now + SAMPLE_SECONDS
                    settings = load_preferences()
                    sample = read_charging()
                    need_overlay = (settings["show"] and sample.protocol) or (settings["stop_popup"] and notice.stop_pending)
                    if view is None and need_overlay and now >= retry_at:
                        view = OpenVROverlay()
                    if view is not None and not view.connected(0):
                        raise RuntimeError("SteamVR headset unavailable")
                    notice.update(sample, view, settings=settings)
                    if view is not None and notice.visible is not None:
                        view.set_position(settings["position"])
                delay = notice.animate(view, time.monotonic())
                if view is not None:
                    last_error = None
            except (RuntimeError, OSError) as error:
                if str(error) != last_error:
                    print(f"[frame-charge-protocol] {error}", file=sys.stderr, flush=True)
                    last_error = str(error)
                if view is not None:
                    view.close()
                    view = None
                notice.hide(None)
                retry_at = now + 3.0
                delay = SAMPLE_SECONDS

            # Framey closes this pipe on unload. It also closes if Framey exits.
            delay = min(delay, max(0.0, sample_at - time.monotonic()))
            if select.select([sys.stdin], [], [], delay)[0] and not os.read(sys.stdin.fileno(), 1):
                return
    finally:
        notice.sound.close()
        if view is not None:
            view.close()


if __name__ == "__main__":
    run()
