# trein.os

A custom immutable Fedora Atomic workstation system built with BlueBuild, designed for personal laptops and desktops with scrollable-tiling Wayland compositing and containerized development.

## Language

**Host Image**:
The immutable, ostree-based system layer built from BlueBuild recipes that manages the hardware drivers, desktop compositor, and core system services.
_Avoid_: Base OS, rootfs, host system

**Devbox**:
The primary mutable Distrobox container used to isolate GUI code editors, developer toolchains, and programming environments from the host image.
_Avoid_: Toolbox, dev container, subshell, VM

**Recipe**:
A top-level declarative BlueBuild YAML document defining the base container image, image version, and module pipeline for a specific hardware or environment flavor.
_Avoid_: Manifest, build script, Containerfile

**Flavor**:
A distinct build configuration of the host image targeting specific hardware capabilities (such as `niri-nvidia` or `niri`) published as a dedicated container tag under the unified image repository.
_Avoid_: Variant, edition, release, distro

**Base Module**:
A modular BlueBuild configuration snippet residing in `recipes/base/` that defines a reusable layer of system packages, files, or services.
_Avoid_: Component, sub-recipe, mixin

**Dotfiles Repository**:
An external user configuration repository managed via Chezmoi that defines shell environments, editor preferences, and per-machine display layouts independently of the host image.
_Avoid_: Skel config, system dotfiles, host configuration
