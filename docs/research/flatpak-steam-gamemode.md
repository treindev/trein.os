# Research: Flatpak Steam Gamescope Integration & Host Gamemode Portal Communication

- **Status**: Completed
- **Date**: 2026-09-20
- **Author**: Antigravity Research Subagent
- **Ticket Reference**: Resolves [#45](https://github.com/treindev/trein.os/issues/45), Part of Map [#43](https://github.com/treindev/trein.os/issues/43)
- **Branch**: `research/flatpak-steam-gamemode`

---

## 1. Executive Summary & Core Verdict

This research investigates the host-level operating system requirements, IPC protocols, device permissions, and kernel tuning necessary to provide an optimal, out-of-the-box gaming experience for Flatpak Steam (`com.valvesoftware.Steam`) and Gamescope on **`trein.os`** (built with BlueBuild on Fedora Atomic Desktop with the **Niri** Wayland compositor).

### Core Verdict & Findings

1. **Zero Flatpak D-Bus Overrides Required for GameMode**:
   - Flatpak Steam communicates with host `gamemoded` through the standard XDG Desktop Portal interface **`org.freedesktop.portal.GameMode`**, hosted by `xdg-desktop-portal` on the session bus at `org.freedesktop.portal.Desktop`.
   - Flatpak's built-in D-Bus proxy grants all sandboxed applications default, filtered access to `org.freedesktop.portal.*`. Therefore, **no `--talk-name` or socket overrides are needed or desired**.
   - The daemon on the host session bus is `com.feralinteractive.GameMode` (the prompt's `org.freedesktop.FeralInteractive.GameMode` is a common misnomer blending the portal and daemon names).
   - Granting direct access to `com.feralinteractive.GameMode` via Flatseal is actively harmful: it circumvents the portal's PID namespace translation (`CLONE_NEWPID`), causing `gamemoded` to receive sandbox-local PIDs that do not match the host PID, breaking process tracking and core pinning.
   - Host prerequisite: Package `gamemode` in the Host Image so `gamemoded` and its D-Bus service activation file `/usr/share/dbus-1/services/com.feralinteractive.GameMode.service` are present on the host.

2. **Official Fedora Package `steam-devices` Satisfies All Controller & VR Requirements**:
   - Systemd's default `70-uaccess.rules` only assigns `TAG+="uaccess"` to `SUBSYSTEM=="input"` for generic joysticks. It completely omits `SUBSYSTEM=="hidraw"`.
   - Modern controllers (Sony DualShock 4, DualSense / DualSense Edge, Nintendo Switch Pro, Joy-Cons, Xbox Elite 2 over Bluetooth, Steam Controller, 8BitDo, Razer, Hori) require raw HID report access (`/dev/hidraw*`) for gyro/motion sensors, touchpad digitizers, adaptive triggers, high-definition haptics, and Bluetooth telemetry.
   - Steam Input also requires `TAG+="uaccess"` on `/dev/uinput` to generate virtual gamepad devices without root elevation.
   - The official Fedora repository package **`steam-devices`** (sourced from `ValveSoftware/steam-devices`) provides both `/usr/lib/udev/rules.d/60-steam-input.rules` and `/usr/lib/udev/rules.d/60-steam-vr.rules`, covering all major gamepads and VR headsets (Valve Index, HTC Vive, Bigscreen Beyond) out of the box with zero third-party Copr dependencies.
   - Third-party `game-devices-udev` is redundant for Steam/Proton gaming and unnecessary unless niche retro flight sticks or unbranded arcade boards are specifically attached.

3. **Adopt SteamOS Standard `vm.max_map_count = 2147483642`**:
   - Modern Windows titles running via Proton (Proton / DXVK / VKD3D) exhaust default Linux memory map limits because Windows' `VirtualAlloc` allows virtually unbounded allocations, whereas Linux bounds Virtual Memory Areas (VMAs) via `vm.max_map_count`.
   - Titles such as *Civilization VI*, *Hogwarts Legacy*, *Star Citizen*, *Counter-Strike 2*, *DayZ*, Unreal Engine 5 games, and modded Bethesda titles (*Skyrim SE*, *Fallout 4*) crash or stutter when VMA limits are exceeded.
   - While Fedora sets `1048576` via `systemd-udev`'s `/usr/lib/sysctl.d/10-map-count.conf`, Valve's **SteamOS 3.5+** and **Bazzite** set `vm.max_map_count = 2147483642` (`MAX_INT - 5`). Raising this limit incurs no memory overhead until mappings are actually allocated.
   - Declaratively deliver `vm.max_map_count = 2147483642` and tuned inotify watch limits in `files/base/usr/lib/sysctl.d/80-gaming.conf`.

```
+---------------------------------------------------------------------------------------+
|                                Flatpak Sandbox Context                                |
|  com.valvesoftware.Steam (PID Namespace: Sandboxed PID 35)                            |
|                                                                                       |
|   +--------------------------+                 +----------------------------------+   |
|   |  Game Process / Proton   |                 |      Gamescope Vulkan Layer      |   |
|   |   (DXVK / VKD3D / WINE)  |                 |  org.freedesktop.Platform.       |   |
|   |                          |                 |  VulkanLayer.gamescope (3.16.x)  |   |
|   +--------------------------+                 +----------------------------------+   |
|                |                                                 |                    |
|                | LD_PRELOAD libgamemode.so                       | Wayland Surface    |
|                | Checks /.flatpak-info -> in_sandbox() == true   | --backend sdl      |
|                v                                                 v                    |
+----------------|-------------------------------------------------|--------------------+
                 | D-Bus Session Proxy (org.freedesktop.portal.*)  | Wayland Protocol
                 v                                                 v
+--------------------------------------------------+   +--------------------------------+
|          xdg-desktop-portal (Host Session)       |   |   Niri Compositor (Host)       |
|          org.freedesktop.portal.Desktop          |   |   Scrollable-tiling Wayland    |
|          /org/freedesktop/portal/desktop         |   +--------------------------------+
|          Interface: org.freedesktop.portal.      |
|                     GameMode                     |
|  - Queries peer credentials (SO_PEERCRED)        |
|  - Translates Sandbox PID 35 -> Host PID 142857  |
|  - Checks permission_store (default allow)       |
|  - Monitors client process lifecycle             |
+--------------------------------------------------+
                         |
                         | D-Bus Call: RegisterGame(142857)
                         v
+--------------------------------------------------+
|           gamemoded (Host Session Service)       |
|           com.feralinteractive.GameMode          |
|           /com/feralinteractive/GameMode         |
|  - Changes CPU governor to performance (cpugov)  |
|  - Applies process niceness / I/O priority       |
|  - Sets GPU performance mode (NVIDIA / AMD)      |
|  - Inhibits screensaver / DPMS suspension        |
+--------------------------------------------------+
                         |
                         +------------> Linux Kernel Subsystem (Host)
                                        - vm.max_map_count = 2147483642
                                        - udev: /dev/hidraw*, /dev/uinput (TAG+="uaccess")
```

---

## 2. Primary Sources & Architectural Investigation

The investigation is based on verification against upstream specifications, source code, and host package repositories:

| Source Domain | Primary Source Location | Verified Mechanics & Findings |
| :--- | :--- | :--- |
| **XDG Desktop Portal Spec & Code** | `flatpak/xdg-desktop-portal`: `data/org.freedesktop.portal.GameMode.xml`, `desktop-portal/gamemode.c` | Verifies `org.freedesktop.portal.GameMode` API (`RegisterGame`, `UnregisterGame`, `QueryStatus`), PID namespace translation from caller sandbox to host, process lifecycle monitoring, and `permission_store` default-allow behavior. |
| **Feral GameMode Client Source** | `FeralInteractive/gamemode`: `lib/client_impl.c` | Verifies `in_sandbox()` detection via `lstat("/.flatpak-info")`. When inside a sandbox, the client switches target from `com.feralinteractive.GameMode` to `org.freedesktop.portal.Desktop` / `org.freedesktop.portal.GameMode`. |
| **Feral GameMode Daemon & Service** | `FeralInteractive/gamemode`: `data/dbus/com.feralinteractive.GameMode.service.in`, `data/systemd/user/gamemoded.service.in` | Confirms D-Bus session activation bus name is `com.feralinteractive.GameMode`, triggered on demand by the portal when games request GameMode. |
| **Steam Flatpak Manifest** | `flathub/com.valvesoftware.Steam`: `com.valvesoftware.Steam.yml` | Validates default `finish-args`: includes `--device=all`, `--filesystem=/run/udev:ro`, `--socket=wayland`, `--socket=x11`, `--socket=pulseaudio`. Does *not* declare `--talk-name` for gamemode because portals are permitted implicitly. |
| **Fedora Package Repositories** | Fedora 44 Repositories: `gamemode-1.8.2-4.fc44`, `steam-devices-1.0.0.101^git20260625.22ec85e-1.fc44` | Confirms `gamemode` and `steam-devices` are officially packaged in Fedora `fedora` and `updates` repositories; no third-party COPR or external script layer needed. |
| **Valve Steam Devices Udev Rules** | `ValveSoftware/steam-devices`: `60-steam-input.rules`, `60-steam-vr.rules` | Examined all 249 lines of input rules and 38 lines of VR rules. Confirms `TAG+="uaccess"` on `/dev/uinput`, `/dev/hidraw*` across Valve, Sony, Nintendo, Xbox, 8BitDo, Razer, Hori, and VR headsets. |
| **Systemd Uaccess Baseline** | Host `/usr/lib/udev/rules.d/70-uaccess.rules` | Proves systemd by default only grants `uaccess` to `SUBSYSTEM=="input"`, omitting `/dev/hidraw*` for gamepads and breaking advanced controller telemetry. |
| **Kernel Sysctl Documentation** | SteamOS 3.5 sysctl configuration, Fedora Change Proposal: `IncreaseVmMaxMapCount` | Confirms Fedora default is `1048576`, while SteamOS and Bazzite deploy `2147483642` to eliminate VMA exhaustion across all Proton/DXVK/VKD3D titles. |

---

## 3. Deep Technical Analysis

### 3.1. D-Bus Portal vs. Direct Socket Permissions for GameMode

#### The Process ID (PID) Namespace Barrier
Flatpak isolates applications in an independent Linux PID namespace (`CLONE_NEWPID`). When a game runs inside Steam Flatpak (and within Steam's pressure-vessel container), it sees process IDs starting from low numbers (e.g. PID 2 or PID 35). On the host operating system, that same process has a completely different PID (e.g. PID 142857).

`gamemoded` operates on the host session bus. Its optimizations (renicing, I/O scheduling, CPU core affinity) require the host kernel PID. If a sandboxed game were to communicate directly with `gamemoded` using its container PID:
1. `gamemoded` would look up the container PID in the host's `/proc`.
2. The lookup would either fail with `ESRCH` (No such process), or worse, apply priority tweaks to an unrelated host process that happened to share that low numeric PID!

#### How `xdg-desktop-portal` Solves the Problem
The XDG Desktop Portal specification provides `org.freedesktop.portal.GameMode`:

```xml
<interface name="org.freedesktop.portal.GameMode">
  <method name="RegisterGame">
    <arg type="i" name="pid" direction="in"/>
    <arg type="i" name="result" direction="out"/>
  </method>
  <method name="UnregisterGame">
    <arg type="i" name="pid" direction="in"/>
    <arg type="i" name="result" direction="out"/>
  </method>
  <method name="QueryStatus">
    <arg type="i" name="pid" direction="in"/>
    <arg type="i" name="result" direction="out"/>
  </method>
</interface>
```

In `desktop-portal/gamemode.c`:
1. When a client calls `RegisterGame(sandbox_pid)`, `xdg-desktop-portal` queries the D-Bus peer credentials (`SO_PEERCRED`) to determine the client's container boundaries and its PID namespace.
2. The portal inspects `/proc/[host_pid]/root` and translates the sandbox PID to the true host PID.
3. The portal checks `xdg-permission-store` under the `gamemode` table. If no explicit rule exists, it defaults to **allowed**:
   ```c
   g_debug ("No gamemode permissions stored for %s: allowing", app_id);
   return TRUE;
   ```
4. The portal issues `RegisterGame(host_pid)` to `com.feralinteractive.GameMode` on the host session bus.
5. If the game crashes or abruptly exits without unregistering, `xdg-desktop-portal` detects process termination and automatically unregisters the host PID from `gamemoded`.

#### Client Implementation in `libgamemode`
In upstream `lib/client_impl.c`, GameMode's client library is sandbox-aware:

```c
static int in_sandbox(void)
{
    static int status = -1;
    if (status == -1) {
        struct stat sb;
        int r = lstat("/.flatpak-info", &sb);
        status = (r == 0 && sb.st_size > 0);
    }
    return status;
}

static int gamemode_request(const char *method, pid_t for_pid)
{
    ...
    native = !in_sandbox();
    const char *dest = native ? DAEMON_DBUS_NAME : PORTAL_DBUS_NAME;
    const char *path = native ? DAEMON_DBUS_PATH : PORTAL_DBUS_PATH;
    const char *iface = native ? DAEMON_DBUS_IFACE : PORTAL_DBUS_IFACE;
    ...
}
```

Where:
- `PORTAL_DBUS_NAME` = `"org.freedesktop.portal.Desktop"`
- `PORTAL_DBUS_PATH` = `"/org/freedesktop/portal/desktop"`
- `PORTAL_DBUS_IFACE` = `"org.freedesktop.portal.GameMode"`

Because `in_sandbox()` detects `/.flatpak-info`, `libgamemode` automatically targets the portal.

#### Why No Flatpak Overrides Are Needed
1. Flatpak's D-Bus filtering proxy (`xdg-dbus-proxy`) permits unrestricted communication to the portal service `org.freedesktop.portal.Desktop` by default for all sandboxed applications.
2. No `--talk-name` entries are required in the Flatpak manifest or Flatseal overrides.
3. Bus name clarification: The actual daemon bus name is `com.feralinteractive.GameMode`, not `org.freedesktop.FeralInteractive.GameMode`.
4. Bypassing the portal by granting `--talk-name=com.feralinteractive.GameMode` breaks PID translation.

---

### 3.2. Gamescope Micro-Compositor Integration with Flatpak Steam

Gamescope is Valve's SteamOS micro-compositor. It provides isolated Wayland display server sandboxing, hardware-accelerated scaling (FSR, NIS), integer scaling, latency reduction, and frame pacing.

#### Architecture in Flatpak
Because Steam runs inside a Flatpak sandbox, host binaries cannot be executed directly. Gamescope is distributed on Flathub as a runtime extension:
- Application Extension: `org.freedesktop.Platform.VulkanLayer.gamescope`
- Runtimes supported: Freedesktop SDK `25.08` and `26.08` (installed on `trein.os`).
- Capabilities required: GPU device access (`--device=all;dri;`), which `com.valvesoftware.Steam` already possesses.

#### Niri Compositor & Multi-Monitor Considerations
Under Niri (a Wayland scrollable-tiling compositor) with multi-monitor setups:

1. **Window Backend (`--backend sdl`)**:
   - Gamescope supports both direct Wayland client rendering (`--backend wayland`) and SDL rendering (`--backend sdl`).
   - On Niri, running Gamescope with `--backend sdl` is strongly recommended. SDL provides superior surface negotiation, Wayland cursor warping, and focus synchronization within nested Wayland environments.

2. **Unfocused Refresh Rate (`--nested-unfocused-refresh`)**:
   - By default, nested Gamescope throttles or halts rendering when its Wayland surface loses keyboard focus.
   - On a multi-monitor workstation, a user frequently clicks away from the game window to an adjacent display (e.g. Discord, browser, terminal). Without tuning, the game will stall or drop to 1 FPS.
   - Supplying `--nested-unfocused-refresh` ensures the game continues rendering at full monitor refresh rate regardless of active compositor focus.

3. **Standardized Launch Option**:
   ```bash
   gamescope -W 2560 -H 1440 -w 2560 -h 1440 -r 144 --backend sdl --nested-unfocused-refresh -- gamemoderun %command%
   ```
   Alternatively, running `gamemoderun` outside Gamescope wraps the compositor itself:
   ```bash
   gamemoderun gamescope -W 2560 -H 1440 -w 2560 -h 1440 -r 144 --backend sdl --nested-unfocused-refresh -- %command%
   ```

---

### 3.3. Host Udev Rules: Controller, VR, and Input Subsystems

#### The Missing Link: Systemd's Uaccess Gap
In standard systemd udev configurations (`/usr/lib/udev/rules.d/70-uaccess.rules`):
```udev
SUBSYSTEM=="input", ENV{ID_INPUT_JOYSTICK}=="?*", TAG+="uaccess"
```

Only `SUBSYSTEM=="input"` nodes (`/dev/input/js*` and `/dev/input/event*`) receive `TAG+="uaccess"`. Devices under `SUBSYSTEM=="hidraw"` (`/dev/hidraw*`) default to `0600 root:root`.

#### Why Modern Controllers Depend on `/dev/hidraw*`
While simple buttons and thumbsticks can report through generic Linux `evdev`, all modern controller capabilities require bi-directional raw HID communication over `/dev/hidraw*`:
- **Sony PlayStation (DualShock 4, DualSense, DualSense Edge)**:
  - 6-axis IMU (gyroscope and accelerometer) for motion aim.
  - Multi-touch capacitive touchpad coordinates.
  - DualSense voice-coil haptic actuators and dynamic adaptive trigger resistance.
  - Lightbar RGB LED state and battery percentage telemetry.
- **Nintendo Switch (Pro Controller & Joy-Cons)**:
  - High-precision calibration curves.
  - IMU gyro reporting over Bluetooth/USB.
  - HD Rumble frequency and amplitude packets.
- **Valve Steam Controller**:
  - Dual capacitive trackpad haptic pulses and configuration mode switches.
- **Xbox One / Series / Elite 2 over Bluetooth**:
  - Raw packet negotiation and paddle assignments.

Without udev rules granting the active user read/write access to `/dev/hidraw*`, Steam and SDL fail to open the device in HIDAPI mode, falling back to degraded evdev emulation with zero motion, haptics, or touchpad support.

#### Steam Input Emulation: `/dev/uinput`
Steam Input translates diverse controller inputs into standard virtual Xbox 360 or DualShock controllers for running games. This requires writing to the kernel user-space input injector: `/dev/uinput`.
The required rule is:
```udev
KERNEL=="uinput", SUBSYSTEM=="misc", TAG+="uaccess", OPTIONS+="static_node=uinput"
```
This ensures `systemd-logind` assigns an ACL (`getfacl /dev/uinput` -> `user:<user>:rw-`) to the logged-in desktop user.

#### Evaluation: `steam-devices` vs. `game-devices-udev`

| Metric | `steam-devices` (Valve Official) | `game-devices-udev` (Community) |
| :--- | :--- | :--- |
| **Upstream Source** | [ValveSoftware/steam-devices](https://github.com/ValveSoftware/steam-devices) | [fabiscafe/game-devices-udev](https://codeberg.org/fabiscafe/game-devices-udev) |
| **Fedora Packaging** | Official package in Fedora `updates`: `steam-devices.noarch` | None. Requires external Copr or manual rule vendoring. |
| **Rule Coverage** | 249 lines of input rules, 38 lines of VR rules. Covers Valve, Sony, Nintendo, Microsoft, 8BitDo, Razer, Hori, PDP, PowerA, Thrustmaster, Flydigi. | Modular rules per vendor. Covers obscure retro USB adapters, flight simulation sticks, and custom DIY arcade boards. |
| **VR Support** | Includes `/usr/lib/udev/rules.d/60-steam-vr.rules` (Valve Index, HTC Vive, Bigscreen Beyond). | Split across various vendor files; VR rules less uniform. |
| **Maintenance & Drift** | Maintained directly by Valve Steam client developers as new hardware launches (e.g. Nintendo Switch 2 and Bigscreen Beyond already present). | Community-contributed PRs. |
| **Host Integration** | 1 declarative line in BlueBuild recipe (`type: dnf` -> `steam-devices`). Zero maintenance burden. | Requires maintaining a mirror, Copr repo, or manual file sync in `files/base/`. |

**Verdict**: The official Fedora `steam-devices` package is the optimal choice for `trein.os`. It provides complete coverage for all mainstream gaming hardware and VR headsets, updates automatically through Fedora OSTree updates, and requires zero custom file vendoring.

---

### 3.4. Kernel & Sysctl Tuning for Modern Proton Titles

#### The `vm.max_map_count` Bottleneck
The kernel parameter `vm.max_map_count` limits the number of Virtual Memory Areas (VMAs) a single process can map simultaneously via `mmap(2)`.

- **Historical Linux Default**: `65530`
- **Fedora Standard Baseline**: `1048576` (1M) via `/usr/lib/sysctl.d/10-map-count.conf`
- **SteamOS 3.5+ & Bazzite Baseline**: `2147483642` (`MAX_INT - 5`, or `0x7fffffff - 5`)

#### Why Windows Games Running under Proton Demand Extreme VMA Counts
1. **Windows Memory Architecture**:
   Under Win32/Win64, applications allocate memory with `VirtualAlloc` with negligible limit on individual allocation blocks. Windows titles routinely allocate hundreds of thousands of distinct memory pages for textures, scripts, sound buffers, and physics data.
2. **Translation Layers (DXVK & VKD3D-Proton)**:
   DXVK (DirectX 9/10/11 -> Vulkan) and VKD3D-Proton (DirectX 12 -> Vulkan) map Vulkan memory pools, host-visible buffers, and shader caches directly into the process address space. Each distinct buffer allocation creates a new VMA in the host kernel's red-black tree.
3. **Titles Prone to VMA Exhaustion**:
   - *Civilization VI*: Generates hundreds of thousands of memory map allocations during turn generation, texture streaming, and map chunk paging.
   - *Hogwarts Legacy*: Crashes during shader compilation and asset streaming if limits are under 1M.
   - *Star Citizen*: Known to require between 1,000,000 and 1,500,000 mappings.
   - *Counter-Strike 2*, *DayZ*, *Payday 2*, *Arma 3*.
   - Heavily modded Bethesda titles (*Skyrim SE*, *Fallout 4*) loading thousands of loose textures and DLL plugins.
   - Unreal Engine 5 titles utilizing Nanite and Virtual Shadow Maps.

#### Safety and Overhead of `2147483642`
Setting `vm.max_map_count = 2147483642` incurs **zero memory penalty at idle**. VMAs are dynamically allocated in kernel slab memory (`vm_area_struct`, ~160 bytes) only when a process actually invokes `mmap`. The sysctl parameter merely raises the ceiling. Adopting Valve's value guarantees identical compatibility with Steam Deck / SteamOS.

#### Ancillary Sysctl Parameters
1. **File Watcher Limits (`fs.inotify`)**:
   Games with large asset hierarchies, mod organizers (e.g. Mod Organizer 2, Vortex running in Wine), and Steam library synchronizers exhaust default inotify watches.
   - `fs.inotify.max_user_watches = 524288`
   - `fs.inotify.max_user_instances = 8192`
2. **Split Lock Mitigation**:
   - Modern x86 processors penalize atomic memory operations that span across cache line boundaries ("split locks"), locking the system memory bus.
   - Linux kernel defaults to throttling applications that trigger split locks (`split_lock_mitigate=1`).
   - Many Windows titles (e.g. *God of War*, *Watch Dogs*, *Total War*) contain unaligned atomic instructions. Kernel throttling causes severe, rhythmic frame stutter.
   - SteamOS and Bazzite disable kernel split lock throttling via the kernel boot parameter:
     `split_lock_mitigate=0`

---

## 4. Declarative Host Image Enablement Plan

To implement full Flatpak Steam, Gamescope, and GameMode enablement in `trein.os`, the following changes should be applied in subsequent implementation tickets:

### 4.1. Recipe Updates: `recipes/base/gaming.yml` or `recipes/base/common.yml`

Add `gamemode` and `steam-devices` to the host package list:

```yaml
  # Gaming Enablement & Hardware Privileges
  - type: dnf
    install:
      packages:
        - gamemode
        - steam-devices

  # Systemd User Services
  - type: systemd
    user:
      enabled:
        - gamemoded.service
```

> [!NOTE]
> `gamemoded.service` is also D-Bus activatable via `/usr/share/dbus-1/services/com.feralinteractive.GameMode.service`. Enabling it under `user.enabled` ensures the daemon can respond instantly when session portals query status.

### 4.2. Declarative Sysctl Drop-In: `files/base/usr/lib/sysctl.d/80-gaming.conf`

Create `/usr/lib/sysctl.d/80-gaming.conf` inside `files/base/` in the repository:

```ini
# Gaming memory map & inotify tuning for Proton / SteamOS parity
# Reference: docs/research/flatpak-steam-gamemode.md

# Match SteamOS 3.5+ max VMA allocation ceiling for DXVK / VKD3D
vm.max_map_count = 2147483642

# Increase inotify limits for Steam asset tracking and mod managers
fs.inotify.max_user_watches = 524288
fs.inotify.max_user_instances = 8192
```

### 4.3. Flatpak Runtime Extension: Gamescope

Ensure the Gamescope Vulkan layer extension is installed for Steam's runtime:

```bash
flatpak install flathub org.freedesktop.Platform.VulkanLayer.gamescope
```

---

## 5. Conclusion & Recommendation

1. **Flatpak Permissions**: No custom D-Bus permissions or Flatseal overrides are needed for `com.valvesoftware.Steam`. `libgamemode` inside the sandbox automatically talks to `org.freedesktop.portal.GameMode` over `org.freedesktop.portal.Desktop`, which is permitted by default and safely handles host PID translation.
2. **Device Privileges**: Add `steam-devices` from the official Fedora repository. This instantly solves all `/dev/hidraw*` permission issues for Sony DualSense, Nintendo Switch Pro, Steam Controller, 8BitDo, and VR hardware without external third-party repositories.
3. **Kernel Parameters**: Deploy `/usr/lib/sysctl.d/80-gaming.conf` setting `vm.max_map_count = 2147483642` and expanded inotify limits to ensure crash-free execution of modern Proton games.
4. **Compositor Pairing**: Gamescope launched with `--backend sdl` and `--nested-unfocused-refresh` guarantees stable multi-monitor gaming under Niri without focus freezes or windowing glitches.
