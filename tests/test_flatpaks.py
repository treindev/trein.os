import unittest
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestDeclarativeFlatpaks(unittest.TestCase):
    def setUp(self):
        self.flatpaks_path = REPO_ROOT / "recipes" / "base" / "flatpaks.yml"
        self.steam_path = REPO_ROOT / "recipes" / "base" / "flatpaks-steam.yml"
        self.assertTrue(self.flatpaks_path.is_file(), f"Missing {self.flatpaks_path}")
        self.assertTrue(self.steam_path.is_file(), f"Missing {self.steam_path}")
        self.content = yaml.safe_load(self.flatpaks_path.read_text())
        self.steam_content = yaml.safe_load(self.steam_path.read_text())
        self.flatpak_modules = [m for m in self.content.get("modules", []) if m.get("type") == "default-flatpaks"]
        self.steam_modules = [m for m in self.steam_content.get("modules", []) if m.get("type") == "default-flatpaks"]

    def _get_flatpak_config(self):
        self.assertTrue(len(self.flatpak_modules) > 0, "No default-flatpaks module found in recipes/base/flatpaks.yml")
        configs = self.flatpak_modules[0].get("configurations", [])
        self.assertTrue(len(configs) > 0, "No configurations entry in default-flatpaks module")
        return configs[0]

    def _get_steam_config(self):
        self.assertTrue(len(self.steam_modules) > 0, "No default-flatpaks module found in recipes/base/flatpaks-steam.yml")
        configs = self.steam_modules[0].get("configurations", [])
        self.assertTrue(len(configs) > 0, "No configurations entry in steam default-flatpaks module")
        return configs[0]

    def _get_installed_flatpaks(self):
        config = self._get_flatpak_config()
        steam_config = self._get_steam_config()
        return config.get("install", []) + steam_config.get("install", [])

    def test_default_flatpaks_configuration(self):
        config = self._get_flatpak_config()
        self.assertEqual(config.get("scope"), "system", "Flatpaks must be installed at system scope")
        self.assertTrue(config.get("notify"), "Notification must be enabled for default flatpak installs")

    def test_curated_multimedia_and_internet_flatpaks_installed(self):
        installed = self._get_installed_flatpaks()
        curated_apps = [
            "com.spotify.Client",
            "org.chromium.Chromium",
            "com.protonvpn.www",
            "org.jellyfin.JellyfinDesktop",
            "org.qbittorrent.qBittorrent",
        ]
        for app in curated_apps:
            self.assertIn(
                app,
                installed,
                f"Curated flatpak '{app}' must be declared in default-flatpaks install list",
            )

    def test_existing_essential_flatpaks_retained(self):
        installed = self._get_installed_flatpaks()
        baseline_apps = [
            "org.mozilla.firefox",
            "com.valvesoftware.Steam",
            "com.usebottles.bottles",
            "org.prismlauncher.PrismLauncher",
            "com.discordapp.Discord",
            "org.fedoraproject.MediaWriter",
            "com.actualbudget.actual",
            "com.calibre_ebook.calibre",
            "io.github.kolunmi.Bazaar",
            "com.github.tchx84.Flatseal",
        ]
        for app in baseline_apps:
            self.assertIn(
                app,
                installed,
                f"Baseline flatpak '{app}' must be retained in default-flatpaks install list",
            )

    def test_adr0001_heavyweight_ides_excluded(self):
        installed = self._get_installed_flatpaks()
        excluded_developer_ides = [
            "com.google.AndroidStudio",
            "com.visualstudio.code",
            "dev.zed.Zed",
        ]
        for ide in excluded_developer_ides:
            self.assertNotIn(
                ide,
                installed,
                f"Developer IDE '{ide}' must not be declared as host Flatpak; must be in Devbox per ADR-0001",
            )


if __name__ == "__main__":
    unittest.main()
