"""Read charging state, the active USB contract, and battery-side power."""

from __future__ import annotations

from pathlib import Path
import re
from typing import NamedTuple


DAEMON = Path("/run/deckardcharger")
POWER = Path("/sys/class/power_supply")
TYPEC = Path("/sys/class/typec")
CONTRACT = re.compile(r"Valid=1,\s*Voltage=([1-9]\d*)mV,\s*Current=([1-9]\d*)mA")


def read_text(path):
    try:
        return path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeError):
        return ""


class ChargingSample(NamedTuple):
    connected: bool | None = None
    protocol: str | None = None
    charging: bool | None = None
    voltage_mv: int | None = None
    current_ma: int | None = None

    @property
    def contract_watts(self):
        if self.voltage_mv is not None and self.current_ma is not None:
            return self.voltage_mv * self.current_ma / 1_000_000
        return None


def read_charging(daemon=DAEMON, power=POWER, typec=TYPEC):
    ac = read_text(daemon / "ac_status").lower()
    if ac == "disconnected":
        return ChargingSample(False)
    if ac not in {"connected", "connected slow"}:
        return ChargingSample()
    status = read_text(daemon / "battery_status").lower()
    charging = {"charging": True, "not charging": False, "discharging": False, "full": False}.get(status)
    connected = ChargingSample(True, charging=charging)

    sources = list(power.glob("tcpm-source-psy-*"))
    if len(sources) != 1:
        return connected
    source = sources[0]
    online = read_text(source / "online")
    mode = read_text(typec / "port0" / "power_operation_mode")
    role = read_text(typec / "port0" / "power_role")
    contract = CONTRACT.fullmatch(read_text(daemon / "typec_contract"))
    if mode != "usb_power_delivery" or role not in {"source [sink]", "[sink]", "sink"} or not contract:
        return connected

    # TCPM uses online=1 for a fixed contract and online=2 for active PPS.
    # usb_type can advertise PPS even while the selected contract is fixed.
    voltage_mv, current_ma = map(int, contract.groups())
    if online == "1":
        return ChargingSample(True, "USB PD", charging, voltage_mv, current_ma)
    usb_type = read_text(source / "usb_type")
    if online == "2" and (usb_type == "PD_PPS" or "[PD_PPS]" in usb_type.split()):
        return ChargingSample(True, "USB PD PPS", charging, voltage_mv, current_ma)
    return connected


def read_details(daemon=DAEMON, power=POWER, typec=TYPEC):
    sample = read_charging(daemon, power, typec)
    battery_watts = None
    for supply in sorted(power.iterdir()) if power.is_dir() else ():
        if read_text(supply / "type") != "Battery":
            continue
        try:
            voltage_uv = int(read_text(supply / "voltage_now"))
            current_ua = int(read_text(supply / "current_now"))
        except ValueError:
            continue
        if voltage_uv > 0:
            battery_watts = voltage_uv * current_ua / 1_000_000_000_000
            break
    return {**sample._asdict(), "contract_watts": sample.contract_watts, "battery_watts": battery_watts}
