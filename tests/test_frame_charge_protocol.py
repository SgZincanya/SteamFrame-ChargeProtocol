import ctypes as c
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from charging import ChargingSample, read_charging, read_details
from bluetooth import AUDIO_PROFILES, BATTERY, DEVICE, audio_batteries
import history
from overlay import FULL_TEXTURES, OpenVROverlay, ProtocolNotice, STOPPED, StopAudio, StopDetector, TEXTURES
from preferences import DEFAULTS, LOCALES, load, save
from texture import contract_label


class View:
    def __init__(self):
        self.awake = True
        self.calls = []
        self.opacity = []
        self.watts = []

    def is_in_use(self):
        return self.awake

    def show(self, label, settings, watts):
        self.calls.append(label)
        self.watts.append(watts)

    def hide(self):
        self.calls.append("hidden")

    def set_opacity(self, value):
        self.opacity.append(value)


class NoticeTests(unittest.TestCase):
    def setUp(self):
        self.notice = ProtocolNotice()
        self.view = View()

    def read(self, time, protocol=None, connected=True):
        self.notice.update(ChargingSample(connected, protocol), self.view, lambda: time)

    def test_confirm_duration_and_deduplication(self):
        self.read(0, "USB PD")
        self.assertEqual(self.view.calls, [])
        self.read(0.25, "USB PD")
        self.read(5.249, "USB PD")
        self.notice.animate(self.view, 5.249)
        self.assertEqual(self.view.calls, ["USB PD"])
        self.read(5.25, "USB PD")
        self.notice.animate(self.view, 5.25)
        self.read(8, "USB PD")
        self.assertEqual(self.view.calls, ["USB PD", "hidden"])

    def test_switch_unplug_and_replug(self):
        self.read(0, "USB PD")
        self.read(0.25, "USB PD")
        self.read(0.50, "USB PD PPS")
        self.read(0.75, "USB PD PPS")
        self.assertEqual(self.notice.hide_at, 5.75)
        self.read(1, connected=False)
        self.read(1.25, "USB PD PPS")
        self.read(1.50, "USB PD PPS")
        self.assertEqual(self.view.calls, ["USB PD", "hidden", "USB PD PPS", "hidden", "USB PD PPS"])

    def test_standby_and_unknown(self):
        self.view.awake = False
        self.read(0, "USB PD")
        self.read(0.25, "USB PD")
        self.assertEqual(self.view.calls, [])
        self.view.awake = True
        self.read(30, "USB PD")
        self.assertEqual(self.notice.hide_at, 35)
        self.read(31)
        self.read(31.25, "USB PD PPS")
        self.read(31.50)
        self.assertEqual(self.view.calls, ["USB PD"])

    def test_time_starts_after_show(self):
        self.read(0, "USB PD")
        self.notice.update(ChargingSample(True, "USB PD"), self.view, lambda: 0.60)
        self.assertEqual(self.notice.hide_at, 5.60)

    def test_fixed_contract_waits_until_wattage_is_stable(self):
        for now, milliamps in [(0, 500), (.25, 2600), (.50, 2600), (.75, 2200), (1, 2200)]:
            sample = ChargingSample(True, "USB PD", True, 15000, milliamps)
            self.notice.update(sample, self.view, lambda: now)
        self.assertEqual(self.view.calls, ["USB PD"])
        self.assertEqual(self.view.watts, [39])

    def test_fade_and_settings(self):
        self.read(0, "USB PD")
        sample = ChargingSample(True, "USB PD")
        self.notice.update(sample, self.view, lambda: 1, {**DEFAULTS, "seconds": 3})
        self.notice.animate(self.view, 3.50)
        self.assertEqual(self.view.opacity, [])
        self.notice.animate(self.view, 4 - 0.45 / 2)
        self.assertAlmostEqual(self.view.opacity[-1], 0.5)
        self.notice.animate(self.view, 4)
        self.assertEqual(self.view.calls, ["USB PD", "hidden"])

    def test_persisted_options(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            path = Path(directory) / "settings.json"
            self.assertEqual(load(path), DEFAULTS)
            save("fade", False, path)
            save("seconds", 8, path)
            save("language", "zh-Hant", path)
            save("position", "bottom-right", path)
            self.assertEqual(load(path), {**DEFAULTS, "seconds": 8, "fade": False,
                                         "language": "zh-Hant", "position": "bottom-right"})
            with self.assertRaises(ValueError):
                save("seconds", -1, path)
            path.write_text('{"suppress":false}')
            self.assertFalse(load(path)["hide_slow_popup"])
            self.assertFalse(load(path)["mute_slow_sound"])

    def test_stop_outputs_are_independent(self):
        charging = ChargingSample(True, "USB PD", True)
        disconnected = ChargingSample(False)
        for popup, sound in ((True, False), (False, True), (True, True), (False, False)):
            notice, view = ProtocolNotice(), View()
            options = {**DEFAULTS, "show": False, "stop_popup": popup, "stop_sound": sound}
            process = Mock()
            process.poll.return_value = 0
            with patch("overlay.play_stop_sound", return_value=process) as play:
                for sample, now in [(charging, 0), (charging, .25), (disconnected, 1),
                                    (disconnected, 1.25), (disconnected, 1.5)]:
                    notice.update(sample, view, lambda: now, options)
                self.assertEqual(view.calls, [STOPPED] if popup else [])
                self.assertEqual(play.call_count, int(sound))

    def test_paused_and_unplugged_are_debounced_and_deduplicated(self):
        detector = StopDetector()
        charging = ChargingSample(True, "USB PD", True)
        paused = ChargingSample(True, "USB PD", False)
        disconnected = ChargingSample(False)
        detector.update(charging, 0)
        self.assertEqual(detector.update(charging, .25), "resumed")
        self.assertIsNone(detector.update(paused, .5))
        self.assertIsNone(detector.update(charging, .75))
        self.assertIsNone(detector.update(paused, 1))
        self.assertIsNone(detector.update(paused, 1.5))
        self.assertEqual(detector.update(paused, 2.5), STOPPED)
        self.assertIsNone(detector.update(disconnected, 2.75))
        self.assertIsNone(detector.update(disconnected, 3))

    def test_unplug_later_after_full_still_notifies(self):
        detector = StopDetector()
        charging = ChargingSample(True, "USB PD", True)
        full = ChargingSample(True, "USB PD", False)
        disconnected = ChargingSample(False)
        detector.update(charging, 0)
        detector.update(charging, .25)
        detector.update(full, 1)
        self.assertEqual(detector.update(full, 2.5), STOPPED)
        detector.update(disconnected, 15)
        self.assertEqual(detector.update(disconnected, 15.25), STOPPED)
        self.assertIsNone(detector.update(disconnected, 15.5))

    def test_stop_audio_waits_for_visible_overlay_when_enabled(self):
        charging = ChargingSample(True, "USB PD", True)
        disconnected = ChargingSample(False)
        self.view.awake = False
        settings = {**DEFAULTS, "show": False}
        with patch("overlay.play_stop_sound", return_value=None) as play:
            for sample, now in [(charging, 0), (charging, .25), (disconnected, 1), (disconnected, 1.25)]:
                self.notice.update(sample, self.view, lambda: now, settings)
            play.assert_not_called()
            self.view.awake = True
            self.notice.update(disconnected, self.view, lambda: 3, settings)
            self.assertEqual(self.view.calls, [STOPPED])
            play.assert_called_once_with(retry=False)

    def test_playback_failure_retries_once(self):
        class Exited:
            def __init__(self, code):
                self.code = code

            def poll(self):
                return self.code

        audio = StopAudio()
        with patch("overlay.play_stop_sound", side_effect=[Exited(1), Exited(0)]) as play:
            audio.request(0)
            for now in (0, .25, .50, .75, 1):
                audio.update(now, True)
            self.assertEqual([call.kwargs for call in play.call_args_list], [{"retry": False}, {"retry": True}])


class ChargingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.daemon = self.root / "deckardcharger"
        self.power = self.root / "power_supply"
        self.typec = self.root / "typec"
        self.source = self.power / "tcpm-source-psy-example"
        self.port = self.typec / "port0"
        for directory in [self.daemon, self.source, self.port]:
            directory.mkdir(parents=True)
        (self.daemon / "ac_status").write_text("Connected\n")
        (self.daemon / "typec_contract").write_text("Valid=1, Voltage=15000mV, Current=3000mA\n")
        (self.port / "power_operation_mode").write_text("usb_power_delivery\n")
        (self.port / "power_role").write_text("source [sink]\n")
        (self.source / "online").write_text("1\n")
        (self.source / "usb_type").write_text("C PD [PD_PPS]\n")

    def read(self):
        return read_charging(self.daemon, self.power, self.typec)

    def test_fixed_and_pps(self):
        self.assertEqual(self.read(), ChargingSample(True, "USB PD", None, 15000, 3000))
        (self.source / "online").write_text("2")
        self.assertEqual(self.read(), ChargingSample(True, "USB PD PPS", None, 15000, 3000))
        (self.source / "usb_type").write_text("[PD] PD_PPS")
        self.assertEqual(self.read(), ChargingSample(True))

    def test_invalid_and_unplug(self):
        (self.daemon / "typec_contract").write_text("Valid=0, Voltage=15000mV, Current=3000mA")
        self.assertEqual(self.read(), ChargingSample(True))
        (self.daemon / "ac_status").write_text("Disconnected")
        self.assertEqual(self.read(), ChargingSample(False))

    def test_wrong_role_and_unknown(self):
        (self.port / "power_role").write_text("[source] sink")
        self.assertEqual(self.read(), ChargingSample(True))
        (self.daemon / "ac_status").unlink()
        self.assertEqual(self.read(), ChargingSample())

    def test_details_separate_contract_from_signed_battery_power(self):
        battery = self.power / "max1720x_battery"
        battery.mkdir()
        (battery / "type").write_text("Battery")
        (battery / "voltage_now").write_text("8800000")
        (battery / "current_now").write_text("500000")
        (self.daemon / "typec_contract").write_text("Valid=1, Voltage=15000mV, Current=2600mA")
        data = read_details(self.daemon, self.power, self.typec)
        self.assertEqual(data["contract_watts"], 39)
        self.assertEqual(data["battery_watts"], 4.4)
        (battery / "current_now").write_text("-500000")
        (self.daemon / "ac_status").write_text("Disconnected")
        data = read_details(self.daemon, self.power, self.typec)
        self.assertIsNone(data["contract_watts"])
        self.assertEqual(data["battery_watts"], -4.4)


class HistoryTests(unittest.TestCase):
    def test_only_observed_sessions_are_saved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "history.sqlite3"
            recorder = history.Recorder(path)
            settings = {**DEFAULTS, "record_history": True}
            with patch("history.time.time", side_effect=[10, 20, 40, 50, 90]), \
                 patch("history.elapsed_clock", side_effect=[10, 20, 40, 50, 85]):
                for state in (True, True, False, False, True, True, False, None, False, False):
                    recorder.update(state, settings)
            self.assertEqual(history.sessions(25, path), [{"started": 40, "ended": 90, "seconds": 45}])
            recorder.update(True, settings)
            recorder.update(True, settings)
            recorder.update(True, DEFAULTS)
            recorder.update(False, settings)
            recorder.update(False, settings)
            self.assertEqual(len(history.sessions(25, path)), 1)

    def test_limit_keeps_newest_and_clear_persists(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "history.sqlite3"
            recorder = history.Recorder(path)
            settings = {**DEFAULTS, "record_history": True, "history_limit": 10}
            with patch("history.time.time", side_effect=range(25)), \
                 patch("history.elapsed_clock", side_effect=range(25)):
                for state in [False, False] + [True, True, False, False] * 12:
                    recorder.update(state, settings)
            self.assertEqual([row["started"] for row in history.sessions(100, path)], list(range(23, 3, -2)))
            history.prune(3, path)
            self.assertEqual([row["started"] for row in history.sessions(100, path)], [23, 21, 19])
            history.clear(path)
            self.assertEqual(history.sessions(100, path), [])


class OverlayTests(unittest.TestCase):
    def test_contract_label(self):
        self.assertEqual(contract_label("USB PD", False, 39), "USB PD · 39 W")
        self.assertEqual(contract_label("USB PD PPS", False, 27.5), "USB PD PPS · 27.5 W")
        self.assertEqual(contract_label("USB PD", True, 39), "USB Power Delivery · 39 W")

    def test_calls_and_textures(self):
        calls = []
        def fake_bind(table, index, result, *types):
            def invoke(*args):
                calls.append((table, index, args))
                if (table, index) == (b"IVROverlay_027", 1):
                    c.cast(args[-1], c.POINTER(c.c_uint64))[0] = 42
                if (table, index) == (b"IVRSystem_022", 15):
                    return 1
                return 0
            return invoke

        view = OpenVROverlay.__new__(OpenVROverlay)
        view.interface = lambda version: version
        view.handle = c.c_uint64()
        with patch("overlay.bind", fake_bind):
            view.configure()
            self.assertTrue(view.is_in_use())
            for full_name, textures in ((False, TEXTURES), (True, {k: v[0] for k, v in FULL_TEXTURES.items()})):
                for label, filename in textures.items():
                    view.show(label, {**DEFAULTS, "full_name": full_name})
                    path = Path(calls[-2][2][1].decode())
                    self.assertEqual(path.name, filename)
                    self.assertEqual(path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
                    self.assertEqual(calls[-1][:2], (b"IVROverlay_027", 41))
                    view.hide()
                    self.assertEqual(calls[-1][:2], (b"IVROverlay_027", 42))
            for locale, strings in LOCALES.items():
                self.assertEqual(strings.keys(), LOCALES["en"].keys())
                view.show(STOPPED, {**DEFAULTS, "language": "auto", "steam_locale": locale, "position": "bottom-right"})
                path = Path(calls[-2][2][1].decode())
                self.assertEqual(path.name, f"stopped-{locale}.png")
                self.assertEqual(path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(view.position, "bottom-right")


class HeadphoneTests(unittest.TestCase):
    def test_default_bluez_reads_audio_devices_and_excludes_controllers(self):
        headset = {"Connected": True, "Alias": "Example buds", "UUIDs": [sorted(AUDIO_PROFILES)[0]]}
        controller = {"Connected": True, "Alias": "Game controller", "Icon": "input-gaming"}
        objects = {
            "/headset": {DEVICE: headset, BATTERY: {"Percentage": 75}},
            "/headset/battery_left": {BATTERY: {"Device": "/headset", "Identifier": "left", "Percentage": 60}},
            "/pad": {DEVICE: controller, BATTERY: {"Percentage": 90}},
            "/offline": {DEVICE: {**headset, "Connected": False}, BATTERY: {"Percentage": 80}},
        }
        self.assertEqual(audio_batteries(objects), [{"name": "Example buds", "connected": True, "percent": 75, "left": 60}])
        self.assertEqual(DEFAULTS["headphone_provider"], "bluez")


class HeadphoneSourceTests(unittest.TestCase):
    def setUp(self):
        path = Path(sys.path[0]) / "backend.py"
        spec = spec_from_file_location("test_frame_charge_backend", path)
        self.backend = module_from_spec(spec)
        spec.loader.exec_module(self.backend)

    def test_provider_is_only_loaded_when_selected(self):
        system = {"name": "System audio", "connected": True, "percent": 85}
        components = {"name": "Example buds", "connected": True, "left": 82, "right": 87, "case": 70}
        with tempfile.TemporaryDirectory() as folder:
            provider_dir = Path(folder)
            provider = provider_dir / "example-buds.py"
            provider.write_text(f"def read():\n    return {components!r}\n", encoding="utf-8")
            with patch.object(self.backend, "PROVIDER_DIR", provider_dir), \
                 patch.object(self.backend.preferences, "load", return_value=DEFAULTS.copy()) as load_settings, \
                 patch.object(self.backend.bluetooth, "read_objects", return_value={}), \
                 patch.object(self.backend.bluetooth, "audio_batteries", return_value=[system]) as bluez:
                self.assertEqual(self.backend.provider_ids(), ["bluez", "example-buds"])
                self.assertEqual(self.backend.read_headphones(), [system])
                self.assertEqual(self.backend.load_provider.cache_info().currsize, 0)
                load_settings.return_value["headphone_provider"] = "example-buds"
                self.assertEqual(self.backend.read_headphones(), [components])
                self.assertEqual(bluez.call_count, 1)
                provider.unlink()
                self.assertEqual(self.backend.read_headphones(), [system])

    def test_invalid_or_empty_provider_falls_back_to_bluez(self):
        system = {"name": "System audio", "connected": True, "percent": 85}
        with tempfile.TemporaryDirectory() as folder:
            provider_dir = Path(folder)
            (provider_dir / "empty.py").write_text("def read():\n    return {'left': None}\n", encoding="utf-8")
            (provider_dir / "broken.py").write_text("def read():\n    raise RuntimeError('failed')\n", encoding="utf-8")
            with patch.object(self.backend, "PROVIDER_DIR", provider_dir), \
                 patch.object(self.backend.preferences, "load") as load_settings, \
                 patch.object(self.backend.bluetooth, "read_objects", return_value={}), \
                 patch.object(self.backend.bluetooth, "audio_batteries", return_value=[system]):
                for selected in ("empty", "broken"):
                    load_settings.return_value = {**DEFAULTS, "headphone_provider": selected}
                    self.assertEqual(self.backend.read_headphones(), [system])


if __name__ == "__main__":
    unittest.main(verbosity=2)
