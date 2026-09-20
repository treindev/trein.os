# Research: Upstream Niri Focus Throttling & Native Wayland Gaming Support

**Ticket Reference**: [#46 (Part of #43)](https://github.com/treindev/trein.os/issues/46)  
**Branch**: `research/niri-multi-monitor-gaming`  
**Date**: September 2026  
**Status**: Complete  

---

## 1. Executive Summary & Core Verdict

This investigation addresses the architectural and operational challenges of gaming on the scrollable-tiling **Niri** compositor across multi-monitor setups with NVIDIA hardware in `trein.os`. Specifically, it examines:
1. Niri's frame callback throttling mechanism on unfocused and hidden windows, and upstream proposals for background rendering.
2. The runtime behavior, failure modes, and limitations of Proton 9 / Experimental's native Wayland driver (`PROTON_ENABLE_WAYLAND=1` via `winewayland.drv`) when run directly under Niri without a nested micro-compositor.
3. NVIDIA direct scanout interactions with mixed-refresh-rate displays, modeset transition freezes, and the precise conditions requiring `disable-direct-scanout` in Niri's `debug` configuration block.

### Core Verdict: Gamescope Sandbox is Mandatory; Global Compositor Tweaks Should Be Avoided

1. **Niri Throttles Unfocused/Offscreen Windows to 1 FPS (1 Hz)**:
   In `src/niri.rs`, Niri hardcodes a fallback timer (`FRAME_CALLBACK_THROTTLE = Some(Duration::from_millis(995))`) that sends `wl_surface.frame` callbacks once every second to windows that are not visible on the active output scanout. While upstream PR #4392 (`feat: force render (v2)`) introduces configurable offscreen rendering via window rules, it remains unmerged and pending an internal redraw loop refactor. Direct un-nested gaming under Niri causes severe engine desynchronization, frame-queue buildup, freezing, and crashes when focus shifts away (Issue #1959).
2. **Proton Native Wayland (`PROTON_ENABLE_WAYLAND=1`) Fails on Multi-Monitor Niri**:
   Running Windows games natively on Wayland without Gamescope suffers from three critical issues:
   - **Pointer Escape**: Games release pointer constraints (`wp_pointer_constraints_unstable_v1`) whenever in-game menus, inventories, or pause screens open. On multi-monitor setups, the cursor drifts to adjacent monitors, causing accidental focus loss (Issue #2672).
   - **Focus Loss Cascade**: Accidental focus loss immediately trips Niri's 1 Hz frame callback throttle, freezing or desyncing the game.
   - **Resolution & Scaling Mismatch**: In-game display mode changes break under Wayland tiling models (Issue #3021, #4275), and fractional scaling breaks direct scanout (Issue #4615).
3. **NVIDIA Direct Scanout and Mixed Refresh Rate Conflicts**:
   Niri performs direct scanout by default into the primary KMS plane for fullscreen opaque windows. On NVIDIA proprietary drivers with mixed refresh rates (e.g. 144Hz + 60Hz), switching focus between monitors triggers atomic KMS page-flip stalls, cursor stutter, or complete display driver deadlocks (GNOME Mutter #3913, Niri #1959).
4. **The Architectural Solution**:
   Rather than applying `disable-direct-scanout` globally across Niri—which penalizes desktop rendering latency and efficiency—all Windows gaming in `trein.os` should be isolated in **Gamescope** with:
   ```bash
   gamescope -f -w <WIDTH> -h <HEIGHT> -W <WIDTH> -H <HEIGHT> -r <REFRESH> --backend sdl --force-grab-cursor --nested-unfocused-refresh -- %command%
   ```
   This encapsulates cursor confinement, eliminates focus throttling freezes, isolates resolution switching, and prevents direct scanout modeset deadlocks.

```
+---------------------------------------------------------------------------------------------------+
|                                      Multi-Monitor Workspace                                      |
|                                                                                                   |
|   +---------------------------------------+       +-------------------------------------------+   |
|   |   Primary Gaming Display (144/240Hz)  |       |       Secondary Display (60/120Hz)        |   |
|   |                                       |       |                                           |   |
|   |   +-------------------------------+   |       |   +-----------------------------------+   |   |
|   |   | Gamescope Micro-Compositor    |   |       |   | Host Apps (Discord, Web, Terminal)|   |   |
|   |   |                               |   |       |   |                                   |   |   |
|   |   |  - Locks cursor (--force-grab)|   |       |   |   Focus clicks do NOT disturb     |   |   |
|   |   |  - Paces frame rate at 60Hz   |   |       |   |   the internal game render loop   |   |   |
|   |   |    when unfocused             |   |       |   |                                   |   |   |
|   |   |  - Scales resolution cleanly  |   |       |   |                                   |   |   |
|   |   |  - Absorbs KMS modeset churn  |   |       |   |                                   |   |   |
|   |   +-------------------------------+   |       |   +-----------------------------------+   |   |
|   +---------------------------------------+       +-------------------------------------------+   |
|                                       \                   /                                       |
|                                        v                 v                                        |
|   +-------------------------------------------------------------------------------------------+   |
|   |                           Niri Compositor (Scrollable Tiling)                             |   |
|   |   - Unfocused fallback timer: 1 Hz (bypassed inside Gamescope via nested refresh)         |   |
|   |   - Direct scanout: Untouched / fully preserved for native Wayland clients                |   |
|   +-------------------------------------------------------------------------------------------+   |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Primary Sources & Architectural Investigation

The investigation is grounded in direct inspection of primary sources across Niri source code, the Smithay compositor library, GitHub discussions, and tracking issues:

| Source Domain | File / Repository Reference | Role & Technical Evidence |
| :--- | :--- | :--- |
| **Niri Source Code** | `niri-wm/niri`: `src/niri.rs` (lines 198–201, 2568–2575, 5167–5290) | Establishes `FRAME_CALLBACK_THROTTLE = Some(Duration::from_millis(995))` and 1-second event loop timer `send_frame_callbacks_on_fallback_timer()` for invisible/unfocused windows. |
| **Niri Redraw Loop Spec** | `niri-wm/niri`: `docs/wiki/Development:-Redraw-Loop.md` | Documents `RedrawState` state machine, VBlank estimation, and why frame callbacks are intentionally throttled to prevent client busy loops. |
| **Niri Debug Documentation** | `niri-wm/niri`: `docs/wiki/Configuration:-Debug-Options.md` | Details `disable-direct-scanout`, `enable-overlay-planes`, and `toggle-debug-tint` (`Mod+Shift+Ctrl+T`). |
| **Niri Gaming Documentation** | `niri-wm/niri`: `docs/wiki/Application-Issues.md` | Prescribes `gamescope --backend sdl --force-grab-cursor` for multi-monitor cursor confinement and non-stacking window isolation. |
| **Background Throttling Discussion** | `niri-wm/niri`: [Discussion #1525](https://github.com/niri-wm/niri/discussions/1525) | Outlines issues with browser media drops (YouTube 1080p -> 360p) and game desync; author (YaLTeR) confirms 1 Hz fallback behavior. |
| **Focus Desync & Freezing Bug** | `niri-wm/niri`: [Issue #1959](https://github.com/niri-wm/niri/issues/1959) | Documents game desync, redraw stalls, and permanent freezes when unfocusing World of Warcraft, Warcraft 3, Satisfactory, and Guild Wars 2 under Niri. |
| **Upstream Force-Render PRs** | `niri-wm/niri`: [PR #2609](https://github.com/niri-wm/niri/pull/2609), [PR #4392](https://github.com/niri-wm/niri/pull/4392) | Draft PRs by `busyoGG` and `MithicSpirit` introducing screencast keepalive and `force-render` window rules; currently pending architectural refactor. |
| **Cursor Capture on Multi-Monitor** | `niri-wm/niri`: [Issue #2672](https://github.com/niri-wm/niri/issues/2672) | Demonstrates client-side cursor release during menus and why `--force-grab-cursor` in Gamescope is required to prevent cursor drift across monitors. |
| **Smithay Swapchain Scanout Bug** | `Smithay/smithay`: [Issue #1754](https://github.com/Smithay/smithay/issues/1754), `niri-wm/niri`: [Issue #1765](https://github.com/niri-wm/niri/issues/1765) | Demonstrates NVIDIA Vulkan swapchain recreation loops (`VK_SUBOPTIMAL_KHR` / `VK_ERROR_OUT_OF_DATE_KHR`) caused by scanout tranche flag mismatches on `winewayland.drv`. |
| **Fractional Scaling Scanout Bug** | `niri-wm/niri`: [Issue #4615](https://github.com/niri-wm/niri/issues/4615) | Identifies that fractional scaling factors that do not evenly divide resolution break direct scanout and induce frame pacing jitter. |
| **Fullscreen Modeset Freeze** | `GNOME/mutter`: [Issue #3913](https://gitlab.gnome.org/GNOME/mutter/-/issues/3913) | Documents recurring Wayland desktop lockups and KMS page-flip timeouts during fullscreen window transitions and workspace switches. |

---

## 3. Deep Technical Analysis

### 3.1. Upstream Niri Focus Throttling & Background Rendering Proposals

#### The 1 Hz Fallback Mechanism
In Wayland, clients schedule rendering by requesting a frame callback via `wl_surface.frame`. The compositor sends the frame callback event when it is ready for the client to draw its next frame. When a window is fully covered, minimized, or placed on an inactive workspace, the Wayland specification permits compositors to suspend frame callbacks to conserve power.

In Niri (`src/niri.rs`), this logic is implemented in two distinct paths:

1. **Active Output Path (`send_frame_callbacks`)**:
   During an output's VBlank event, Niri traverses all mapped windows on that output:
   ```rust
   let should_send = |surface: &WlSurface, states: &SurfaceData| {
       let current_primary_output = surface_primary_scanout_output(surface, states);
       if current_primary_output.as_ref() != Some(output) {
           return None;
       }
       // Check throttling state to prevent empty-damage commit busy loops...
   };
   ```
   If a window is not on the active workspace or is not visible on the primary scanout output, `should_send` returns `None`. The window receives **zero** frame callbacks from the monitor's VBlank cycle.

2. **Fallback Timer Path (`send_frame_callbacks_on_fallback_timer`)**:
   To prevent invisible or offscreen clients from permanently deadlocking if their event loops depend on frame callbacks, Niri registers a 1-second fallback timer in its event loop:
   ```rust
   const FRAME_CALLBACK_THROTTLE: Option<Duration> = Some(Duration::from_millis(995));

   event_loop.insert_source(
       Timer::from_duration(Duration::from_secs(1)),
       |_, _, state| {
           state.niri.send_frame_callbacks_on_fallback_timer();
           TimeoutAction::ToDuration(Duration::from_secs(1))
       },
   ).unwrap();
   ```
   When this timer fires, Niri traverses all mapped windows across all outputs and calls `mapped.send_frame(...)` with `should_send = |_, _| None`. This forcibly emits a frame callback with a throttle interval of ~995 ms.

#### Failure Modes in Applications & Games (Discussion #1525, Issue #1959)
This 1 Hz throttling has severe unintended consequences for complex applications:
- **Browser Video Playback (Firefox / YouTube / Twitch)**: When Firefox sits on an unfocused or inactive workspace, video elements observe the 1 Hz callback cadence. Firefox interprets this as display pipeline starvation or background idling, automatically downscaling resolution from 1080p to 360p or halting stream buffering entirely (Discussion #1525).
- **Proton & Wine Game Engines**: Games running under DXVK/VKD3D or native Vulkan often couple internal message dispatch, frame pacing, or engine synchronization to presentation intervals. When unfocused in Niri, the game drops to 1 FPS:
  - In *World of Warcraft: Mists of Pandaria Classic* (Issue #1959), unfocusing the window for a few seconds causes engine desync; refocusing forces a full redraw burst. Leaving it unfocused for >10–15 seconds triggers a permanent freeze or crash.
  - In *Warcraft 3: Reforged*, *Guild Wars 2*, and *Satisfactory*, focus loss similarly induces presentation lockups and freezes.
- **PipeWire Window Screencasting**: Capturing a window into OBS via `xdg-desktop-portal-gnome` / PipeWire drops to 1 FPS if the window is moved to an inactive workspace or scrolled offscreen.

#### Status of Upstream Proposals & Pull Requests
- **PR #2609 (`feat: force render` by busyoGG)**: Proposed adding a global mechanism to bypass frame throttling for offscreen windows, but was stalled by architectural concerns and global data map memory leaks.
- **PR #4392 (`feat: force render (v2)` by MithicSpirit)**: Opened in August 2026 and currently active:
  - Automatically force-renders windows that are active screencast targets at the native output refresh rate.
  - Adds a configurable window rule syntax (e.g. `force-render fps=15` or `force-render { fps 60 }`).
  - Implements per-window timers in the event loop clamped to the last active output's refresh rate.
- **Upstream Verdict & Timeline**:
  While PR #4392 is confirmed functional by community testers, Niri's author (YaLTeR) and maintainers noted that injecting per-window timers into the event loop is architecturally suboptimal ("hacky") and that a proper implementation requires a comprehensive refactor of Niri's internal redraw loop (likely in Niri v3). **Consequently, native upstream background rendering configuration is not available in stable releases and cannot be relied upon for near-term host images.**

---

### 3.2. Proton 9 / Experimental Native Wayland Driver (`PROTON_ENABLE_WAYLAND=1`)

Valve's Proton 9 and Proton Experimental include an experimental native Wayland driver (`winewayland.drv`). Passing `PROTON_ENABLE_WAYLAND=1` instructs Proton to bypass XWayland entirely. However, running native Wayland games under Niri on multi-monitor setups without a nested micro-compositor reveals fundamental behavioral limitations:

#### 1. Pointer Constraints & Cursor Confinement Failure (Issue #2672)
In Wayland, pointer confinement is negotiated via `zwp_pointer_constraints_v1` (`zwp_locked_pointer_v1` and `zwp_confined_pointer_v1`), paired with `zwp_relative_pointer_v1`. While Niri implements both protocols correctly:
- **Client-Side Pointer Release**: Game engines (via SDL2 or Win32 API calls) deliberately release pointer locks when displaying in-game cursor menus (e.g. inventory screens, world maps, pause menus, dialogue trees).
- **Multi-Monitor Cursor Drift**: The moment the pointer lock is released, the physical mouse coordinates are free to leave the window boundaries. In a multi-monitor setup where outputs are placed adjacent to each other (e.g. `position x=0 y=0` and `position x=2560 y=0`), moving the cursor to inspect UI at the edge of the screen causes the pointer to glide onto the secondary monitor.
- **The Accidental Focus Loss Trap**: Clicking anywhere on the secondary monitor transfers keyboard and pointer focus away from the game window. Because the game is now unfocused, Niri's fallback frame throttling immediately throttles the game to 1 Hz, inducing the desync/freeze described in Issue #1959.

#### 2. Relative Mouse Motion & Offset Inaccuracies (Issue #3552)
Under Wine/Proton, Win32 games expect absolute hardware mouse warping via `SetCursorPos`. Because Wayland prohibits clients from arbitrarily repositioning the pointer, `winewayland.drv` simulates cursor movement using relative pointer deltas. On scrolling-tiling compositors:
- Unbounded horizontal canvas positioning can introduce coordinate translation offsets (Issue #3552), causing in-game clicks to register hundreds of pixels away from the rendered crosshair or UI element unless executed in virtual desktop mode.

#### 3. Display Mode & Resolution Switching (Issue #3021, #4275)
Windows games expect arbitrary display mode setting (`ChangeDisplaySettings`), whereas Wayland delegates all window sizing to the compositor via `xdg_toplevel.configure`:
- When a game attempts to switch internal resolution (e.g. from 4K to 1440p), native Wayland clients under Niri frequently experience window shrinkage, odd column resizing, or silent crashes where the process remains running without a visible surface (Issue #3021).
- Alt-tabbing away from and back to a native Wayland game frequently causes the window geometry to shrink into a narrow tile column (Issue #4275).

#### 4. NVIDIA Vulkan Swapchain Desync (Smithay #1754, Niri #1765, #2232)
Historically, Niri's Smithay backend advertised direct scanout preferences via `TrancheFlags::Scanout`. On NVIDIA drivers, `winewayland.drv` misinterpreted these tranches, causing `vkAcquireNextImageKHR()` to continuously return `VK_SUBOPTIMAL_KHR` in windowed mode and `VK_ERROR_OUT_OF_DATE_KHR` in fullscreen mode. The game would enter a tight loop recreating its Vulkan swapchain multiple times per second, dropping performance to 5–10 FPS. While recent Smithay fixes improved tranche handling, native Wayland Vulkan presentation remains substantially more brittle on NVIDIA than standard XWayland or Gamescope.

---

### 3.3. NVIDIA Direct Scanout & Mixed Refresh Rates (Issues #1959, #3913, #4615)

#### Direct Scanout Architecture in Niri
Direct scanout is an essential Wayland optimization wherein the compositor detects that a client surface is fully opaque, unscaled, and covers the entire output. Instead of executing an OpenGL ES composition pass (reading the client DMA-BUF into a texture, binding a framebuffer, and rendering the scene), Niri hands the client's DMA-BUF directly to the Linux Direct Rendering Manager (DRM) KMS primary plane via atomic commit (`drmModeAtomicCommit`).
- **Benefits**: Near-zero display latency, eliminates GPU compositing overhead, reduces power consumption.
- **Verification**: Niri provides a built-in debug action:
  ```kdl
  binds {
      Mod+Shift+Ctrl+T { toggle-debug-tint; }
  }
  ```
  Surfaces that are directly scanned out remain untinted; surfaces rendered through the compositor turn bright green.

#### Mixed Refresh Rate Hazards on NVIDIA
In modern multi-monitor workstations, users frequently combine high-refresh gaming displays (144Hz, 165Hz, 240Hz) with standard productivity displays (60Hz, 75Hz). On NVIDIA proprietary drivers, direct scanout across mixed-refresh-rate displays introduces severe hardware and driver synchronization friction:

1. **Atomic KMS Modeset & Page-Flip Deadlocks (Mutter #3913, Niri #1959)**:
   When direct scanout is active on Monitor A (144Hz) and the user moves the cursor or activates a window on Monitor B (60Hz), Niri must dynamically revoke direct scanout on Monitor A and revert to GLES composition.
   - On NVIDIA proprietary drivers, rapid transitions between direct scanout and EGL/GBM composition frequently stall the kernel DRM driver (`nvidia-drm`).
   - The display pipeline hits an unrecoverable page-flip timeout (`flip_done timed out`), resulting in the mouse pointer and desktop freezing entirely while background audio continues playing (GNOME Mutter #3913).
2. **Fractional Scaling Incompatibility (Issue #4615)**:
   If either monitor uses fractional scaling (e.g. 1.25x or 1.75x) that does not evenly divide the hardware panel resolution, direct scanout fails completely or causes erratic frame pacing and micro-stuttering.
3. **Cursor Plane Micro-Stutter**:
   When direct scanout takes over the primary plane, hardware cursor updates on the secondary monitor can become desynchronized from the GPU's presentation clock, causing visual cursor stutter across the 60Hz display.

#### The `disable-direct-scanout` Flag
Niri exposes an explicit debug option to force all surfaces through the GLES compositor:

```kdl
debug {
    disable-direct-scanout
}
```

- **What it does**: Disables direct scanout to both primary and overlay planes. Every window, including fullscreen games, is composited via shaders.
- **When it is required**:
  1. If switching focus between monitors during fullscreen gaming triggers complete screen freezes, GPU hangs, or `nvidia-drm` page-flip timeouts in `journalctl` / `dmesg`.
  2. If fractional scaling is enabled on the primary gaming monitor and causes frame-pacing judder or tearing.
  3. If multi-monitor mixed-refresh setups exhibit severe frame drops or stutter on the secondary monitor whenever a game is running.
- **Trade-off**: Disabling direct scanout adds approximately 1 frame of latency (~6.9 ms at 144Hz; ~16.6 ms at 60Hz) and marginally increases GPU power usage.

---

## 4. Architectural Comparison: Native Wayland vs. Gamescope Sandbox

The following matrix contrasts running Windows games directly under Niri (`PROTON_ENABLE_WAYLAND=1`) versus encapsulating them inside **Gamescope**:

| Capability / Behavior | Native Wayland (`PROTON_ENABLE_WAYLAND=1`) | Gamescope Sandbox (`--backend sdl`) |
| :--- | :--- | :--- |
| **Cursor Confinement** | **Broken on in-game menus**: Cursor escapes to secondary monitor when game unconfines pointer (Issue #2672). | **Rock-solid**: `--force-grab-cursor` intercepts client unconstrain requests and keeps the pointer locked to the window. |
| **Unfocused Frame Throttling** | **Severe failure**: Drops to 1 Hz on focus loss; causes game engine desync, frame buildup, or freeze (Issue #1959). | **Immune**: `--nested-unfocused-refresh` continuously feeds frames to the client at a fixed rate regardless of Niri focus. |
| **Display Mode Changes** | **Unstable**: In-game resolution changes collapse window geometry or crash the surface (Issue #3021, #4275). | **Virtual Desktop Isolation**: Gamescope presents a static virtual display mode to the game; scales cleanly to output. |
| **NVIDIA Direct Scanout Stability** | **High risk of freeze**: Atomic KMS plane handover during alt-tab/unfocus triggers page-flip stalls (Mutter #3913). | **Safe**: Gamescope runs as a standard Wayland surface, smoothing presentation and eliminating modeset thrashing. |
| **Fractional Scaling** | Breaks direct scanout and induces frame pacing stutter (Issue #4615). | Built-in integer, FSR, and NIS upscalers provide crisp scaling with consistent frame times. |
| **Game Launcher Compatibility** | Breaks CEF/Electron launchers (Battle.net, Paradox, EA App) without extensive CLI workarounds. | Flawlessly embeds game launchers within its virtual X11/XWayland root window. |
| **HDR Enablement** | Experimental / game-dependent. | Fully supported via Gamescope `--hdr-enabled` on supported kernels/drivers. |

---

## 5. Practical Implementation Recommendations for trein.os

Based on the empirical evidence, the recommended configuration for `trein.os` adheres to the following principles:

### 1. Maintain Flatpak Steam with Standardized Gamescope Launchers
Gamescope completely resolves the focus-throttling and cursor-escape pathologies without requiring unmerged Niri patches or invasive compositor-wide compromises.

**Standardized Game Launch Options**:
For games prone to multi-monitor focus loss or desync (such as *Civilization VI*, *World of Warcraft*, *Satisfactory*, or *Guild Wars 2*):

```sh
gamescope -f -w 2560 -h 1440 -W 2560 -H 1440 -r 144 --backend sdl --force-grab-cursor --nested-unfocused-refresh 60 -- %command%
```

**Key Parameters Explained**:
- `-f`: Runs Gamescope fullscreen on the active Niri workspace.
- `-w <W> -h <H>`: Defines the game's internal rendering resolution.
- `-W <W> -H <H>`: Sets the target presentation resolution (matching the monitor).
- `-r <HZ>`: Sets the target presentation refresh rate.
- `--backend sdl`: **Mandatory under Niri.** Gamescope's native Wayland backend has cursor locking regressions (documented in Niri wiki `Application-Issues.md`). The SDL backend guarantees proper cursor confinement.
- `--force-grab-cursor`: **Mandatory for multi-monitor.** Forces relative mouse motion and prevents the cursor from leaking onto adjacent screens when in-game menus open.
- `--nested-unfocused-refresh <FPS>`: **Mandatory for Niri focus stability.** Instructs Gamescope to maintain frame pacing (e.g. 60 FPS) when the window loses focus, bypassing Niri's 1 Hz fallback throttle and preventing engine lockups.

### 2. Selective Application of `disable-direct-scanout`
Per the standing preferences in Map #43 (*"Global compositor `disable-direct-scanout` unless proven necessary after Gamescope tuning"*):
- **Do NOT enable `disable-direct-scanout` globally by default** in `trein.os` dotfiles or recipes.
- Direct scanout provides measurable latency advantages for native Wayland tools and well-behaved applications.
- Because Gamescope presents its output buffer as an ordinary Wayland surface, it absorbs display timing discrepancies without triggering atomic modeset freezes.
- **Only enable `disable-direct-scanout` if**:
  1. A user experiences total system freezes or DRM page-flip timeouts during workspace navigation while Gamescope is running.
  2. The primary monitor utilizes non-integer fractional scaling (e.g. 1.25x / 1.75x) on NVIDIA drivers.

### 3. Upstream Niri Feature Tracking
The project should monitor upstream development on the following milestones:
- **Niri PR #4392**: Monitor for potential inclusion or stabilization of `force-render` window rules. If upstream merges a clean window-rule API for offscreen rendering, evaluate whether specific lightweight background applications (e.g. browser video streaming or OBS window capture) can run without nested wrappers.
- **Wine Wayland Driver (`winewayland.drv`)**: Track upstream Wine and Proton-GE improvements regarding `wp_pointer_constraints_unstable_v1` persistence across UI state changes.

---

## 6. Action Plan & Next Steps (For Map #43)

This research document forms the empirical foundation for subsequent implementation tickets under Map #43:

1. **Ticket #44 (`base/gaming.yml` Enablement)**:
   - Declaratively install `gamemode` and `steam-devices` (udev rules for Xbox, DualSense, and Steam controllers) in the Host Image.
   - Configure user group permissions for controller hardware access.
2. **Ticket #45 (Flatpak Steam & Gamescope Standardization)**:
   - Ensure Flatpak Steam permissions allow Gamescope execution and Wayland socket access.
   - Standardize a reusable launcher helper script (e.g. `gamescope-game` or `trein-game-run`) in dotfiles or host `/usr/bin` that automates detection of active output resolution and applies `--backend sdl --force-grab-cursor --nested-unfocused-refresh`.
3. **Formal ADR Creation**:
   - Author an ADR in `docs/adr/` formalizing Gamescope as the mandatory containerized gaming abstraction layer for `trein.os`.

---

## 7. Conclusion

Niri's strict 1 Hz frame callback throttle on unfocused windows and NVIDIA's atomic direct scanout sensitivities make direct, un-nested Wayland gaming (`PROTON_ENABLE_WAYLAND=1`) unreliable across multi-monitor setups. Rather than applying global compositor workarounds that degrade desktop performance, encapsulating games within Gamescope using `--backend sdl`, `--force-grab-cursor`, and `--nested-unfocused-refresh` completely insulates games from Niri's background throttling and multi-monitor cursor escape, providing a stable, high-performance gaming foundation for `trein.os`.
