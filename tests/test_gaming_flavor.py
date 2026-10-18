import unittest
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestGamingFlavor(unittest.TestCase):
    def setUp(self):
        self.gaming_recipe_path = REPO_ROOT / "recipes" / "gaming-nvidia.yml"
        self.greetd_module_path = REPO_ROOT / "recipes" / "base" / "greetd.yml"
        self.niri_module_path = REPO_ROOT / "recipes" / "base" / "niri.yml"
        self.common_module_path = REPO_ROOT / "recipes" / "base" / "common.yml"
        self.flatpaks_module_path = REPO_ROOT / "recipes" / "base" / "flatpaks.yml"
        self.flatpaks_steam_module_path = REPO_ROOT / "recipes" / "base" / "flatpaks-steam.yml"
        self.hardware_control_module_path = REPO_ROOT / "recipes" / "base" / "hardware-control.yml"
        self.niri_nvidia_recipe_path = REPO_ROOT / "recipes" / "niri-nvidia.yml"
        self.niri_recipe_path = REPO_ROOT / "recipes" / "niri.yml"
        self.build_workflow_path = REPO_ROOT / ".github" / "workflows" / "build.yml"

    def _get_from_files(self, recipe_path: Path) -> list[str]:
        recipe = yaml.safe_load(recipe_path.read_text())
        modules = recipe.get("modules", [])
        return [m.get("from-file") for m in modules if "from-file" in m]

    def _get_flatpak_install_list(self, module_path: Path) -> list[str]:
        content = yaml.safe_load(module_path.read_text())
        modules = content.get("modules", [])
        for mod in modules:
            if mod.get("type") == "default-flatpaks":
                configs = mod.get("configurations", [])
                if configs:
                    return configs[0].get("install", [])
        return []

    def _get_dnf_packages(self, module_path: Path) -> list[str]:
        content = yaml.safe_load(module_path.read_text())
        modules = content.get("modules", [])
        packages = []
        for mod in modules:
            if mod.get("type") == "dnf":
                packages.extend(mod.get("install", {}).get("packages", []))
        return packages

    def test_gaming_nvidia_recipe_structure(self):
        self.assertTrue(self.gaming_recipe_path.is_file(), f"Missing {self.gaming_recipe_path}")
        recipe = yaml.safe_load(self.gaming_recipe_path.read_text())

        self.assertEqual(recipe.get("name"), "trein.os")
        self.assertEqual(recipe.get("base-image"), "ghcr.io/ublue-os/bazzite-nvidia")
        self.assertEqual(recipe.get("image-version"), "stable")
        self.assertIn("gaming-nvidia", recipe.get("alt-tags", []))
        self.assertEqual(recipe.get("platforms"), ["linux/amd64"])

        from_files = self._get_from_files(self.gaming_recipe_path)

        # Must include common, flatpaks (non-steam), and niri
        self.assertIn("base/common.yml", from_files)
        self.assertIn("base/flatpaks.yml", from_files)
        self.assertIn("base/niri.yml", from_files)

        # Must NOT include greetd (uses SDDM), akmods nvidia (in Bazzite), flatpak steam (in Bazzite),
        # or hardware-control (Bazzite provides tuned-ppd and terra-ddcutil)
        self.assertNotIn("base/greetd.yml", from_files)
        self.assertNotIn("base/nvidia.yml", from_files)
        self.assertNotIn("base/flatpaks-steam.yml", from_files)
        self.assertNotIn("base/hardware-control.yml", from_files)

    def test_greetd_module_decoupled(self):
        self.assertTrue(self.greetd_module_path.is_file(), f"Missing {self.greetd_module_path}")
        greetd_content = yaml.safe_load(self.greetd_module_path.read_text())
        greetd_modules = greetd_content.get("modules", [])

        # greetd.yml enables greetd.service
        systemd_mods = [m for m in greetd_modules if m.get("type") == "systemd"]
        self.assertTrue(len(systemd_mods) > 0, "No systemd module in base/greetd.yml")
        enabled_system = systemd_mods[0].get("system", {}).get("enabled", [])
        self.assertIn("greetd.service", enabled_system)

        # niri.yml must NOT enable greetd.service
        self.assertTrue(self.niri_module_path.is_file(), f"Missing {self.niri_module_path}")
        niri_content = yaml.safe_load(self.niri_module_path.read_text())
        niri_modules = niri_content.get("modules", [])
        niri_systemd_mods = [m for m in niri_modules if m.get("type") == "systemd"]
        for sm in niri_systemd_mods:
            enabled = sm.get("system", {}).get("enabled", [])
            self.assertNotIn("greetd.service", enabled, "greetd.service must not be enabled in base/niri.yml")

        # niri-nvidia.yml and niri.yml must include base/greetd.yml
        self.assertIn("base/greetd.yml", self._get_from_files(self.niri_nvidia_recipe_path))
        self.assertIn("base/greetd.yml", self._get_from_files(self.niri_recipe_path))

    def test_flatpaks_modules_decoupled(self):
        self.assertTrue(self.flatpaks_module_path.is_file(), f"Missing {self.flatpaks_module_path}")
        self.assertTrue(self.flatpaks_steam_module_path.is_file(), f"Missing {self.flatpaks_steam_module_path}")

        # common.yml must not contain default-flatpaks
        common_content = yaml.safe_load(self.common_module_path.read_text())
        common_modules = common_content.get("modules", [])
        flatpak_mods = [m for m in common_modules if m.get("type") == "default-flatpaks"]
        self.assertEqual(len(flatpak_mods), 0, "default-flatpaks must be extracted from base/common.yml")

        # flatpaks.yml must not contain Steam
        installed = self._get_flatpak_install_list(self.flatpaks_module_path)
        self.assertNotIn("com.valvesoftware.Steam", installed)
        self.assertIn("org.mozilla.firefox", installed)

        # flatpaks-steam.yml must contain Steam
        steam_installed = self._get_flatpak_install_list(self.flatpaks_steam_module_path)
        self.assertIn("com.valvesoftware.Steam", steam_installed)

        # niri-nvidia and niri must include both flatpak modules
        niri_nvidia_files = self._get_from_files(self.niri_nvidia_recipe_path)
        self.assertIn("base/flatpaks.yml", niri_nvidia_files)
        self.assertIn("base/flatpaks-steam.yml", niri_nvidia_files)

    def test_hardware_control_module_decoupled(self):
        self.assertTrue(self.hardware_control_module_path.is_file(), f"Missing {self.hardware_control_module_path}")

        # hardware-control.yml installs ddcutil and power-profiles-daemon
        hw_packages = self._get_dnf_packages(self.hardware_control_module_path)
        self.assertIn("ddcutil", hw_packages)
        self.assertIn("power-profiles-daemon", hw_packages)

        # common.yml must not contain conflicting ddcutil or power-profiles-daemon
        common_packages = self._get_dnf_packages(self.common_module_path)
        self.assertNotIn("ddcutil", common_packages, "ddcutil conflicts with Bazzite terra-ddcutil")
        self.assertNotIn("power-profiles-daemon", common_packages, "power-profiles-daemon conflicts with Bazzite tuned-ppd")

        # niri-nvidia and niri must include base/hardware-control.yml
        self.assertIn("base/hardware-control.yml", self._get_from_files(self.niri_nvidia_recipe_path))
        self.assertIn("base/hardware-control.yml", self._get_from_files(self.niri_recipe_path))

    def test_ci_matrix_includes_gaming_nvidia(self):
        workflow = yaml.safe_load(self.build_workflow_path.read_text())
        matrix_recipes = workflow["jobs"]["bluebuild"]["strategy"]["matrix"]["recipe"]
        self.assertIn("gaming-nvidia.yml", matrix_recipes)


if __name__ == "__main__":
    unittest.main()
