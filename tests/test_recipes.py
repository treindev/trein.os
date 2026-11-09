import unittest
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestRecipes(unittest.TestCase):
    def setUp(self):
        self.recipes_dir = REPO_ROOT / "recipes"
        self.niri_path = self.recipes_dir / "niri.yml"
        self.niri_nvidia_path = self.recipes_dir / "niri-nvidia.yml"
        self.gaming_nvidia_path = self.recipes_dir / "gaming-nvidia.yml"
        self.readme_path = REPO_ROOT / "README.md"

    def test_niri_recipe_metadata(self):
        self.assertTrue(self.niri_path.is_file(), f"Missing {self.niri_path}")
        data = yaml.safe_load(self.niri_path.read_text())
        self.assertEqual(data.get("name"), "trein.os")
        self.assertEqual(data.get("base-image"), "ghcr.io/ublue-os/base-main")
        self.assertEqual(data.get("image-version"), 45)
        self.assertIn("Fedora 45", data.get("description", ""))
        self.assertEqual(data.get("alt-tags"), ["niri"])

    def test_niri_nvidia_recipe_metadata(self):
        self.assertTrue(self.niri_nvidia_path.is_file(), f"Missing {self.niri_nvidia_path}")
        data = yaml.safe_load(self.niri_nvidia_path.read_text())
        self.assertEqual(data.get("name"), "trein.os")
        self.assertEqual(data.get("base-image"), "ghcr.io/ublue-os/base-main")
        self.assertEqual(data.get("image-version"), 45)
        self.assertIn("Fedora 45", data.get("description", ""))
        self.assertEqual(data.get("alt-tags"), ["niri-nvidia"])

    def test_gaming_nvidia_recipe_metadata(self):
        self.assertTrue(self.gaming_nvidia_path.is_file(), f"Missing {self.gaming_nvidia_path}")
        data = yaml.safe_load(self.gaming_nvidia_path.read_text())
        self.assertEqual(data.get("name"), "trein.os")
        self.assertEqual(data.get("base-image"), "ghcr.io/ublue-os/kinoite-main")
        self.assertEqual(data.get("image-version"), 45)
        self.assertIn("Fedora 45", data.get("description", ""))
        self.assertEqual(data.get("alt-tags"), ["gaming-nvidia"])

    def test_readme_documents_fedora_45(self):
        self.assertTrue(self.readme_path.is_file(), f"Missing {self.readme_path}")
        content = self.readme_path.read_text()
        self.assertIn("Fedora Atomic 45", content)


if __name__ == "__main__":
    unittest.main()
