"""Read the batteries BlueZ already exposes for connected audio devices."""


DEVICE = "org.bluez.Device1"
BATTERY = "org.bluez.Battery1"
AUDIO_PROFILES = {
    "00001108-0000-1000-8000-00805f9b34fb",  # Headset
    "0000110b-0000-1000-8000-00805f9b34fb",  # Audio Sink
    "0000111e-0000-1000-8000-00805f9b34fb",  # Hands-Free
    "0000184e-0000-1000-8000-00805f9b34fb",  # LE Audio Stream Control
}
AUDIO_ICONS = {"audio-headset", "audio-headphones", "audio-headphones-symbolic", "audio-headset-symbolic"}


def read_objects():
    try:
        import dbus
    except ImportError:
        return {}
    try:
        bus = dbus.SystemBus(private=True)
        try:
            manager = dbus.Interface(bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager")
            return manager.GetManagedObjects(timeout=2)
        finally:
            bus.close()
    except dbus.DBusException:
        return {}


def percentage(properties):
    value = properties.get("Percentage")
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 100:
        return int(value)
    return None


def audio_batteries(objects):
    devices = {}
    for path, interfaces in objects.items():
        device = interfaces.get(DEVICE, {})
        if not device.get("Connected"):
            continue
        icon = device.get("Icon")
        if icon in {"input-gaming", "input-gamepad", "input-keyboard", "input-mouse"}:
            continue
        if icon not in AUDIO_ICONS and AUDIO_PROFILES.isdisjoint(device.get("UUIDs", ())):
            continue
        name = device.get("Alias") or device.get("Name")
        if not name:
            continue
        devices[path] = {"name": str(name), "connected": True, "percent": percentage(interfaces.get(BATTERY, {}))}

    for interfaces in objects.values():
        battery = interfaces.get(BATTERY, {})
        parent = devices.get(battery.get("Device"))
        part = battery.get("Identifier")
        value = percentage(battery)
        if parent is not None and part in {"left", "right", "case"} and value is not None:
            parent[part] = value

    return [item for item in devices.values()
            if any(item.get(key) is not None for key in ("percent", "left", "right", "case"))]
