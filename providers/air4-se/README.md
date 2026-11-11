# 小米 Air 4 SE 电量模块 · Xiaomi Air 4 SE Battery Provider

## 中文

此模块提供小米 Air 4 SE 左耳、右耳和充电盒电量。链接安装需要主插件 **v0.9.3** 或更新版本。模块使用 SteamOS 的 BlueZ、Python D-Bus 和 `sdptool`。

### 在头显里用链接安装

1. 在 Steam Frame 安装或更新[充电协议主插件](../../README.md#安装)，并连接 Air 4 SE。
2. 打开 **Framey → Settings**，粘贴下面的链接，然后点 **Install**。

   ```text
   https://github.com/SgZincanya/SteamFrame-ChargeProtocol/releases/download/v0.9.3/Air4-SE-Provider-v1.1.0.zip
   ```

3. 打开 **充电协议 → 蓝牙电量来源**，选择 `air4-se`。要测试盒子电量，把耳机放回盒里再开盖。没有新回报时，详情页会显示上次成功读取的时间。

更新模块时，在 Settings 粘贴新版模块 ZIP 的链接。也可以在同一页停用或移除 **Air 4 SE Battery Provider**。如曾手动安装过，移除 Framey 模块后，主插件仍可发现手动安装的副本。

### 自己构建

在仓库根目录用 Python 3.9 或更新版本运行以下命令，输出为 `dist/Air4-SE-Provider-v1.1.0.zip`。

```sh
python3 scripts/build_zip.py --air4-se
```

### 手动安装

主插件 v0.9.1 起支持手动安装。解压模块 ZIP，在头显终端进入解压目录后运行以下命令，再在 **蓝牙电量来源** 选择 `air4-se`。

   ```sh
   mkdir -p ~/.config/framey/frame-charge-protocol-providers
   cp air4-se.py ~/.config/framey/frame-charge-protocol-providers/
   systemctl --user restart framey.service
   ```

手动安装的模块可通过替换或删除该文件更新或卸载，之后重启 Framey。切回 **系统蓝牙** 可暂停专用查询。

## English

This provider supplies left earbud, right earbud, and charging case readings for Xiaomi Air 4 SE. Installation by URL requires Charge Protocol **v0.9.3** or newer. The provider uses SteamOS BlueZ, Python D-Bus, and `sdptool`.

### Install by URL in the headset

1. Install or update the [main Charge Protocol plugin](../../README.md#english) and connect your Air 4 SE.
2. In **Framey → Settings**, paste the following URL and select **Install**.

   ```text
   https://github.com/SgZincanya/SteamFrame-ChargeProtocol/releases/download/v0.9.3/Air4-SE-Provider-v1.1.0.zip
   ```

3. Open **Charging Protocol → Bluetooth Battery Source** and select `air4-se`. To check the case battery, put the earbuds in the case and open the lid. The panel shows the age of cached readings when there is no fresh report.

Paste the new module ZIP URL to update. You can disable or remove **Air 4 SE Battery Provider** in the same Settings page. If you also installed the provider manually, the main plugin can still find the manual copy after removal.

### Build

Download or clone this repository and run the following from its root with Python 3.9 or newer. It creates `dist/Air4-SE-Provider-v1.1.0.zip`.

```sh
python3 scripts/build_zip.py --air4-se
```

### Manual installation

Manual installation works with Charge Protocol v0.9.1 or newer. Extract the ZIP on the headset, run these commands from the extracted directory, then select `air4-se` under **Bluetooth Battery Source**.

   ```sh
   mkdir -p ~/.config/framey/frame-charge-protocol-providers
   cp air4-se.py ~/.config/framey/frame-charge-protocol-providers/
   systemctl --user restart framey.service
   ```

To update or uninstall a manually installed provider, replace or delete the file and restart Framey. Select **System Bluetooth** to pause provider queries.

## 授权与参考 · License and reference

MIT. The provider implements read-only battery requests and notifications. [XiaomiTWS protocol reference](https://github.com/web1n/android_packages_apps_XiaomiTWS)
