import subprocess
import unittest
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestContainerTooling(unittest.TestCase):
    def setUp(self):
        self.common_path = REPO_ROOT / "recipes" / "base" / "common.yml"
        self.content = yaml.safe_load(self.common_path.read_text())
        self.modules = self.content.get("modules", [])
        self.fish_conf_path = (
            REPO_ROOT / "files" / "base" / "usr" / "share" / "fish" / "vendor_conf.d" / "podman-socket.fish"
        )
        self.sh_conf_path = REPO_ROOT / "files" / "base" / "etc" / "profile.d" / "podman-socket.sh"

    def test_podman_compose_and_docker_shim_installed(self):
        dnf_modules = [m for m in self.modules if m.get("type") == "dnf" and "install" in m]
        installed = []
        for dm in dnf_modules:
            installed.extend(dm.get("install", {}).get("packages", []))

        self.assertIn("podman-compose", installed, "podman-compose must be installed in recipes/base/common.yml")
        self.assertIn("podman-docker", installed, "podman-docker must be installed in recipes/base/common.yml")

    def test_podman_user_socket_enabled(self):
        systemd_modules = [m for m in self.modules if m.get("type") == "systemd"]
        user_enabled = []
        for sm in systemd_modules:
            user_enabled.extend(sm.get("user", {}).get("enabled", []))

        self.assertIn("podman.socket", user_enabled, "podman.socket must be enabled under systemd.user.enabled")

    def test_podman_socket_env_configs_exist_and_valid(self):
        self.assertTrue(self.fish_conf_path.is_file(), f"Missing {self.fish_conf_path}")
        self.assertTrue(self.sh_conf_path.is_file(), f"Missing {self.sh_conf_path}")

        fish_content = self.fish_conf_path.read_text()
        self.assertIn("DOCKER_HOST", fish_content)
        self.assertIn("podman/podman.sock", fish_content)

        sh_content = self.sh_conf_path.read_text()
        self.assertIn("DOCKER_HOST", sh_content)
        self.assertIn("podman/podman.sock", sh_content)

        res = subprocess.run(["sh", "-n", str(self.sh_conf_path)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"POSIX shell syntax error in {self.sh_conf_path}: {res.stderr}")


if __name__ == "__main__":
    unittest.main()
