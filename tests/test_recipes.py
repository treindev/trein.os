import unittest
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestRecipes(unittest.TestCase):
    def setUp(self):
        self.recipes_dir = REPO_ROOT / "recipes"
        self.recipe_path = self.recipes_dir / "recipe.yml"
        self.readme_path = REPO_ROOT / "README.md"

    def test_single_recipe_metadata(self):
        self.assertTrue(self.recipe_path.is_file(), f"Missing {self.recipe_path}")
        top_level_recipes = sorted(p.name for p in self.recipes_dir.glob("*.yml"))
        self.assertEqual(top_level_recipes, ["recipe.yml"])

        data = yaml.safe_load(self.recipe_path.read_text())
        self.assertEqual(data.get("name"), "trein.os")
        self.assertEqual(data.get("base-image"), "ghcr.io/ublue-os/kinoite-main")
        self.assertEqual(data.get("image-version"), 45)
        self.assertIn("Fedora 45", data.get("description", ""))
        self.assertNotIn("alt-tags", data, "alt-tags must be omitted so BlueBuild publishes :latest and :45")

    def test_readme_documents_fedora_45(self):
        self.assertTrue(self.readme_path.is_file(), f"Missing {self.readme_path}")
        content = self.readme_path.read_text()
        self.assertIn("Fedora Atomic 45", content)

    def test_build_workflow_matrix_builds_single_recipe(self):
        workflow_path = REPO_ROOT / ".github" / "workflows" / "build.yml"
        self.assertTrue(workflow_path.is_file(), f"Missing {workflow_path}")
        data = yaml.safe_load(workflow_path.read_text())
        recipes = data.get("jobs", {}).get("bluebuild", {}).get("strategy", {}).get("matrix", {}).get("recipe", [])
        self.assertEqual(
            recipes,
            ["recipe.yml"],
            "build.yml matrix must build only recipe.yml",
        )


if __name__ == "__main__":
    unittest.main()
