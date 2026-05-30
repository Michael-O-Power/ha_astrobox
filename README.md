# AstroBox 3D Printer Integration for Home Assistant
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![Platform-AstroBox](https://img.shields.io/badge/Platform-AstroBox-blue.svg?style=for-the-badge)](https://github.com/AstroPrint/AstroBox)
[![Verified Firmware](https://img.shields.io/badge/Verified%20Firmware-v0.21(3)-success.svg?style=for-the-badge)](https://github.com/AstroPrint/AstroBox)

A comprehensive local custom integration linking **AstroBox** gateways and compatible 3D printers directly into your Home Assistant smart home system.
---
## Overview & Purpose
This custom integration provides local monitoring and automation capabilities for AstroBox deployments without relying on external cloud infrastructure. By targeting local REST API frameworks, it enables real-time telemetry tracking and hardware command controls over a local area network connection.
### Core Features
* **Automated API Key Extraction:** Eliminates the manual process of hunting down hidden security tokens. The config flow requests only the local address, then extracts the internal `UI_API_KEY` straight from the gateway's frontend login script headers.
* **Unified Device Representation:** Maps sensors, binary flags, configuration inputs, control buttons, and selector options under a single consolidated Device Card within the Home Assistant interface.
* **Local Network Flexibility:**
  * **Hostname Addressability:** Supports local mDNS address parsing (e.g., `astrobox.local`) alongside standard fixed IPv4 addresses. Connection processes explicitly handle mDNS routing adjustments to force IPv4 transport mechanisms exclusively, preventing common mDNS IPv6 resolution failures.
  * **Optional MAC Address Network Profile Fusion:** Allows you to input an optional network hardware MAC address. When specified, Home Assistant cross-references this token against network tracking integrations (like UniFi, Omada, or OPNsense) to dynamically merge system connectivity metrics directly into the same printer device card.
* **Resilient Lifecycle Handshakes:** Gracefully catches hardware power-state cycles. If the physical 3D printer is switched off at the wall while the underlying Raspberry Pi or gateway computer remains active, the integration intercepts the resulting HTTP `409 Conflict` errors. This updates entities to an `Offline` or `Unavailable` state cleanly, protecting system logs from traceback exceptions.
---
## Available Integration Entities

| Platform | Entity Name | Functional Description |
| :--- | :--- | :--- |
| **Sensor** | Nozzle Temperature | Active extruder temperature telemetry (`°C`). Keeps target limits visible as an attribute. |
| **Sensor** | Bed Temperature | Print surface bed temperature telemetry (`°C`). Keeps target limits visible as an attribute. |
| **Sensor** | Print Progress | Completion metrics percentage indicator (`%`). Includes file name, byte size, and filament requirements as state attributes. |
| **Sensor** | Printer State | Explicit string representation of current operations (Printing, Operational, Paused, Offline). |
| **Sensor** | Print Time Elapsed | Cumulative active runtime tracker (`seconds`). |
| **Sensor** | Print Time Remaining | Live countdown timer tracking remaining duration until completion (`seconds`). |
| **Sensor** | Print ETA | Static timestamp tracking absolute completion time matching your system timezone clock. |
| **Sensor** | Storage Disk Usage | Tracks host gateway filesystem memory usage thresholds (`%`). |
| **Binary Sensor** | Connection Status | Binary indicator showing gateway communication availability. |
| **Binary Sensor** | Error Status | Dedicated safety tracking node watching internal firmware error signals. |
| **Button** | Connect Printer | Commands the local gateway to open and claim the hardware serial line. |
| **Button** | Disconnect Printer | Safely disconnects the active serial line link. |
| **Button** | Wakeup Nudge | Forwards harmless serial text signals (`M117`, `M105`) to wake stalled microcontrollers. |
| **Button** | System Operations | Advanced controls to power cycle services, reboot the operating system, or execute safe system shutdowns. |
| **Number** | Nozzle / Bed Targets | Dynamic input numbers mapping custom target temperatures onto live hardware heating matrices. |
| **Select** | Preheat Profile | A drop-down selection macro setting material heating presets (`PLA`, `PETG`, `ABS`) to both elements concurrently. |

---
## Installation Procedures
### Method 1: HACS Custom Repository Setup (Recommended)
1. Navigate to your **Home Assistant** instance dashboard.
2. Select **HACS** (Home Assistant Community Store) -> **Integrations**.
3. Click the **Three Dots Menu** located in the top-right corner, then click **Custom repositories**.
4. Input the repository URL into the **Repository** prompt field:
   ```text
   [https://github.com/Michael-O-Power/ha_astrobox](https://github.com/Michael-O-Power/ha_astrobox)
   ```
5. Assign **Integration** as the functional Category, then click **Add**.
6. Select the freshly populated **AstroBox 3D Printer** entry from your list, select **Download**, and fetch the desired version bundle.
7. Restart your **Home Assistant** server to load and register the component directory structure.
### Method 2: Manual Code Deployment
1. Download the target release source package as a structured `.zip` archive.
2. Unzip the code bundle and identify the interior `custom_components/astrobox/` folder directory.
3. Access your Home Assistant runtime directories via secure SFTP, Samba sharing, or the Terminal & SSH add-on.
4. Copy the entire `astrobox` folder path explicitly into your custom components directory:
   ```text
   config/custom_components/astrobox/
   ```
5. Verify structural folder read/write file permissions and execute a full core framework reboot of **Home Assistant**.
---
## Configuration Wizard Steps
Once the integration assets have loaded into your deployment environment, initialize your connection by following these instructions:
1. Navigate to **Settings** -> **Devices & Services** -> **Integrations**.
2. Click the floating **+ Add Integration** button in the lower-right corner.
3. Search for **AstroBox 3D Printer** and select it to initialize the setup block.
4. Complete the input validation options:
   * **Host:** Supply either the static IP network allocation address or the local mDNS hostname string (e.g., `192.168.68.58` or `cocooncreate.local`).
   * **MAC Address (Optional):** Input the network interface hardware MAC address matching your box platform (e.g., `AA:BB:CC:DD:EE:FF`). This allows Home Assistant to automatically group and align your printer with existing network profiles tracking client status.
5. Click **Submit**.
The integration will access the target host web template, extract the active authentication token automatically, check core system characteristics against your firmware parameters (`v0.21(3)` baseline architectures), and generate your dashboard controller card.
```
