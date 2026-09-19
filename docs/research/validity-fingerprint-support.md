# Research: Validity 138a:00ab Fingerprint Sensor Support on Fedora 44 Atomic

**Ticket Reference**: [#26 (Part of #20)](https://github.com/treindev/trein.os/issues/26)  
**Branch**: `research/validity-fingerprint-support`  
**Date**: September 2026  
**Status**: Complete  

---

## 1. Executive Summary & Verdict

As part of the workstation hardening and hardware enablement milestone for the HP ZBook Studio x360 G5 convertible laptop ([Issue #20](https://github.com/treindev/trein.os/issues/20)), this research investigates the feasibility, stability, and security of supporting the onboard **Validity Sensors, Inc. (138a:00ab)** fingerprint reader on **Fedora 44 Atomic Workstation (BlueBuild)**.

### Definitive Verdict: **UNSUPPORTED / WONTFIX**

Biometrics for the `138a:00ab` sensor should be formally declared **Unsupported / WONTFIX** for the `trein.os` host image (`recipes/base/common.yml`). Do not package, layer, or enable `python-validity` or `open-fprintd`.

### Core Rationale:
1. **Zero Upstream Support**: Mainline `libfprint` does not support USB ID `138a:00ab` in any released version. Upstream Merge Request `!626` remains stalled and unmerged due to complex proprietary cryptography and licensing barriers.
2. **Immutable Filesystem Violations**: The community driver (`python-validity`) and firmware extractor (`validity-sensors-firmware`) hardcode firmware, pairing data, and calibration paths to `/usr/share/python-validity/`. On an ostree/bootc system where `/usr` is mounted strictly read-only (`ro`), initialization and runtime calibration fail with `EROFS` (Read-only file system).
3. **Proprietary Firmware Redistribution Barrier**: The driver requires extracting proprietary binary blobs (`.xpfwext`) from HP Windows SoftPaq driver installers. Distributing these binary blobs inside public container image layers built via GitHub Actions violates HP/Synaptics proprietary copyright and distribution terms.
4. **Daemon Replacement & Base Conflicts**: `python-validity` cannot communicate with standard Fedora `fprintd`. It requires replacing `fprintd` with `open-fprintd`, creating severe package conflicts against the base image (`ghcr.io/ublue-os/base-main:44`) that destabilize future ostree upgrades.
5. **Silicon Mismatch in Generic COPRs**: Available Fedora COPR repositories (`sneexy/python-validity`, `taaem/python-validity`) only package legacy ThinkPad Prometheus drivers (targeting Fedora 38–41). They lack the unmerged `SimpleX-T` patches required for HP sensor silicon variants (`0xd51` and `0x969`), and have no maintenance guarantees for Fedora 44 Python ABI changes.
6. **Authentication Hangs in DMS / PAM**: The driver suffers from persistent USB bus disconnects upon sleep/resume and boot. When `python-validity` or `open-fprintd` stalls, `pam_fprintd.so` blocks the authentication stack for 10–30 seconds, causing Dank Material Shell (`dms-greeter`) and Polkit prompts to freeze or lock users out of their graphical sessions.

---

## 2. Hardware Specification & USB Identification

The HP ZBook Studio x360 G5 convertible workstation integrates a touch-style fingerprint sensor manufactured by Validity Sensors, Inc. (acquired by Synaptics).

```
Bus 001 Device 004: ID 138a:00ab Validity Sensors, Inc.
```

### Silicon Architecture:
* **Product Line**: Synaptics / Validity VFS7552 Touch Sensor (part of the VCSFW / Prometheus hardware generation).
* **Architecture**: **Match-on-Chip (MoC)**. Biometric template extraction, storage, and matching are performed by a secure microcontroller embedded directly on the sensor silicon rather than by the host OS.
* **Internal Silicon Types**: Devices reporting USB ID `138a:00ab` contain divergent internal silicon revisions:
  * Type `0xd51`: Commonly deployed in HP EliteBook 840/850 G5.
  * Type `0x969`: Commonly deployed in HP ZBook Studio G5 and x360 G5 convertible models.
* **Communication Security**: The sensor does not transmit raw image frames over standard USB endpoints. Instead, it requires:
  1. Boot-time uploading of an encrypted microcontroller firmware container (`*.xpfwext`).
  2. A TLS-like encrypted handshake over USB endpoints utilizing Elliptic Curve Cryptography (ECC) and Pre-Shared Keys (PSK).
  3. Mutual device-host cryptographic pairing.

---

## 3. Upstream `libfprint` Status

All findings were checked against the official upstream `libfprint` repository and issue tracker hosted on freedesktop.org:

* **Official Repository**: `gitlab.freedesktop.org/libfprint/libfprint`
* **Supported Devices Wiki**: `fprint.freedesktop.org/supported-devices.html`
* **Result**: **138a:00ab is completely absent** from official released versions of `libfprint` (including versions 1.94.x through modern development HEAD).

### Architectural Blockers in Upstream `libfprint`:
1. **Driver Philosophy**: Upstream `libfprint` operates either as an image capture framework (passing raw biometric images to the host-side `libfprint` matching engine) or as an interface for standard Match-on-Chip devices that conform to documented vendor protocols without out-of-tree cryptographic wrapping.
2. **Proprietary Protocol & Licensing**: Synaptics has never published technical documentation, open specifications, or redistributable firmware for the VFS7552 / VCSFW family. 
3. **Merge Request Status (!626)**:
   * Community developers opened Merge Request **!626** (*"Add support for Validity VCSFW 0x969/0xd51 sensors"*, succeeding earlier PR !579).
   * While tracked in community hubs (e.g., `jedbillyb/linux-fingerprint-drivers`) as hardware-validated on the HP ZBook Studio x360 G5, MR `!626` has remained stalled and unmerged.
   * Upstream maintainers cannot merge reverse-engineered drivers that rely on proprietary firmware blobs without clear redistribution licenses, automated test harnesses, and vendor support.

---

## 4. Community Driver Ecosystem Analysis

To work around upstream omission, community developers created userspace shims to talk to Validity sensors:

```
+----------------------------------------------------------------+
|                     Desktop Authentication                     |
|           (DMS Lockscreen, greetd, Polkit, sudo)               |
+----------------------------------------------------------------+
                                |
                                v
+----------------------------------------------------------------+
|                         PAM Stack                              |
|                       pam_fprintd.so                           |
+----------------------------------------------------------------+
                                |
                        (D-Bus IPC Call)
                                v
+----------------------------------------------------------------+
|                         open-fprintd                           |
|        (Replaces fprintd; owns net.reactivated.Fprint)        |
+----------------------------------------------------------------+
                                |
                        (D-Bus / Unix Socket)
                                v
+----------------------------------------------------------------+
|                      python3-validity                          |
|         (Reverse-engineered userspace crypto & driver)         |
+----------------------------------------------------------------+
                                |
                    (libusb raw USB transfers)
                                v
+----------------------------------------------------------------+
|             Hardware Sensor: Validity 138a:00ab               |
|            (Firmware blob + ECC Session Encrypted)             |
+----------------------------------------------------------------+
```

### 4.1. Core Components

1. **`uunicorn/python-validity`**:
   * A Python daemon running as root that communicates with the hardware via `libusb`.
   * Implements the cryptographic handshake, loads the proprietary firmware blob, manages device pairing, and communicates with `open-fprintd`.
2. **`SimpleX-T/python-validity` (Fork & PR #256)**:
   * The mainline `uunicorn/python-validity` project only targeted Lenovo ThinkPads (`138a:0090`, `138a:0097`, `06cb:009a`).
   * The `138a:00ab` sensor in HP laptops requires the fork by developer `SimpleX-T` (`feat/sensor-type-0xd51` and `0x969`), which introduced custom sensor initialization logic and defensive USB resets.
   * This code was never consolidated or merged into a stable, tagged upstream release.
3. **`open-fprintd`**:
   * Standard `fprintd` expects native `libfprint` C drivers. Because `python-validity` runs out-of-tree, `open-fprintd` was written as a drop-in Python replacement daemon that exposes the standard `net.reactivated.Fprint` D-Bus interface.

### 4.2. Firmware Extraction & Cryptographic Pairing Requirements

* **HP SoftPaq Dependency**: The sensor will not function without firmware extracted from HP's Windows driver installer (e.g., SoftPaq `sp135736.exe` or `sp96668.exe`). The utility `validity-sensors-firmware` extracts `.xpfwext` files from the `WBF_Drivers` cabinet files.
* **Cryptographic Pairing**:
  * During initial setup, the driver generates an Elliptic Curve keypair and PSK stored in local pairdata.
  * If the laptop was ever booted into Windows or enrolled in Windows Hello, the hardware enclave locks itself to the Windows SID. Linux enrollment fails with factory-reset errors (`0404` error) unless the sensor is reset or distinct fingers are enrolled.
* **Bus Disconnects & Defensive Resets**:
  * After system reboot or cold boot, the sensor frequently enters an uninitialized state where it disappears from the USB bus or fails to respond to D-Bus requests.
  * The `SimpleX-T` driver requires issuing a defensive `udevadm` trigger or USB port reset on every startup:
    ```bash
    udevadm trigger --attr-match=idVendor=138a --attr-match=idProduct=00ab
    ```

---

## 5. Architectural Evaluation on Fedora 44 Atomic / BlueBuild

Integrating this community stack into `trein.os` (`ublue-os/base-main:44`) was evaluated against container image building, ostree runtime constraints, and system security.

### 5.1. Conflict 1: Read-Only Filesystem Violations (`/usr` is `ro`)

| Component | Default Expected Path | Ostree / bootc Reality | Consequence |
|---|---|---|---|
| Firmware Blobs | `/usr/share/python-validity/*.xpfwext` | Read-only at runtime | Running `validity-sensors-firmware` post-install crashes with `EROFS` |
| Calibration Data | `/usr/share/python-validity/calib-data.bin` | Read-only at runtime | Sensor cannot store runtime calibration or write backoff tables |
| Playground Scripts | `/usr/share/python-validity/playground/` | Read-only at runtime | Pairing reset scripts cannot write temporary state files |

*Mitigation Attempt*: Symlinking `/usr/share/python-validity` to `/var/lib/python-validity` creates complex mutable state in `/var`, defeating the declarative, reproducible build philosophy of BlueBuild.

### 5.2. Conflict 2: Base Package Replacement in Immutable Image

The base container image `ghcr.io/ublue-os/base-main:44` ships official Fedora `fprintd` and `fprintd-pam` packages.
* Installing `open-fprintd` requires removing `fprintd` and `fprintd-pam` due to file and D-Bus namespace collisions (`net.reactivated.Fprint`).
* In BlueBuild recipes, removing base packages via `type: dnf` and layering replacement daemons from unvetted COPRs weakens the dependency graph and frequently causes broken updates during Fedora version rebases.

### 5.3. Conflict 3: COPR Stagnation & Fedora 44 Python ABI Breaks

* Available COPR repositories (`sneexy/python-validity`, `taaem/python-validity`):
  1. Only build for Fedora 39–41; neither maintains packages for Fedora 44 (Rawhide/future development).
  2. Package the upstream `uunicorn` branch for Lenovo hardware; **they do NOT contain the `SimpleX-T` patches for HP `138a:00ab`**.
* Fedora 44 incorporates Python 3.14/3.15 changes where legacy C-extension APIs and byte-compiled packages fail if unmaintained. Maintaining a custom COPR or in-tree build of `python-validity` + `open-fprintd` for `trein.os` would impose a permanent engineering tax on a personal workstation image.

### 5.4. Conflict 4: Legal & Licensing Redistribution Barriers

* Distributing the extracted HP `.xpfwext` firmware blob inside the public `trein.os` container registry (`ghcr.io/treindev/trein.os` or private Zot mirror) would violate HP and Synaptics End User License Agreements (EULA).
* BlueBuild cannot legally download, extract, and bake non-redistributable proprietary firmware into open container image layers.

### 5.5. Conflict 5: Suspend/Resume Instability

Community testing reveals that `python-validity` fails to recover after system suspend/sleep on HP ZBook hardware. The workaround requires enabling auxiliary recovery services:
* `open-fprintd-restart-after-resume.service`
* `python3-validity-restart-after-resume.service`
* A custom udev rule to force a bus power cycle.

Despite these hooks, race conditions between display wake and USB bus enumeration regularly leave the daemon in a deadlocked state.

---

## 6. Desktop Shell (DMS) & PAM Authentication Integration

The desktop stack in `trein.os` combines **Niri** (Wayland scrollable-tiling compositor) with **Dank Material Shell (DMS)** and `dms-greeter`.

### 6.1. PAM Stack Operation

Fingerprint authentication in Fedora is enabled via:
```bash
authselect enable-feature with-fingerprint
```
This updates `/etc/pam.d/system-auth`, `/etc/pam.d/password-auth`, and `/etc/pam.d/polkit-1` by inserting:
```pam
auth [success=done default=ignore] pam_fprintd.so
```

When PAM is invoked:
1. `pam_fprintd.so` sends a D-Bus method call to `net.reactivated.Fprint`.
2. The daemon claims the sensor and enters an asynchronous capture loop.
3. If no finger is swiped, or if the sensor is unresponsive, PAM waits until `fprintd` times out (default: 10–30 seconds) before falling back to `pam_unix.so` (password entry).

### 6.2. DMS Lockscreen & Greeter Failure Mode

* **Lockscreen Hangs**: Dank Material Shell (`dms` and `dms-greeter`) interfaces with PAM via a Go/Quickshell wrapper.
* When the sensor enters a wedged state (common with `138a:00ab`), `pam_fprintd` blocks the PAM conversation thread.
* **Symptom**: The lockscreen UI freezes, keyboard inputs for the password field are unresponsive, and the user cannot unlock their session until the 30-second timeout expires or they switch to a virtual terminal (TTY, `Ctrl+Alt+F3`) to restart the shell.
* **Polkit Degradation**: Privilege elevation prompts in terminal (`sudo`) and graphical applications (`plasma-polkit-agent` or DMS polkit agent) pause with a blank cursor while waiting for the dead sensor, severely degrading desktop responsiveness.

---

## 7. Actionable Recommendation & Decision Record

### Summary of Alternatives Evaluated

| Approach | Feasibility | Stability | Security / Legal | Decision |
|---|---|---|---|---|
| **Upstream `libfprint`** | ❌ None (Device not supported; MR !626 unmerged) | N/A | Clean / Open source | Rejected (Upstream unsupported) |
| **`python-validity` via COPR** | ❌ Broken (COPR lacks HP 00ab patches; Fedora 44 incompatible) | ❌ Poor (Resume crashes, daemon hangs) | ⚠️ Unvetted third-party COPR; privileged Python root daemon | Rejected (Incompatible & unmaintained) |
| **Custom Containerfile Build + Extracted Firmware** | ⚠️ Partial (Can compile SimpleX-T fork & hack /var links) | ❌ Fragile (USB bus disconnects, PAM timeouts) | ❌ Violates HP EULA; bundles proprietary blobs | Rejected (Legal risk & maintenance nightmare) |
| **Declare Unsupported / WONTFIX** | ✅ Immediate | ✅ Perfect (Clean PAM, no hangs, zero bloat) | ✅ Fully compliant and secure | **APPROVED** |

### Implementation Instructions for `trein.os`

1. **`recipes/base/common.yml`**:
   * Do **NOT** add `python3-validity`, `open-fprintd`, or `sneexy/python-validity` COPR to the recipe.
   * Ensure `fprintd` and `fprintd-pam` remain either unconfigured or inactive. Do not enable `with-fingerprint` in `authselect`.
   * Standard password authentication remains the sole, robust authentication path for DMS, `greetd`, and Polkit.

2. **Future Upstream Re-evaluation**:
   * Revisit biometric support only if:
     1. Upstream `libfprint` merges MR `!626` or native kernel/userspace drivers for Synaptics VCSFW sensors.
     2. Firmware is distributed officially via the Linux Vendor Firmware Service (LVFS / `fwupd`).

---

## 8. Primary Sources & References

1. **libfprint Upstream Project**:
   * Repository: [https://gitlab.freedesktop.org/libfprint/libfprint](https://gitlab.freedesktop.org/libfprint/libfprint)
   * Supported Devices List: [https://fprint.freedesktop.org/supported-devices.html](https://fprint.freedesktop.org/supported-devices.html)
   * Merge Request !626 (Validity VCSFW 0x969/0xd51): [https://gitlab.freedesktop.org/libfprint/libfprint/-/merge_requests/626](https://gitlab.freedesktop.org/libfprint/libfprint/-/merge_requests/626)
2. **Community Linux Fingerprint Drivers Tracker**:
   * Hardware Validation Hub: [https://github.com/jedbillyb/linux-fingerprint-drivers](https://github.com/jedbillyb/linux-fingerprint-drivers)
   * Device entry for `138a:00ab` on HP ZBook Studio x360 G5.
3. **`python-validity` Repositories & Specifications**:
   * Upstream Daemon: [https://github.com/uunicorn/python-validity](https://github.com/uunicorn/python-validity)
   * SimpleX-T Fork (HP 00ab / 0xd51 Support): [https://github.com/SimpleX-T/python-validity/tree/feat/sensor-type-0xd51](https://github.com/SimpleX-T/python-validity/tree/feat/sensor-type-0xd51)
   * Open Fprintd Bridge: [https://github.com/uunicorn/open-fprintd](https://github.com/uunicorn/open-fprintd)
4. **Fedora Packaging & COPR Specifications**:
   * Sneexy Python-Validity COPR: [https://copr.fedorainfracloud.org/coprs/sneexy/python-validity/](https://copr.fedorainfracloud.org/coprs/sneexy/python-validity/)
   * Git Packaging Spec: [https://git.gay/sneexy/copr/tree/master/python-validity](https://git.gay/sneexy/copr/tree/master/python-validity)
5. **Dank Material Shell (DMS)**:
   * Greeter & Lockscreen Repository: [https://github.com/AvengeMedia/dms-greeter](https://github.com/AvengeMedia/dms-greeter)
   * Documentation: [https://danklinux.com/docs/](https://danklinux.com/docs/)
