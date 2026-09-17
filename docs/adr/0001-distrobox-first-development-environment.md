# Distrobox-first development environment

The host ostree image is kept strictly lean and stable, containing only desktop compositing, GPU drivers, core system utilities, and desktop flatpaks. All IDEs (VS Code, Zed, Antigravity), toolchains, compilers, and project dependencies are isolated inside a mutable Distrobox container (`devbox`) with GPU forwarding, rather than layered into the host image or packaged as sandboxed Flatpaks.
