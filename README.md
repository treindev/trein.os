# trein.os &nbsp; [![bluebuild build badge](https://github.com/treindev/trein.os/actions/workflows/build.yml/badge.svg)](https://github.com/treindev/trein.os/actions/workflows/build.yml)

An opinionated, immutable Fedora Atomic workstation built with [BlueBuild](https://blue-build.org/), based on Universal Blue's Fedora Kinoite (KDE Plasma) with NVIDIA drivers, host-layered Steam gaming tooling, and containerized development via [Distrobox](https://github.com/89luca89/distrobox).

---

## System Overview

- **Host Image**: Fedora Atomic 45 ([Universal Blue `kinoite-main`](https://github.com/ublue-os/main))
- **Desktop Environment & Greeter**: KDE Plasma with SDDM
- **Shell**: Fish shell
- **Graphics / Drivers**: NVIDIA proprietary drivers built via `akmods`
- **Gaming**: Host-layered RPM Steam (`steam`, `gamemode`, `gamescope`, `steam-devices`) and SteamOS sysctl tuning (`vm.max_map_count = 2147483642`)
- **Development**: Isolated Distrobox (`devbox`) with exported IDEs (VS Code, Zed, Antigravity)
- **Virtualization**: Host-layered KVM/QEMU hypervisor with `virt-manager`
- **Application Layer**: System-level Flatpaks (Firefox, Bottles, Prism Launcher, Discord, Actual Budget, Calibre, MediaWriter, Bazaar, Flatseal)

---

## Installation

Images are signed with [Sigstore](https://www.sigstore.dev/)'s [cosign](https://github.com/sigstore/cosign) and published to the GitHub Container Registry under `ghcr.io/treindev/trein.os:latest` (and `:45`).

### Rebasing an Existing Atomic Fedora System

1. **Rebase to the unsigned image** to import container signing keys and policies:
   ```bash
   rpm-ostree rebase ostree-unverified-registry:ghcr.io/treindev/trein.os:latest
   ```
2. **Reboot** to boot into the new image:
   ```bash
   systemctl reboot
   ```
3. **Rebase to the signed image**:
   ```bash
   rpm-ostree rebase ostree-image-signed:docker://ghcr.io/treindev/trein.os:latest
   ```
4. **Reboot** to complete verification:
   ```bash
   systemctl reboot
   ```

### Verification

Verify image signatures manually using `cosign.pub` from this repository:

```bash
cosign verify --key cosign.pub ghcr.io/treindev/trein.os:latest
```

---

## Development Environment (`devbox`)

Per [ADR-0001](docs/adr/0001-distrobox-first-development-environment.md), the host image remains lean and stable. Compilers, runtimes, and graphical IDEs are isolated inside a mutable Distrobox container named `devbox`.

- **Declarative Assembly**: Defined via `/etc/distrobox/distrobox.ini` (`files/base/etc/distrobox/distrobox.ini`) using `distrobox assemble`. Provisioned seamlessly on first login by `init-devbox.service`.
- **Graphics & Hardware**: Dedicated NVIDIA GPU passthrough enabled (`nvidia=true`).
- **Tooling & IDEs**: Pre-initialization hooks configure external repositories (VS Code RPM repository & Microsoft signing key). Automatic hooks bootstrap development IDEs (VS Code, Zed, Antigravity 2.0, and Antigravity CLI).
- **Application & Binary Exports**: GUI applications (`code`, `zed`, `antigravity`) are exported to host desktop menus, and CLI commands (`/usr/bin/code`, `/usr/local/bin/antigravity`) are exported directly into host shells.
- **Host Wrapper Command**: Running `devbox` (or `devbox <command>`) directly from host shells (Fish, Bash, etc.) enters the container or executes commands within it.
- **Background Auto-Updates**: `devbox-update.timer` triggers asynchronously ~5 minutes after login (`OnStartupSec=5m`) to run `distrobox upgrade devbox` with non-intrusive notifications.

---

## Dotfiles & Machine Customization

Per [ADR-0003](docs/adr/0003-chezmoi-for-user-dotfiles.md), machine-specific configurations (such as multi-monitor layouts) and user dotfiles are decoupled from the host image via **Chezmoi**.

---

## Repository Structure

```
trein.os/
├── CONTEXT.md               # Domain vocabulary and ubiquitous terms
├── AGENTS.md                # Agent workflow rules and guidelines
├── recipes/                 # BlueBuild image definitions
│   ├── recipe.yml           # Main Kinoite Plasma + NVIDIA + Gaming recipe
│   └── base/                # Reusable module snippets
│       ├── common.yml       # Base packages, fonts, flatpaks, user services
│       ├── gaming.yml       # Host RPM Steam, GameMode, Gamescope, udev rules
│       └── nvidia.yml       # Kernel modules and drivers
├── files/                   # Root filesystem overlays
│   └── base/                # Systemd units, sysctl, udev rules, and core scripts
├── docs/
│   ├── adr/                 # Architecture Decision Records
│   │   ├── 0001-distrobox-first-development-environment.md
│   │   ├── 0002-flavor-tagged-container-images.md  # Superseded
│   │   └── 0003-chezmoi-for-user-dotfiles.md
│   └── agents/              # Agent skills and tracker documentation
└── cosign.pub               # Public key for container verification
```

---

## License

See [LICENSE](LICENSE).
