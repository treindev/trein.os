import unittest
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestBootloaderConfiguration(unittest.TestCase):
    def setUp(self):
        self.grub_dropin_path = (
            REPO_ROOT / "files" / "base" / "etc" / "default" / "grub.d" / "00-fastboot.cfg"
        )

    def test_grub_dropin_exists(self):
        self.assertTrue(
            self.grub_dropin_path.is_file(),
            f"GRUB fastboot drop-in missing at {self.grub_dropin_path}",
        )

    def test_grub_dropin_configuration(self):
        content = self.grub_dropin_path.read_text()
        self.assertIn("GRUB_TIMEOUT=0", content, "GRUB_TIMEOUT must be set to 0")
        self.assertIn(
            "GRUB_TIMEOUT_STYLE=hidden",
            content,
            "GRUB_TIMEOUT_STYLE must be set to hidden",
        )


class TestAppStreamTimer(unittest.TestCase):
    def setUp(self):
        self.timer_path = (
            REPO_ROOT
            / "files"
            / "base"
            / "usr"
            / "lib"
            / "systemd"
            / "system"
            / "fedora-atomic-desktop-appstream-cache-refresh.timer"
        )

    def test_timer_exists(self):
        self.assertTrue(
            self.timer_path.is_file(),
            f"AppStream refresh timer missing at {self.timer_path}",
        )

    def test_timer_configuration(self):
        content = self.timer_path.read_text()
        self.assertIn("[Timer]", content)
        self.assertIn("OnBootSec=10min", content)
        self.assertIn("OnUnitActiveSec=1d", content)
        self.assertIn("WantedBy=timers.target", content)
        self.assertNotIn(
            "Persistent=",
            content,
            "Monotonic timer should not specify Persistent=true",
        )


class TestBaseModuleSystemdIntegration(unittest.TestCase):
    def setUp(self):
        self.base_module_path = REPO_ROOT / "recipes" / "base" / "common.yml"

    def test_base_module_systemd_boot_optimizations(self):
        self.assertTrue(
            self.base_module_path.is_file(),
            f"Base Module not found at {self.base_module_path}",
        )
        content = yaml.safe_load(self.base_module_path.read_text())
        modules = content.get("modules", [])

        systemd_modules = [m for m in modules if m.get("type") == "systemd"]
        self.assertTrue(
            len(systemd_modules) > 0,
            "No systemd module found in base module common.yml",
        )

        system_section = None
        for module in systemd_modules:
            if "system" in module:
                system_section = module["system"]
                break

        self.assertIsNotNone(
            system_section,
            "systemd module in base module common.yml must define a 'system' section",
        )

        disabled_services = system_section.get("disabled", [])
        self.assertIn(
            "NetworkManager-wait-online.service",
            disabled_services,
            "NetworkManager-wait-online.service must be disabled",
        )
        self.assertIn(
            "rpc-statd-notify.service",
            disabled_services,
            "rpc-statd-notify.service must be disabled",
        )
        self.assertIn(
            "fedora-atomic-desktop-appstream-cache-refresh.service",
            disabled_services,
            "fedora-atomic-desktop-appstream-cache-refresh.service must be disabled",
        )

        enabled_services = system_section.get("enabled", [])
        self.assertIn(
            "fedora-atomic-desktop-appstream-cache-refresh.timer",
            enabled_services,
            "fedora-atomic-desktop-appstream-cache-refresh.timer must be enabled",
        )


if __name__ == "__main__":
    unittest.main()
