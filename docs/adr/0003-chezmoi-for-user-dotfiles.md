# Chezmoi for user dotfile management

User-specific desktop configurations, monitor geometries, and shell dotfiles are managed externally via the official BlueBuild `chezmoi` module rather than baked permanently into the immutable host image. Baseline fallbacks remain in `/etc/skel` for unconfigured accounts, while per-machine configurations (such as multi-monitor layouts) are templated and synced through a dedicated Chezmoi dotfiles repository.
