# 小米 Air 4 SE 电量模块 · Xiaomi Air 4 SE Battery Provider

## 中文

此模块为 Steam Frame 的充电协议插件提供小米 Air 4 SE 左耳、右耳和充电盒的电量。分项读取支持主插件 v0.9.1 起的版本，头显低电量提醒需要主插件 v0.9.2 或更高版本。模块使用 SteamOS 的 BlueZ、Python D-Bus 和 `sdptool`。

### 自己构建

下载或克隆本仓库，在仓库根目录运行以下命令。打包仅依赖 Python 3.9 或更高版本，生成 `dist/Air4-SE-Provider-v1.0.0.zip`。

```sh
python3 scripts/build_zip.py --air4-se
```

也可以直接 [下载模块 ZIP](https://github.com/SgZincanya/SteamFrame-ChargeProtocol/releases/download/v0.9.2/Air4-SE-Provider-v1.0.0.zip)。

### 安装和使用

1. 先安装主插件，再将耳机与 Steam Frame 配对并连接。
2. 解压模块 ZIP，将 `air4-se.py` 复制到头显上的 `~/.config/framey/frame-charge-protocol-providers/`。在头显终端里进入解压目录后可运行以下命令。

   ```sh
   mkdir -p ~/.config/framey/frame-charge-protocol-providers
   cp air4-se.py ~/.config/framey/frame-charge-protocol-providers/
   systemctl --user restart framey.service
   ```

3. 在 Framey 打开 **充电协议 → 蓝牙电量来源**，选择 `air4-se`。要测试盒子电量，先把耳机放回盒里再开盖。没有新回报时，详情页会显示上次成功读取的时间。

更新模块时，替换该文件并重启 Framey。要暂停专用查询，切回 **系统蓝牙**。要移除模块，切回系统蓝牙后删除该文件并重启 Framey。

## English

This provider supplies left earbud, right earbud, and charging case readings for Xiaomi Air 4 SE on Steam Frame. Component readings work with Charge Protocol v0.9.1 or newer. The headset low battery alert requires v0.9.2 or newer. The provider uses SteamOS BlueZ, Python D-Bus, and `sdptool`.

### Build

Download or clone this repository and run the following from its root with Python 3.9 or newer. It creates `dist/Air4-SE-Provider-v1.0.0.zip`.

```sh
python3 scripts/build_zip.py --air4-se
```

You can also [download the provider ZIP](https://github.com/SgZincanya/SteamFrame-ChargeProtocol/releases/download/v0.9.2/Air4-SE-Provider-v1.0.0.zip).

### Install and use

1. Install the main plugin and pair and connect the earbuds to Steam Frame.
2. Extract the provider ZIP and copy `air4-se.py` to `~/.config/framey/frame-charge-protocol-providers/` on the headset. From the extracted directory on the headset, run the commands below.

   ```sh
   mkdir -p ~/.config/framey/frame-charge-protocol-providers
   cp air4-se.py ~/.config/framey/frame-charge-protocol-providers/
   systemctl --user restart framey.service
   ```

3. Select `air4-se` under **Charging Protocol → Bluetooth Battery Source** in Framey. To check the case battery, put the earbuds in the case and open the lid. The panel shows the age of cached readings when there is no fresh report.

To update the provider, replace the file and restart Framey. To pause provider queries, select **System Bluetooth**. To uninstall, switch to System Bluetooth, remove the file, and restart Framey.

## 授权与参考 · License and reference

MIT. The provider implements read-only battery requests and notifications. [XiaomiTWS protocol reference](https://github.com/web1n/android_packages_apps_XiaomiTWS)
