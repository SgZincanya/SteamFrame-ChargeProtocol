# 蓝牙电量扩展接口 · Headphone battery providers

公开安装包只带系统蓝牙读取，默认使用 BlueZ 已上报的电量。机型专用读取（包括小米 Air 4 SE 左耳、右耳和充电盒）需单独安装补丁。只安装你信任的扩展，扩展会在当前 SteamOS 用户权限下运行。

将补丁的 `<id>.py` 放到头显的 `~/.config/framey/frame-charge-protocol-providers/`，重启 Framey，再到插件的 **蓝牙电量来源** 选择它。切回系统蓝牙即可停用专用查询。更新插件 ZIP 时，这个外置目录会保留。扩展需提供同步、有超时的 `read()`，只查询能识别的耳机。返回 `None` 或没有任何有效电量时，会回退到系统蓝牙。

The public ZIP ships with BlueZ support. Model-specific readers, including Xiaomi Air 4 SE component readings, require a separate provider. Install only providers you trust. They run with your SteamOS user permissions.

Place a provider such as `example-buds.py` in `~/.config/framey/frame-charge-protocol-providers/`, restart Framey, and select its ID under **Bluetooth Battery Source**. IDs use lowercase letters, digits, and hyphens. This directory is outside the plugin ZIP and survives updates. Switch to **System Bluetooth** to disable provider queries.

Export a synchronous, bounded `read()` function. Framey calls it in a worker thread while the details panel is open. Query only a device your provider recognizes. Return `None` when no device applies. The plugin falls back to BlueZ when the selected provider is missing, raises an exception, or returns no valid battery values.

```python
{
    "name": "Example Buds",
    "connected": True,
    "left": 72,
    "right": 65,
    "case": 48,
    "stale": ["case"],
    "age_seconds": {"case": 12},
}
```

- `name` is the device name and `connected` is its current connection state.
- Use `percent` for a device-wide reading. Add `left`, `right`, or `case` for supported component fields.
- A reading is an integer from `0` to `100`. Use `None` if a supported field has no reading, or omit the field if the device does not support it.
- If you return an earlier reading, name its field in `stale`. Include that field in `age_seconds` with the elapsed seconds since its last successful read so the panel can show its age. Do not carry readings over to a different physical device.

Test discovery and parsing with fixtures and verify the reader against the target device. Keep provider code and device-specific data outside the public plugin ZIP.
