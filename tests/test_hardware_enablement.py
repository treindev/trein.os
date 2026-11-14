import os
import stat
import unittest
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestHardwareEnablement(unittest.TestCase):
    def setUp(self):
        self.common_path = REPO_ROOT / "recipes" / "base" / "common.yml"
        self.assertTrue(self.common_path.is_file(), f"Missing {self.common_path}")
        self.common_content = yaml.safe_load(self.common_path.read_text())
        self.common_modules = self.common_content.get("modules", [])
        self.dnf_modules = [m for m in self.common_modules if m.get("type") == "dnf" and "install" in m]
        self.systemd_modules = [m for m in self.common_modules if m.get("type") == "systemd"]

    def _get_installed_packages(self):
        packages = []
        for dm in self.dnf_modules:
            packages.extend(dm.get("install", {}).get("packages", []))
        return packages

    def test_polkit_kde_and_plasma_service_removed(self):
        """Verify polkit-kde and plasma-polkit-agent.service are removed per Research #24."""
        packages = self._get_installed_packages()
        self.assertNotIn("polkit-kde", packages, "polkit-kde must be purged from dnf packages")

        for sm in self.systemd_modules:
            user_enabled = sm.get("user", {}).get("enabled", [])
            self.assertNotIn(
                "plasma-polkit-agent.service",
                user_enabled,
                "plasma-polkit-agent.service must be removed from user enabled services",
            )

    def test_iio_sensor_proxy_installed_and_enabled(self):
        """Verify iio-sensor-proxy is installed and systemd service enabled per Research #25."""
        packages = self._get_installed_packages()
        self.assertIn(
            "iio-sensor-proxy",
            packages,
            "iio-sensor-proxy must be in dnf install packages",
        )

        system_enabled_services = []
        for sm in self.systemd_modules:
            system_enabled_services.extend(sm.get("system", {}).get("enabled", []))
        self.assertIn(
            "iio-sensor-proxy.service",
            system_enabled_services,
            "iio-sensor-proxy.service must be enabled in systemd system services",
        )

    def test_fingerprint_biometrics_wontfix(self):
        """Verify unsupported third-party fingerprint packages are NOT added per Research #26."""
        packages = self._get_installed_packages()
        self.assertNotIn(
            "open-fprintd",
            packages,
            "open-fprintd must not be installed (unsupported Validity 138a:00ab)",
        )
        self.assertNotIn(
            "python-validity",
            packages,
            "python-validity must not be installed (unsupported Validity 138a:00ab)",
        )

    def test_input_inhibit_udev_rules(self):
        """Verify udev rules grant input group access to keyboard and touchpad sysfs inhibition."""
        udev_path = (
            REPO_ROOT / "files" / "base" / "usr" / "lib" / "udev" / "rules.d" / "99-input-inhibit.rules"
        )
        self.assertTrue(udev_path.is_file(), f"Missing {udev_path}")
        content = udev_path.read_text()
        self.assertIn('ATTR{name}=="AT Translated Set 2 keyboard"', content)
        self.assertIn('ATTR{name}=="SYNA307B:00 06CB:CD46 Touchpad"', content)
        self.assertIn('GROUP="input"', content)


if __name__ == "__main__":
    unittest.main()
