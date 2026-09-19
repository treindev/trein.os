# Research: HP ZBook Studio x360 G5 Sensor Integration & Niri Display Auto-Rotation

- **Status**: Completed
- **Date**: 2026-09-19
- **Author**: Antigravity Research Subagent
- **Issue Reference**: Resolves [#25](https://github.com/treindev/trein.os/issues/25), Part of [#20](https://github.com/treindev/trein.os/issues/20)

---

## 1. Executive Summary

This research investigates the hardware topology, kernel subsystems, Wayland compositor mechanics, and user-space daemons required to achieve battery-efficient automatic screen rotation, tablet mode detection, and physical input inhibition for the **HP ZBook Studio x360 G5** convertible workstation under the **Niri** scrollable-tiling Wayland compositor.

### Primary Recommendations
1. **Host Image Layer (`recipes/base/common.yml`)**: Package and enable `iio-sensor-proxy`. Ensure `iio-sensor-proxy.service` is enabled to provide the standard system D-Bus interface `net.hadess.SensorProxy`.
2. **Sensor Routing**: The system contains two accelerometer components. The older `ST LIS3LV02DL` (`hp_accel` / `lis3lv02d`) is mounted in the **base** chassis (for HDD drop protection) and tagged as `ACCEL_LOCATION=base` in systemd hwdb. The display orientation must be driven by the **Intel Integrated Sensor Hub (ISH)** 3D accelerometer (`iio:device1`, `HID-SENSOR-200073`), which is mounted in the screen lid.
3. **Orientation Daemon**: Deploy **`iio-niri`** as a systemd user service (`iio-niri.service`). Unlike polling daemons like `rot8` (which drain battery and rely on `wlr-output-management`), `iio-niri` is purely event-driven over D-Bus, communicates directly with Niri's IPC socket via the native Rust `niri-ipc` library, and dynamically commands `niri msg output eDP-1 transform <normal|90|180|270>`.
4. **Touch & Pen Mapping**: Configure `input { touch { map-to-output "eDP-1"; } tablet { map-to-output "eDP-1"; } }` in Chezmoi's `input.kdl`. In Niri (via Smithay), rotating an output automatically rotates the normalized coordinate transformation matrix of all mapped touchscreens and stylus digitizers without needing manual matrix manipulation.
5. **Tablet Mode Inhibition**: Leverage `libinput`'s built-in `LIBINPUT_SWITCH_TABLET_MODE` handling. When `SW_TABLET_MODE` is triggered (via `intel-hid` / `hp-wmi`), `libinput` automatically disables the internal keyboard and touchpad while preserving external USB/Bluetooth inputs. Niri's `switch-events { tablet-mode-on { ... } }` provides the hook to launch on-screen keyboards (such as `sysboard` or DMS virtual keyboard). Direct kernel sysfs inhibition (`/sys/class/input/input[N]/inhibited`) provides a reliable hardware fallback if ACPI firmware events drop.

---

## 2. Hardware Inventory & Kernel Subsystem Topology

Hardware interrogation on the live HP ZBook Studio x360 G5 platform (`Linux 7.2.5-200.fc44.x86_64`) reveals the following device configuration:

| Subsystem / Device | Kernel Driver & Bus | Sysfs / Evdev Node | Capabilities / Role |
| :--- | :--- | :--- | :--- |
| **Internal Display** | `i915` / `nvidia` DRM | Output `eDP-1` | 1920x1080 @ 60 Hz internal panel |
| **Lid Accelerometer** | `hid-sensor-accel-3d` via Intel ISH (PCI `00:13.0`) | `/sys/bus/iio/devices/iio:device1` (`HID-SENSOR-200073`) | Primary 3D display orientation sensor (`in_accel_{x,y,z}_raw`) |
| **Base Accelerometer** | `hp_accel` / `lis3lv02d` (ACPI) | `/devices/faux/lis3lv02d/input/input44` (`event25`) | Chassis-mounted drop-sensor (`ACCEL_LOCATION=base`) |
| **Multi-touch Digitizer** | `wacom` / `i2c-designware` (ACPI `WCOM48A0:00`) | `/dev/input/event10` (`input26`: Wacom HID 48D8 Finger) | Direct capacitive touchscreen (`ID_INPUT_TOUCHSCREEN=1`) |
| **Stylus Digitizer** | `wacom` / `i2c-designware` (ACPI `WCOM48A0:00`) | `/dev/input/event9` (`input25`: Wacom HID 48D8 Pen) | Direct EMR stylus pen with pressure/tilt (`ID_INPUT_TABLET=1`) |
| **Internal Keyboard** | `atkbd` / `i8042` | `/dev/input/event4` (`input4`: AT Translated Set 2 keyboard) | Physical laptop keyboard (`ID_INPUT_KEYBOARD=1`) |
| **Internal Touchpad** | `synaptics_i2c` / `i2c-designware` | `/dev/input/event8` (`input23`: SYNA307B:00 06CB:CD46 Touchpad) | Multi-touch clickpad (`ID_INPUT_TOUCHPAD=1`) |
| **Hinge / Tablet Switch** | `intel-hid` (ACPI `INT33D5:00`) & `hp-wmi` | `/dev/input/event257` (`input52`: HP WMI hotkeys), `event24` (`input43`) | Reports `SW_TABLET_MODE` (`0x01`) and `SW_DOCK` (`0x05`) |
| **Lid Switch** | `button` / ACPI `PNP0C0D:00` | `/dev/input/event1` (`input1`: Lid Switch) | Reports `SW_LID` (`0x00`) |

### Dual Accelerometer Distinction & Hwdb
A frequent pitfall on HP convertibles is confusion between the **HDD protection accelerometer** and the **display orientation accelerometer**:
- In `/usr/lib/udev/hwdb.d/60-sensor.hwdb`:
  ```ini
  sensor:modalias:platform:lis3lv02d:dmi:*:svnHewlett-Packard:*
  sensor:modalias:platform:lis3lv02d:dmi:*:svnHP:*
   ACCEL_LOCATION=base
  ```
  The ST LIS3LV02DL accelerometer is physically located in the bottom casing to detect free-fall of rotating hard drives.
- The Intel ISH (`hid-sensor-accel-3d`) exposes `/sys/bus/iio/devices/iio:device1` through the kernel Industrial I/O (IIO) subsystem. This sensor is located in the display lid.
- `iio-sensor-proxy` parses `ACCEL_LOCATION` from udev properties. Because `lis3lv02d` is marked as `base`, `iio-sensor-proxy` ignores it for display orientation and selects the display-mounted IIO device.

---

## 3. Accelerometer Integration: `iio-sensor-proxy`

### D-Bus Interface Architecture
`iio-sensor-proxy` provides a unified system D-Bus service at `net.hadess.SensorProxy` (`/net/hadess/SensorProxy`):
- **Claim-Driven Power Management**:
  - `net.hadess.SensorProxy.ClaimAccelerometer()`
  - `net.hadess.SensorProxy.ReleaseAccelerometer()`
  - Sensors are **only polled/active when at least one client has claimed them**. When no clients are active (e.g., clamshell docked mode with lid closed), the kernel IIO buffer/sampling remains stopped, preventing timer wakeups and maximizing battery life.
- **Signals and Properties**:
  - `HasAccelerometer` (`b`): Indicates hardware accelerometer presence.
  - `AccelerometerOrientation` (`s`): One of `"undefined"`, `"normal"`, `"bottom-up"`, `"left-up"`, `"right-up"`.
  - Emits `org.freedesktop.DBus.Properties.PropertiesChanged` signals whenever orientation changes across threshold hystereses.

### Current Gap in trein.os
`iio-sensor-proxy` is currently not installed on the host image (`Unit iio-sensor-proxy.service could not be found`). It must be added to the declarative package list in `recipes/base/common.yml`.

---

## 4. Evaluation of Wayland & Niri Orientation Daemons

| Candidate Daemon | Protocol / IPC Mechanism | Sensor Source | Idle Battery Impact | Assessment for trein.os |
| :--- | :--- | :--- | :--- | :--- |
| **`rot8`** | `wlr-output-management-unstable-v1` / `swaymsg` | Polls sysfs files (`in_accel_*_raw`) in a loop | **Severe** (continuous CPU wakeups every 100-500ms) | **Incompatible & Rejected**: Niri is built on Smithay, not `wlroots`, and does not support `wlr_output_management`. Constant sysfs polling ruins battery life. |
| **`iio-niri`** (Zhaith-Izaliel) | Native Niri IPC socket (`niri-ipc` Rust crate) | Event-driven D-Bus (`net.hadess.SensorProxy`) | **Zero wakeups** (completely sleeping until D-Bus signal fires) | **Recommended Primary**: Engineered specifically for Niri. Connects to `$NIRI_SOCKET`, translates orientation, supports manual rotation lock, and issues instant atomic output transformations. |
| **Custom Python D-Bus Script** | `niri msg output <name> transform` via subprocess | Event-driven D-Bus (`pydbus` / `Gio.DBusProxy`) | **Negligible** | **Viable Fallback**: Useful if avoiding an extra compiled binary, but lacks `iio-niri`'s Unix socket lock management and IPC integration. |
| **DMS (Dank Material Shell)** | Internal QuickShell / Go IPC | No native accelerometer daemon | N/A | **Shell Integration**: DMS handles OSDs, quicksettings toggles, and panel layouts, but does not provide an automated sensor orientation daemon. DMS should be used for the UI toggle button. |

### Orientation Mapping Table
Niri output transforms are specified in degrees **counter-clockwise**:

| `iio-sensor-proxy` Orientation | Physical Device Position | Niri Output Transform (`niri msg output eDP-1 transform <val>`) |
| :--- | :--- | :--- |
| `normal` | Standard laptop orientation | `normal` |
| `bottom-up` | Upside-down (flipped 180°) | `180` |
| `left-up` | Rotated 90° clockwise (portrait, ports down) | `270` |
| `right-up` | Rotated 90° counter-clockwise (portrait, ports up)| `90` |

---

## 5. Coordinate Transformation & Touch/Pen Mapping

### Problem Statement
On convertible touchscreen devices, rotating the display raster must automatically update the touch digitizer and active stylus mapping. If the coordinate transformation matrix is not updated, touching the top-left of the physical screen will register on the wrong quadrant of the compositor's canvas.

### Niri Architectural Solution
In Niri, absolute pointing devices are bound to displays declaratively in the user dotfiles (`~/.config/niri/input.kdl`):

```kdl
input {
    touch {
        map-to-output "eDP-1"
    }

    tablet {
        map-to-output "eDP-1"
    }
}
```

### Coordinate Space Transformation Mechanics
1. **Normalized Input Space**: Both the Wacom HID 48D8 touchscreen (`input26`) and pen stylus (`input25`) report coordinates normalized to the unit square `[0.0, 1.0]`.
2. **Smithay Output Transformation**: Because `touch` and `tablet` are mapped to output `eDP-1`, Niri's input pipeline projects the unit coordinates into `eDP-1`'s logical geometry.
3. **Automatic Transform Rotation**: When `niri msg output eDP-1 transform 270` is executed, Niri transforms the display raster and **automatically rotates the coordinate projection matrix for all mapped touch and tablet devices**.
4. **No Static Calibration Required**: The Wacom digitizer hardware on the HP ZBook Studio x360 G5 is aligned 1:1 with the LCD panel matrix. No `calibration-matrix` or udev `LIBINPUT_CALIBRATION_MATRIX` adjustments are required for standard operation.

---

## 6. Tablet Mode Hinge Detection & Physical Input Inhibition

When folding the HP ZBook Studio x360 G5 360 degrees into a tablet, the physical keyboard keys and touchpad must be disabled to prevent spurious accidental keystrokes while holding the chassis.

### Primary Mechanism: `libinput` Native Handling
`libinput` natively implements internal keyboard and touchpad suppression when a tablet mode switch is asserted:
- **Specification**: According to the [official libinput documentation](https://wayland.freedesktop.org/libinput/doc/latest/switches.html#tablet-mode-switch-handling):
  > *"Where available, libinput listens to devices providing a tablet mode switch... The event sent by the kernel is `EV_SW SW_TABLET_MODE` and is provided as `LIBINPUT_SWITCH_TABLET_MODE`. When the device switches to tablet mode, the touchpad and internal keyboard are disabled. If a trackpoint exists, it is disabled too. The input devices are automatically re-enabled whenever tablet mode is disengaged."*
- **Scope**: `libinput` detects internal devices based on `ID_INPUT_KEYBOARD`, `ID_INPUT_TOUCHPAD`, and the bus type (`i8042` / internal `i2c`). External USB/Bluetooth keyboards (such as the Keychron Q6 Max) and external mice remain fully functional.

### Compositor Event Hooks: Niri `switch-events`
Niri provides native syntax in `config.kdl` for reacting to switch transitions:
```kdl
switch-events {
    tablet-mode-on {
        // Automatically spawn an on-screen keyboard when converted to tablet
        spawn "notify-send" "-u" "low" "Tablet Mode" "Internal keyboard inhibited"
    }
    tablet-mode-off {
        spawn "notify-send" "-u" "low" "Laptop Mode" "Internal keyboard enabled"
    }
}
```

### Hardware Verification & Fallback: Kernel Sysfs Input Inhibition
On HP laptops, if ACPI firmware fails to emit `SW_TABLET_MODE` (or `hp-wmi` returns query errors), Linux kernel 5.4+ provides a kernel-level hardware inhibition toggle:
- **Sysfs Node**: `/sys/class/input/input[N]/inhibited`
  - Keyboard: `/sys/class/input/input4/inhibited` (`AT Translated Set 2 keyboard`)
  - Touchpad: `/sys/class/input/input23/inhibited` (`SYNA307B:00 06CB:CD46 Touchpad`)
- **Kernel Behavior**: Writing `1` to `inhibited` immediately calls the driver's `close()` method and drops all hardware events at the input core. Writing `0` restores normal operation.
- **Permissions**: Granting write access to group `input` via udev rule:
  ```udev
  # /etc/udev/rules.d/99-input-inhibit.rules
  SUBSYSTEM=="input", ATTR{name}=="AT Translated Set 2 keyboard", ATTR{inhibited}=="0", GROUP="input", MODE="0664"
  SUBSYSTEM=="input", ATTR{name}=="SYNA307B:00 06CB:CD46 Touchpad", ATTR{inhibited}=="0", GROUP="input", MODE="0664"
  ```
  This allows a user session daemon or orientation script to forcibly inhibit physical inputs if manual or heuristic tablet mode triggers are required.

---

## 7. Actionable Implementation Plan for trein.os

To implement this architecture in accordance with trein.os repository standards:

### 1. Host Image BlueBuild Recipe (`recipes/base/common.yml`)
Add `iio-sensor-proxy` to the declarative package list:
```yaml
  # In recipes/base/common.yml under dnf packages:
  - type: dnf
    install:
      packages:
        - iio-sensor-proxy
```
And enable the systemd service:
```yaml
  - type: systemd
    system:
      enabled:
        - iio-sensor-proxy.service
```

### 2. Auto-Rotation Daemon (`iio-niri`)
Package `iio-niri` (via COPR, cargo build in recipe, or user flatpak/binary) and configure a user systemd service:
`~/.config/systemd/user/iio-niri.service`:
```ini
[Unit]
Description=IIO Niri Auto-Rotation Daemon
PartOf=graphical-session.target
After=graphical-session.target

[Service]
ExecStart=/usr/bin/iio-niri listen --target eDP-1
Restart=on-failure
RestartSec=2s

[Install]
WantedBy=graphical-session.target
```

### 3. User Dotfiles (`~/.config/niri/input.kdl`)
Update the dotfiles repository (managed via Chezmoi) to map tablet and touch inputs directly to `eDP-1`:
```kdl
input {
    keyboard {
        xkb {
        }
        numlock
    }

    touchpad {
        tap
        natural-scroll
    }

    touch {
        map-to-output "eDP-1"
    }

    tablet {
        map-to-output "eDP-1"
    }
}
```

### 4. Niri Switch Events (`~/.config/niri/config.kdl`)
Configure tablet mode notifications and virtual keyboard hooks:
```kdl
switch-events {
    tablet-mode-on {
        spawn "notify-send" "-i" "input-tablet" "Tablet Mode" "Display autorotation active"
    }
    tablet-mode-off {
        spawn "notify-send" "-i" "video-display" "Laptop Mode" "Display locked to normal"
    }
}
```

---

## 8. Primary Sources & Citations

1. **Niri Compositor Documentation**:
   - Outputs Configuration: [Niri Wiki - Configuration: Outputs](https://github.com/niri-wm/niri/wiki/Configuration:-Outputs)
   - Input Device Mapping: [Niri Wiki - Configuration: Input](https://github.com/niri-wm/niri/wiki/Configuration:-Input)
   - Switch Events Specification: [Niri Wiki - Configuration: Switch Events](https://github.com/niri-wm/niri/wiki/Configuration:-Switch-Events)
   - IPC Protocol Specification: [Niri Wiki - IPC](https://github.com/niri-wm/niri/wiki/IPC)
2. **Freedesktop & Libinput Documentation**:
   - Switch Handling Specification: [libinput - Switches: Tablet mode switch handling](https://wayland.freedesktop.org/libinput/doc/latest/switches.html#tablet-mode-switch-handling)
   - Absolute Axes & Tablet Tools: [libinput - Tablet Support](https://wayland.freedesktop.org/libinput/doc/latest/tablet-support.html)
3. **iio-sensor-proxy Documentation**:
   - Sensor Proxy Reference Manual & D-Bus Interface: [iio-sensor-proxy - net.hadess.SensorProxy](https://hadess.pages.freedesktop.org/iio-sensor-proxy/gdbus-net.hadess.SensorProxy.html)
   - Systemd Sensor Hardware Database: [systemd - 60-sensor.hwdb](https://github.com/systemd/systemd/blob/master/hwdb.d/60-sensor.hwdb)
4. **Linux Kernel Documentation & ABI**:
   - Input Subsystem ABI (`inhibited` attribute): [Linux Kernel ABI - sysfs-class-input](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/Documentation/ABI/testing/sysfs-class-input)
   - HP WMI Driver: `drivers/platform/x86/hp/hp-wmi.c`
   - Intel HID Event Driver: `drivers/platform/x86/intel/hid.c`
5. **iio-niri Project**:
   - Source Code & Architecture: [Zhaith-Izaliel/iio-niri](https://github.com/Zhaith-Izaliel/iio-niri)
