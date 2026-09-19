import unittest
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestServiceCleanup(unittest.TestCase):
    def test_niri_recipe_files_module_syntax(self):
        niri_module_path = REPO_ROOT / "recipes" / "base" / "niri.yml"
        self.assertTrue(niri_module_path.is_file(), f"Missing {niri_module_path}")
        content = yaml.safe_load(niri_module_path.read_text())
        files_modules = [m for m in content.get("modules", []) if m.get("type") == "files"]
        self.assertTrue(len(files_modules) > 0, "No files module found in recipes/base/niri.yml")

        for fm in files_modules:
            files_list = fm.get("files", [])
            self.assertTrue(len(files_list) > 0, "files module has empty files list")
            for item in files_list:
                self.assertIsInstance(item, dict, f"Expected mapping in files list, got {type(item)}")
                self.assertIn("source", item, f"Mapping entry missing 'source': {item}")
                self.assertIn("destination", item, f"Mapping entry missing 'destination': {item}")

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

    def test_niri_config_cleaned_startup(self):
        config_path = REPO_ROOT / "files" / "niri" / "etc" / "skel" / ".config" / "niri" / "config.kdl"
        self.assertTrue(config_path.is_file(), f"Missing {config_path}")
        content = config_path.read_text()

        self.assertNotIn("cliphist", content, "cliphist spawn must be removed from config.kdl")
        self.assertNotIn('spawn-at-startup "dms" "run"', content, "redundant dms run spawn must be removed from config.kdl")


if __name__ == "__main__":
    unittest.main()
