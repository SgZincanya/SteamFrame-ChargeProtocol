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


def battery_values(flags, opcode, body, sequences):
    if (not flags & 0x80 and opcode == 0x02 and len(body) == 7
            and body[0] == 0 and body[1] in sequences and body[2:4] == b"\x04\x07"):
        return body[4:]
    if flags & 0x80 and opcode == 0x0E:
        # Byte zero is the notification sequence. The rest is a list of TLVs.
        offset = 1
        while offset + 1 < len(body):
            size, tag = body[offset:offset + 2]
            end = offset + 1 + size
            if size < 1 or end > len(body):
                return None
            if tag == 0 and size == 4:
                return body[offset + 2:end]
            offset = end
    return None


def battery_reports(buffer, sequences):
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
        if end == 0xEF:
            values = battery_values(flags, opcode, body, sequences)
            if values is not None:
                levels = (value & 0x7F for value in values)
                yield {key: level for key, level in zip(PARTS, levels) if 1 <= level <= 100}


def query(address, channel):
    readings = {}
    with socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM) as link:
        link.settimeout(2)
        link.connect((address, channel))
        time.sleep(0.4)
        buffer = bytearray()
        request = bytearray(QUERY)
        for sequence in range(1, 4):
            request[7] = sequence
            link.settimeout(1.5)
            try:
                link.sendall(request)
            except ConnectionError:
                if readings:
                    return readings
                raise
            deadline = time.monotonic() + 1.5
            while (remaining := deadline - time.monotonic()) > 0:
                link.settimeout(remaining)
                try:
                    data = link.recv(4096)
                except TimeoutError:
                    break
                except ConnectionError:
                    if readings:
                        return readings
                    raise
                if not data:
                    return readings or None
                buffer.extend(data)
                for report in battery_reports(buffer, range(1, sequence + 1)):
                    readings.update(report)
                if len(readings) == len(PARTS):
                    return readings
    return readings or None


class Air4Reader:
    def __init__(self):
        self.address = None
        self.channel = None
        self.name = None
        self.last = {}

    def result(self, connected, report):
        now = time.monotonic()
        fresh = {part: value for part, value in (report or {}).items() if value is not None}
        self.last.update({part: (value, now) for part, value in fresh.items()})
        ages = {part: int(now - received_at) for part, (_, received_at) in self.last.items() if part not in fresh}
        return {"name": self.name, "connected": connected,
                **{part: self.last[part][0] if part in self.last else None for part in PARTS},
                "stale": list(ages), "age_seconds": ages}

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


_reader = Air4Reader()
read = _reader.read
