# Steam Frame Charge Protocol

<img src="logo.svg" width="96" alt="A blue power bank overlapping a red battery">

Steam Frame 的 Framey 插件。插线后在头显内显示已确认的 USB PD 或 PPS 协议与协商功率，详情页实时显示电池净功率。慢充弹窗、慢充音效、停止充电浮层和停止充电提示音可以分别设置。浮层支持位置、时长与淡出设置，菜单提供简体中文、繁体中文、英文、日语和韩语。

## 安装

请先在 Steam Frame 上安装 [Framey](https://github.com/chaosfox26/framey)。

### 在头显里用链接安装

1. 打开 **Framey → Settings**。
2. 把下面的插件 ZIP 下载地址粘贴到输入框，点击 **Install**。

   ```text
   https://github.com/SgZincanya/SteamFrame-ChargeProtocol/releases/download/v0.9.2/SteamFrame-ChargeProtocol-v0.9.2.zip
   ```

3. 安装成功后，在 Framey 中打开 **充电协议**。要安装其他版本，在 [Releases](https://github.com/SgZincanya/SteamFrame-ChargeProtocol/releases) 复制对应插件 ZIP 的下载地址。

### 用电脑安装 ZIP

从 [Releases](https://github.com/SgZincanya/SteamFrame-ChargeProtocol/releases) 下载插件 ZIP。在电脑的 [Framey App](https://github.com/chaosfox26/framey-app) 中点击 **Add plugin**，选择整个 ZIP，无需解压。Framey App 会重启正在运行的 SteamVR。

## 蓝牙耳机电量

公开安装包默认使用 **系统蓝牙**，无需配置。详情页读取 SteamOS 的 BlueZ 服务已上报的蓝牙音频设备电量。设备上报一个百分比时就显示一个，BlueZ 上报独立部件时则显示对应部件。手柄不在读取范围内。

主插件安装包只带系统蓝牙。小米 Air 4 SE 的左右耳和充电盒分项读取可单独安装。安装模块后，在 **蓝牙电量来源** 选择 `air4-se`，也可随时切回系统蓝牙。[Air 4 SE 模块构建与安装](providers/air4-se/README.md) · [耳机电量扩展接口](docs/headphone-providers.md)

支持上报充电盒电量的设备可使用 **充电盒低电量提醒**。插件在后台定期查询，收到低于 20% 的新读数时在头显内提示一次。回升到 20% 或以上后可以再次提醒。设备没有上报电量时沿用上次读数的时间标记。

## 供电记录

在插件底部打开 **记录电池**，再选择 **查看记录**。从下一次接入 USB 电源开始计时，确认断开后保存插入时间、断开时间和总时长。记录按最近完成排序，默认保留 25 条，可改为 10、50 或 100 条，也可清除。已完成的记录保存在头显本地。

充电宝和墙充都会记录。电池充满后只要 USB 电源仍然接通，就继续计时。插件需要观察到插入和断开才能保存一条完整记录。

## 开发与兼容性

```sh
python -m unittest discover -s tests
python scripts/build_zip.py
```

安装包生成在 `dist/`。插件依赖头显本机的 SteamVR、Framey 和 Cairo。系统蓝牙电量使用 SteamOS 的 BlueZ 与 Python D-Bus。提示音使用 PipeWire 或 PulseAudio。

已有 Steam Frame / SteamOS 0.5.8 的设备验证。公开版的默认蓝牙路径与分项选择可独立切换。慢充弹窗及其音效使用 Steam 客户端的内部入口，客户端更新后可能需要重新适配。

## English

A Framey plugin for Steam Frame that shows the negotiated USB PD/PPS contract in VR, with battery-side power in the details panel. Controls for the slow-charger dialog, its sound, and charging-stop notifications are independent.

**Install in the headset.** Open **Framey → Settings**, paste the [direct plugin ZIP URL](https://github.com/SgZincanya/SteamFrame-ChargeProtocol/releases/download/v0.9.2/SteamFrame-ChargeProtocol-v0.9.2.zip), and select **Install**. Then open **Charging Protocol** in Framey. For another version, copy its plugin ZIP URL from [Releases](https://github.com/SgZincanya/SteamFrame-ChargeProtocol/releases).

You can also download the ZIP and select it with **Add plugin** in the desktop [Framey App](https://github.com/chaosfox26/framey-app). Framey App restarts SteamVR if it is running.

The panel supports Simplified Chinese, Traditional Chinese, English, Japanese, and Korean. The main ZIP includes system Bluetooth battery reporting. The Xiaomi Air 4 SE provider installs separately. Once installed, select `air4-se` under **Bluetooth Battery Source**. [Build and install the Air 4 SE provider](providers/air4-se/README.md) · [Provider interface](docs/headphone-providers.md)

**Low charging case battery alert** checks supported case batteries in the background and shows a headset overlay on a fresh reading below 20%. The alert re-arms after a fresh reading of 20% or more.

Enable **Log battery use** at the bottom of the plugin, then select **View history**. The plugin records both ends of an observed USB power connection and the elapsed time, even if charging pauses while connected. Power banks and wall chargers both count. Completed sessions stay on the headset. You can set how many to keep or clear them from the history page.

## 授权与参考 · License and references

本插件以 [MIT](LICENSE) 发布。Framey、SteamVR、BlueZ 及系统库单独安装，并适用各自的许可。插件包不包含这些项目的源码、二进制文件或字体文件。该项目与 Valve、小米及 Framey 项目无隶属关系。

- [Framey 插件接口](https://github.com/chaosfox26/framey/blob/main/docs/plugins.md)
- [Valve OpenVR Overlay API](https://github.com/ValveSoftware/openvr/wiki/IVROverlay_Overview)
- [BlueZ Battery API](https://github.com/bluez/bluez/blob/master/doc/org.bluez.Battery.rst)
