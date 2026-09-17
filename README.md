# trein.os &nbsp; [![bluebuild build badge](https://github.com/treindev/trein.os/actions/workflows/build.yml/badge.svg)](https://github.com/treindev/trein.os/actions/workflows/build.yml)

An opinionated, immutable Fedora Atomic workstation built with [BlueBuild](https://blue-build.org/), featuring the [Niri](https://github.com/YaLTeR/niri) scrollable-tiling Wayland compositor, [Dank Material Shell (DMS)](https://github.com/avengemedia/dms), and containerized development via [Distrobox](https://github.com/89luca89/distrobox).

---

## System Overview

- **Host Image**: Fedora Atomic 44 ([Universal Blue `base-main`](https://github.com/ublue-os/base-main))
- **Compositor**: [Niri](https://github.com/YaLTeR/niri) (infinite scrollable-tiling Wayland compositor)
- **Desktop Shell & Greeter**: Dank Material Shell (`dms`) with `dms-greeter` running on `greetd`
- **Shell & Terminal**: Fish shell and [Ghostty](https://ghostty.org/)
- **Graphics / Drivers**: NVIDIA proprietary drivers built via `akmods`
- **Development**: Isolated Distrobox (`devbox`) with exported IDEs (VS Code, Zed, Antigravity)
- **Virtualization**: Host-layered KVM/QEMU hypervisor with `virt-manager`
- **Application Layer**: System-level Flatpaks (Firefox, Steam, Bottles, Prism Launcher, Discord, Actual Budget, Calibre, MediaWriter, Bazaar, Flatseal)

---

## Flavors & Installation

Images are signed with [Sigstore](https://www.sigstore.dev/)'s [cosign](https://github.com/sigstore/cosign) and published to the GitHub Container Registry under `ghcr.io/treindev/trein.os`.

Per [ADR-0002](docs/adr/0002-flavor-tagged-container-images.md), builds are organized into flavor tags:

| Flavor | Tag | Target Hardware |
| :--- | :--- | :--- |
| **Niri + NVIDIA** (Default) | `niri-nvidia` | Personal laptop with dedicated NVIDIA GPU |
| **Niri Generic** | `niri` | Desktop / work laptop with AMD or Intel graphics |

### Rebasing an Existing Atomic Fedora System

Replace `<flavor>` with your target flavor (e.g. `niri-nvidia` or `niri`):

1. **Rebase to the unsigned image** to import container signing keys and policies:
   ```bash
   rpm-ostree rebase ostree-unverified-registry:ghcr.io/treindev/trein.os:<flavor>
   ```
2. **Reboot** to boot into the new image:
   ```bash
   systemctl reboot
   ```
3. **Rebase to the signed image**:
   ```bash
   rpm-ostree rebase ostree-image-signed:docker://ghcr.io/treindev/trein.os:<flavor>
   ```
4. **Reboot** to complete verification:
   ```bash
   systemctl reboot
   ```

### Verification

Verify image signatures manually using `cosign.pub` from this repository:

```bash
cosign verify --key cosign.pub ghcr.io/treindev/trein.os:<flavor>
```

---

## Development Environment (`devbox`)

Per [ADR-0001](docs/adr/0001-distrobox-first-development-environment.md), the host image remains lean and stable. Compilers, runtimes, and graphical IDEs are isolated inside a mutable Distrobox container named `devbox`.

- **Declarative Assembly**: Defined via `/etc/distrobox/distrobox.ini` (`files/base/etc/distrobox/distrobox.ini`) using `distrobox assemble`. Provisioned seamlessly on first login by `init-devbox.service`.
- **Graphics & Hardware**: Dedicated NVIDIA GPU passthrough enabled (`nvidia=true`).
- **Tooling & IDEs**: Pre-initialization hooks configure external repositories (VS Code RPM repository & Microsoft signing key). Automatic hooks bootstrap development IDEs (VS Code, Zed, and Antigravity CLI).
- **Application & Binary Exports**: GUI applications (`code`, `zed`) are exported to host desktop menus, and CLI commands (`/usr/bin/code`) are exported directly into host shells.
- **Host Wrapper Command**: Running `devbox` (or `devbox <command>`) directly from host shells (Fish, Bash, etc.) enters the container or executes commands within it.
- **Background Auto-Updates**: `devbox-update.timer` triggers asynchronously ~5 minutes after login (`OnStartupSec=5m`) to run `distrobox upgrade devbox` with non-intrusive notifications.

---

## Dotfiles & Machine Customization

Per [ADR-0003](docs/adr/0003-chezmoi-for-user-dotfiles.md), machine-specific configurations (such as multi-monitor layouts) and user dotfiles are decoupled from the host image:

- `/etc/skel/` provides fallback compositor and shell defaults for unconfigured user accounts.
- Active dotfiles, per-machine monitor geometries, and keybinding overrides are managed via **Chezmoi**.
- **Planned Migration ([#5](https://github.com/treindev/trein.os/issues/5))**: Moving personal Niri configs and templated display profiles to an external dotfiles repository via BlueBuild's official `chezmoi` module.

---

## Repository Structure

```
trein.os/
├── CONTEXT.md               # Domain vocabulary and ubiquitous terms
├── AGENTS.md                # Agent workflow rules and guidelines
├── recipes/                 # BlueBuild image definitions
│   ├── niri-nvidia.yml      # Niri + NVIDIA flavor
│   ├── niri.yml             # Niri generic (non-Nvidia) flavor
│   └── base/                # Reusable module snippets
│       ├── common.yml       # Base packages, fonts, flatpaks, user services
│       ├── niri.yml         # Niri compositor and DMS shell
│       └── nvidia.yml       # Kernel modules and drivers
├── files/                   # Root filesystem overlays
│   ├── base/                # Systemd units and core system files
│   └── niri/                # Greetd configs and skeleton defaults
├── docs/
│   ├── adr/                 # Architecture Decision Records
│   │   ├── 0001-distrobox-first-development-environment.md
│   │   ├── 0002-flavor-tagged-container-images.md
│   │   └── 0003-chezmoi-for-user-dotfiles.md
│   └── agents/              # Agent skills and tracker documentation
└── cosign.pub               # Public key for container verification
```

---

## License

See [LICENSE](LICENSE).
