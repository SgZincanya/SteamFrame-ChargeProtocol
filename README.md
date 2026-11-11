# Steam Frame Charge Protocol

<img src="logo.svg" width="96" alt="A blue power bank overlapping a red battery">

Steam Frame 的 Framey 插件。插线后在头显内显示已确认的 USB PD 或 PPS 协议与协商功率，详情页实时显示电池净功率。慢充弹窗、慢充音效、停止充电浮层和停止充电提示音可以分别设置。浮层支持位置、时长与淡出设置，菜单提供简体中文、繁体中文和英文。

## 安装

1. 在 Steam Frame 上安装 [Framey](https://github.com/chaosfox26/framey)。
2. 从 [Releases](https://github.com/SgZincanya/SteamFrame-ChargeProtocol/releases) 下载插件 ZIP。在电脑的 [Framey App](https://github.com/chaosfox26/framey-app) 中点击 **Add plugin**，选择整个 ZIP。Framey App 会重启正在运行的 SteamVR。
3. 在头显里打开 **Framey → 充电协议**。

## 蓝牙耳机电量

「蓝牙电量来源」默认是 **系统蓝牙**，无需配置。详情页读取 SteamOS 的 BlueZ 服务已上报的蓝牙音频设备电量。设备上报一个百分比时就显示一个，BlueZ 上报独立部件时则显示对应部件。手柄不在读取范围内。

小米 Air 4 SE 用户可以在菜单里手动选择 **小米 Air 4 SE 分项**，通过已连接耳机的配件服务查询左右耳和充电盒。充电盒通常在开盖时回应。某项暂时没回报时，分项模式保留本次运行的上次读数并明确标记。其他型号的贡献者可参考 [耳机读取扩展接口](docs/headphone-providers.md)。

## 开发与兼容性

```sh
python -m unittest discover -s tests
python scripts/build_zip.py
```

安装包生成在 `dist/`。插件依赖头显本机的 SteamVR、Framey 和 Cairo。蓝牙电量使用 SteamOS 的 BlueZ 与 Python D-Bus，Air 4 SE 分项模式还使用 `sdptool`。提示音使用 PipeWire 或 PulseAudio。

已有 Steam Frame / SteamOS 0.5.8 的设备验证。公开版的默认蓝牙路径与分项选择可独立切换。慢充弹窗及其音效使用 Steam 客户端的内部入口，客户端更新后可能需要重新适配。

## English

A Framey plugin for Steam Frame that shows the negotiated USB PD/PPS contract in VR, with battery-side power in the details panel. Controls for the slow-charger dialog, its sound, and charging-stop notifications are independent.

Download the plugin ZIP from [Releases](https://github.com/SgZincanya/SteamFrame-ChargeProtocol/releases), import it with **Add plugin** in Framey App, and open **Charging Protocol** in Framey. System Bluetooth battery reporting is the default and requires no setup. The Xiaomi Air 4 SE component reader is opt-in. See the [provider interface](docs/headphone-providers.md) to add support for another device.

## 授权与参考 · License and references

本插件以 [MIT](LICENSE) 发布。Framey、SteamVR、BlueZ 及系统库单独安装，并适用各自的许可。插件包不包含这些项目的源码、二进制文件或字体文件。该项目与 Valve、小米及 Framey 项目无隶属关系。

- [Framey 插件接口](https://github.com/chaosfox26/framey/blob/main/docs/plugins.md)
- [Valve OpenVR Overlay API](https://github.com/ValveSoftware/openvr/wiki/IVROverlay_Overview)
- [BlueZ Battery API](https://github.com/bluez/bluez/blob/master/doc/org.bluez.Battery.rst)
- [XiaomiTWS](https://github.com/web1n/android_packages_apps_XiaomiTWS) 提供 Air 4 SE 的协议参考。此项目独立实现了只读查询与解析。
