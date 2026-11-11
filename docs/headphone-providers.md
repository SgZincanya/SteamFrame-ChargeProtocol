# 蓝牙电量扩展接口 · Headphone battery providers

没有选择分项来源时，`bluetooth.py` 只读取 BlueZ 已经公开的电量字段。配件协议只会在用户选择对应来源后运行。

To add an opt-in provider, create a Python module and register a reader instance in `HEADPHONE_PROVIDERS` in `backend.py`. Use a lowercase identifier such as `example-buds` and add `headphone_example-buds` to each language in `locales.json`. The registered identifier appears in **Bluetooth Battery Source**.

Implement a synchronous, bounded `read()` method. Framey calls it off the main event loop while the details panel is open. Read only a device your provider recognizes. Return `None` when the provider has no applicable device so the plugin can fall back to the system Bluetooth reading.

```python
{
    "name": "Example Buds",
    "connected": True,
    "left": 72,
    "right": 65,
    "case": 48,
    "stale": ["case"],
}
```

- `name` is the device name and `connected` is its current connection state.
- Use `percent` for a device-wide reading. Add `left`, `right`, or `case` for supported component fields.
- A reading is an integer from `0` to `100`. Use `None` if a supported field has no reading, or omit the field if the device does not support it.
- If you return an earlier reading, name its field in `stale`. Do not carry readings over to a different physical device.

The bundled Air 4 SE reader in `headphones.py` provides a reference implementation. Test discovery and parsing with fixtures and verify the reader against the target device before submitting it.
