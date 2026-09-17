# Flavor-tagged container images

Multiple machine hardware targets (e.g., Nvidia laptop, generic non-Nvidia desktop) share a unified container repository (`ghcr.io/treindev/trein.os`) differentiated by flavor tags (e.g. `niri-nvidia`, `niri`) rather than publishing separate container image repositories or embedding runtime driver detection.
