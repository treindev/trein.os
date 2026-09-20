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

    def test_flameshot_removed(self):
        installed = self._get_installed_packages()
        self.assertNotIn(
            "flameshot",
            installed,
            "flameshot must be removed in favor of modern Wayland screenshot tooling",
        )

    def test_wayland_screenshot_utilities_installed(self):
        installed = self._get_installed_packages()
        for pkg in ["grim", "slurp", "swappy"]:
            self.assertIn(
                pkg,
                installed,
                f"Modern Wayland screenshot utility '{pkg}' must be in dnf install packages",
            )

    def test_desktop_control_utilities_installed(self):
        installed = self._get_installed_packages()
        self.assertIn(
            "playerctl",
            installed,
            "playerctl must be installed to support MPRIS media keybindings in binds.kdl",
        )
        self.assertIn(
            "brightnessctl",
            installed,
            "brightnessctl must be installed for scriptable backlight control",
        )

    def test_dms_integration_dependencies_installed(self):
        installed = self._get_installed_packages()
        self.assertIn(
            "adw-gtk3-theme",
            installed,
            "adw-gtk3-theme must be installed to satisfy DMS GTK3 theming and doctor checks",
        )
        self.assertIn(
            "cups-pk-helper",
            installed,
            "cups-pk-helper must be installed to satisfy DMS doctor checks and printer policy",
        )


if __name__ == "__main__":
    unittest.main()
