import unittest
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestServiceCleanup(unittest.TestCase):
    def test_common_recipe_mako_removed(self):
        common_path = REPO_ROOT / "recipes" / "base" / "common.yml"
        self.assertTrue(common_path.is_file(), f"Missing {common_path}")
        content = yaml.safe_load(common_path.read_text())
        modules = content.get("modules", [])

        # Verify mako package is not in dnf install
        dnf_modules = [m for m in modules if m.get("type") == "dnf" and "install" in m]
        for dm in dnf_modules:
            packages = dm["install"].get("packages", [])
            self.assertNotIn("mako", packages, "mako package must not be in dnf install packages")

        # Verify mako.service is not in user enabled
        systemd_modules = [m for m in modules if m.get("type") == "systemd"]
        for sm in systemd_modules:
            user_section = sm.get("user", {})
            user_enabled = user_section.get("enabled", [])
            self.assertNotIn("mako.service", user_enabled, "mako.service must not be enabled under user services")


if __name__ == "__main__":
    unittest.main()
