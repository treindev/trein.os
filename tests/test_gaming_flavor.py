import unittest
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestGamingFlavor(unittest.TestCase):
    def setUp(self):
        self.gaming_module_path = REPO_ROOT / "recipes" / "base" / "gaming.yml"
        self.sysctl_gaming_path = (
            REPO_ROOT / "files" / "base" / "usr" / "lib" / "sysctl.d" / "80-gaming.conf"
        )
        self.greetd_module_path = REPO_ROOT / "recipes" / "base" / "greetd.yml"
        self.niri_module_path = REPO_ROOT / "recipes" / "base" / "niri.yml"
        self.common_module_path = REPO_ROOT / "recipes" / "base" / "common.yml"
        self.gaming_recipe_path = REPO_ROOT / "recipes" / "gaming-nvidia.yml"
        self.niri_nvidia_recipe_path = REPO_ROOT / "recipes" / "niri-nvidia.yml"
        self.niri_recipe_path = REPO_ROOT / "recipes" / "niri.yml"
        self.build_workflow_path = REPO_ROOT / ".github" / "workflows" / "build.yml"

    def _get_from_files(self, recipe_path: Path) -> list[str]:
        recipe = yaml.safe_load(recipe_path.read_text())
        modules = recipe.get("modules", [])
        return [m.get("from-file") for m in modules if "from-file" in m]

    def _get_dnf_packages(self, module_path: Path) -> list[str]:
        content = yaml.safe_load(module_path.read_text())
        modules = content.get("modules", [])
        packages = []
        for mod in modules:
            if mod.get("type") == "dnf":
                packages.extend(mod.get("install", {}).get("packages", []))
        return packages

    def _get_enabled_services(self, module_path: Path, scope: str = "system") -> list[str]:
        content = yaml.safe_load(module_path.read_text())
        modules = content.get("modules", [])
        enabled = []
        for mod in modules:
            if mod.get("type") == "systemd":
                enabled.extend(mod.get(scope, {}).get("enabled", []))
        return enabled

    def test_gaming_base_module_packages_and_service(self):
        self.assertTrue(self.gaming_module_path.is_file(), f"Missing {self.gaming_module_path}")
        packages = self._get_dnf_packages(self.gaming_module_path)
        for pkg in ["steam", "gamemode", "gamescope", "steam-devices"]:
            self.assertIn(pkg, packages, f"'{pkg}' must be installed in recipes/base/gaming.yml")

        user_enabled = self._get_enabled_services(self.gaming_module_path, scope="user")
        self.assertIn(
            "gamemoded.service",
            user_enabled,
            "gamemoded.service must be enabled under systemd.user.enabled in recipes/base/gaming.yml",
        )

    def test_gaming_sysctl_dropin(self):
        self.assertTrue(self.sysctl_gaming_path.is_file(), f"Missing {self.sysctl_gaming_path}")
        content = self.sysctl_gaming_path.read_text()
        self.assertIn("vm.max_map_count = 2147483642", content)
        self.assertIn("fs.inotify.max_user_watches = 524288", content)
        self.assertIn("fs.inotify.max_user_instances = 8192", content)

    def test_greetd_module_decoupled_from_niri(self):
        self.assertTrue(self.greetd_module_path.is_file(), f"Missing {self.greetd_module_path}")
        greetd_packages = self._get_dnf_packages(self.greetd_module_path)
        self.assertIn("dms-greeter", greetd_packages, "dms-greeter must be installed in base/greetd.yml")

        enabled_system = self._get_enabled_services(self.greetd_module_path, scope="system")
        self.assertIn("greetd.service", enabled_system)

        self.assertTrue(self.niri_module_path.is_file(), f"Missing {self.niri_module_path}")
        niri_packages = self._get_dnf_packages(self.niri_module_path)
        self.assertNotIn("dms-greeter", niri_packages, "dms-greeter must be decoupled from base/niri.yml")

        niri_enabled_system = self._get_enabled_services(self.niri_module_path, scope="system")
        self.assertNotIn("greetd.service", niri_enabled_system, "greetd.service must not be enabled in base/niri.yml")

        niri_nvidia_files = self._get_from_files(self.niri_nvidia_recipe_path)
        self.assertIn("base/gaming.yml", niri_nvidia_files)
        self.assertIn("base/greetd.yml", niri_nvidia_files)

        niri_files = self._get_from_files(self.niri_recipe_path)
        self.assertIn("base/gaming.yml", niri_files)
        self.assertIn("base/greetd.yml", niri_files)

    def test_common_retains_hardware_control_and_flatpaks(self):
        common_packages = self._get_dnf_packages(self.common_module_path)
        self.assertIn("ddcutil", common_packages)
        self.assertIn("tuned-ppd", common_packages)
        self.assertNotIn("power-profiles-daemon", common_packages)

        common_content = yaml.safe_load(self.common_module_path.read_text())
        flatpak_mods = [
            m for m in common_content.get("modules", []) if m.get("type") == "default-flatpaks"
        ]
        self.assertTrue(len(flatpak_mods) > 0, "default-flatpaks must remain in base/common.yml")

        self.assertFalse((REPO_ROOT / "recipes" / "base" / "hardware-control.yml").exists())
        self.assertFalse((REPO_ROOT / "recipes" / "base" / "flatpaks.yml").exists())
        self.assertFalse((REPO_ROOT / "recipes" / "base" / "flatpaks-steam.yml").exists())

    def test_gaming_nvidia_recipe_structure_and_ci(self):
        self.assertTrue(self.gaming_recipe_path.is_file(), f"Missing {self.gaming_recipe_path}")
        recipe = yaml.safe_load(self.gaming_recipe_path.read_text())

        self.assertEqual(recipe.get("name"), "trein.os")
        self.assertEqual(recipe.get("base-image"), "ghcr.io/ublue-os/kinoite-main")
        self.assertEqual(recipe.get("image-version"), 45)
        self.assertEqual(recipe.get("alt-tags"), ["gaming-nvidia"])
        self.assertEqual(recipe.get("platforms"), ["linux/amd64"])

        from_files = self._get_from_files(self.gaming_recipe_path)
        self.assertEqual(
            from_files,
            [
                "base/common.yml",
                "base/gaming.yml",
                "base/niri.yml",
                "base/nvidia.yml",
            ],
        )
        self.assertNotIn("base/greetd.yml", from_files)

        os_release_mods = [
            m for m in recipe.get("modules", []) if m.get("type") == "os-release"
        ]
        self.assertEqual(len(os_release_mods), 1)
        self.assertEqual(
            os_release_mods[0].get("properties", {}).get("PRETTY_NAME"),
            "trein.os for Gaming Nvidia - Plasma & Niri (FROM Universal Blue Kinoite)",
        )

        workflow = yaml.safe_load(self.build_workflow_path.read_text())
        matrix_recipes = workflow["jobs"]["bluebuild"]["strategy"]["matrix"]["recipe"]
        self.assertIn("gaming-nvidia.yml", matrix_recipes)

    def test_niri_suppresses_xwaylandvideobridge_autostart(self):
        niri_content = yaml.safe_load(self.niri_module_path.read_text())
        script_mods = [m for m in niri_content.get("modules", []) if m.get("type") == "script"]
        snippets = []
        for sm in script_mods:
            snippets.extend(sm.get("snippets", []))
        joined = "\n".join(snippets)
        self.assertIn("/etc/xdg/autostart/org.kde.xwaylandvideobridge.desktop", joined)
        self.assertIn("NotShowIn=niri;", joined)


if __name__ == "__main__":
    unittest.main()
