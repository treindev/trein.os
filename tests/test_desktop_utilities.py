import unittest
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestDesktopUtilities(unittest.TestCase):
    def setUp(self):
        self.common_path = REPO_ROOT / "recipes" / "base" / "common.yml"
        self.assertTrue(self.common_path.is_file(), f"Missing {self.common_path}")
        self.content = yaml.safe_load(self.common_path.read_text())
        self.modules = self.content.get("modules", [])
        self.dnf_modules = [m for m in self.modules if m.get("type") == "dnf" and "install" in m]

    def _get_installed_packages(self):
        packages = []
        for dm in self.dnf_modules:
            packages.extend(dm.get("install", {}).get("packages", []))
        return packages

    def test_niri_and_ghostty_packages_removed(self):
        installed = self._get_installed_packages()
        for pkg in [
            "flameshot",
            "grim",
            "slurp",
            "swappy",
            "nautilus",
            "xdg-desktop-portal-gnome",
            "adw-gtk3-theme",
            "ghostty",
        ]:
            self.assertNotIn(
                pkg,
                installed,
                f"'{pkg}' must be removed from base/common.yml for Plasma-only Kinoite image",
            )

        for dm in self.dnf_modules:
            coprs = dm.get("repos", {}).get("copr", [])
            self.assertNotIn("scottames/ghostty", coprs)

    def test_desktop_control_utilities_installed(self):
        installed = self._get_installed_packages()
        self.assertIn(
            "playerctl",
            installed,
            "playerctl must be installed to support MPRIS media control",
        )
        self.assertIn(
            "brightnessctl",
            installed,
            "brightnessctl must be installed for scriptable backlight control",
        )
        self.assertIn(
            "cups-pk-helper",
            installed,
            "cups-pk-helper must be installed for printer policy integration",
        )


if __name__ == "__main__":
    unittest.main()
