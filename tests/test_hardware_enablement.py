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

    def test_iio_niri_executable_and_mapping(self):
        """Verify iio-niri daemon script exists, is executable, and contains valid orientation transforms."""
        script_path = REPO_ROOT / "files" / "niri" / "usr" / "bin" / "iio-niri"
        self.assertTrue(script_path.is_file(), f"Missing {script_path}")
        mode = script_path.stat().st_mode
        self.assertTrue(bool(mode & stat.S_IXUSR), "iio-niri must have executable permissions")

        content = script_path.read_text()
        self.assertIn("monitor-sensor", content)
        self.assertIn("niri", content)

        namespace = {}
        exec(content, namespace)
        orientation_map = namespace["ORIENTATION_MAP"]
        self.assertEqual(orientation_map.get("normal"), "normal")
        self.assertEqual(orientation_map.get("bottom-up"), "180")
        self.assertEqual(orientation_map.get("left-up"), "90")
        self.assertEqual(orientation_map.get("right-up"), "270")

    def test_iio_niri_user_service(self):
        """Verify iio-niri systemd user unit exists and targets eDP-1."""
        service_path = (
            REPO_ROOT / "files" / "niri" / "usr" / "lib" / "systemd" / "user" / "iio-niri.service"
        )
        self.assertTrue(service_path.is_file(), f"Missing {service_path}")
        content = service_path.read_text()
        self.assertIn("ExecStart=/usr/bin/iio-niri listen --target eDP-1", content)
        self.assertIn("WantedBy=graphical-session.target", content)

    def test_niri_recipe_iio_niri_symlink(self):
        """Verify niri recipe creates niri.service.wants symlink for iio-niri.service."""
        niri_path = REPO_ROOT / "recipes" / "base" / "niri.yml"
        self.assertTrue(niri_path.is_file(), f"Missing {niri_path}")
        niri_content = yaml.safe_load(niri_path.read_text())
        script_modules = [m for m in niri_content.get("modules", []) if m.get("type") == "script"]
        snippets = []
        for sm in script_modules:
            snippets.extend(sm.get("snippets", []))

        symlink_cmd = (
            "ln -s /usr/lib/systemd/user/iio-niri.service "
            "/etc/systemd/user/niri.service.wants/iio-niri.service"
        )
        self.assertIn(symlink_cmd, snippets)

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

    def test_niri_input_kdl_touch_tablet_mapping(self):
        """Verify input.kdl maps touch and tablet digitizers to eDP-1."""
        input_path = REPO_ROOT / "files" / "niri" / "etc" / "skel" / ".config" / "niri" / "input.kdl"
        self.assertTrue(input_path.is_file(), f"Missing {input_path}")
        content = input_path.read_text()
        self.assertIn("touch", content)
        self.assertIn("tablet", content)
        self.assertIn('map-to-output "eDP-1"', content)

    def test_niri_config_switch_events(self):
        """Verify config.kdl specifies switch-events for tablet mode transitions."""
        config_path = REPO_ROOT / "files" / "niri" / "etc" / "skel" / ".config" / "niri" / "config.kdl"
        self.assertTrue(config_path.is_file(), f"Missing {config_path}")
        content = config_path.read_text()
        self.assertIn("switch-events", content)
        self.assertIn("tablet-mode-on", content)
        self.assertIn("tablet-mode-off", content)


if __name__ == "__main__":
    unittest.main()
