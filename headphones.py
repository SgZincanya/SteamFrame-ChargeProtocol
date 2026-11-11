"""Read the three battery fields of a connected Xiaomi Air 4 SE."""

import re
import socket
import subprocess
import time


FAST_CONNECT = "0000fd2d-0000-1000-8000-00805f9b34fb"
HEADER = b"\xfe\xdc\xba"
QUERY = bytes.fromhex("fe dc ba c0 02 00 05 01 00 00 00 80 ef")
PARTS = ("left", "right", "case")


def connected_air4(devices):
    matches = [device for device in devices if device.get("Connected")
               and FAST_CONNECT in device.get("UUIDs", ())
               and "air4se" in "".join(device.get("Name", "").lower().split())]
    return matches[0] if len(matches) == 1 else None


def paired_device():
    try:
        import dbus
    except ImportError:
        return None

    try:
        bus = dbus.SystemBus(private=True)
        try:
            manager = dbus.Interface(bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager")
            objects = manager.GetManagedObjects(timeout=2)
            return connected_air4(props.get("org.bluez.Device1", {}) for props in objects.values())
        finally:
            bus.close()
    except dbus.DBusException:
        return None


def service_channel(address):
    result = subprocess.run(["sdptool", "search", "--bdaddr", address, "0xfd2d"],
                            capture_output=True, text=True, timeout=3, check=True)
    for record in result.stdout.split("Service RecHandle:"):
        if FAST_CONNECT in record.lower():
            channel = re.search(r"\bChannel:\s*(\d+)\b", record)
            if channel and 1 <= int(channel[1]) <= 30:
                return int(channel[1])
    return None


def battery_report(buffer):
    while len(buffer) >= 8:
        start = buffer.find(HEADER)
        if start < 0:
            del buffer[:-2]
            return None
        del buffer[:start]
        if len(buffer) < 8:
            return None
        flags, opcode = buffer[3:5]
        length = int.from_bytes(buffer[5:7], "big")
        if length > 1024:
            del buffer[:3]
            continue
        if len(buffer) < length + 8:
            return None
        body, end = bytes(buffer[7:7 + length]), buffer[7 + length]
        del buffer[:length + 8]
        if end == 0xEF and not flags & 0x80 and opcode == 0x02 and len(body) == 7 and body[:4] == b"\x00\x01\x04\x07":
            levels = (value & 0x7F for value in body[4:])
            return {key: level if 1 <= level <= 100 else None for key, level in zip(PARTS, levels)}
    return None


def query(address, channel):
    with socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM) as link:
        link.settimeout(2)
        link.connect((address, channel))
        link.sendall(QUERY)
        buffer = bytearray()
        deadline = time.monotonic() + 2
        while (remaining := deadline - time.monotonic()) > 0:
            link.settimeout(remaining)
            data = link.recv(4096)
            if not data:
                break
            buffer.extend(data)
            report = battery_report(buffer)
            if report is not None:
                return report
    return None


class Air4Reader:
    def __init__(self):
        self.address = None
        self.channel = None
        self.name = None
        self.last = {}

    def result(self, connected, report):
        fresh = {part: value for part, value in (report or {}).items() if value is not None}
        self.last.update(fresh)
        return {"name": self.name, "connected": connected,
                **{part: self.last.get(part) for part in PARTS},
                "stale": [part for part in self.last if part not in fresh]}

    def read(self):
        device = paired_device()
        if not device:
            self.channel = None
            return self.result(False, None) if self.last else None
        address = str(device["Address"])
        if address != self.address:
            self.address, self.channel = address, None
            self.last.clear()
        self.name = str(device.get("Alias", device["Name"]))
        report = None
        try:
            if self.channel is None:
                self.channel = service_channel(address)
            if self.channel is not None:
                report = query(address, self.channel)
        except TimeoutError:
            pass
        except (OSError, subprocess.SubprocessError):
            self.channel = None
        return self.result(True, report)
