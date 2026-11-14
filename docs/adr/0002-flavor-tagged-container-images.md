# Flavor-tagged container images (Superseded)

**Status:** Superseded

Originally, multiple machine hardware targets (e.g., NVIDIA laptop, generic non-NVIDIA desktop) shared `ghcr.io/treindev/trein.os` differentiated by flavor tags (`niri-nvidia`, `niri`, `gaming-nvidia`).

Because only a single Plasma + NVIDIA Kinoite configuration is actively used in practice, the repository has consolidated onto a single `recipes/recipe.yml` publishing BlueBuild's default `:latest` and versioned (`:45`) tags to eliminate redundant CI builds and maintenance overhead.
