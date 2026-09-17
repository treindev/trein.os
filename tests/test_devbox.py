import configparser
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def create_mock_distrobox(tmpdir, container_exists=True):
    mock_bin = Path(tmpdir) / "distrobox"
    log_file = Path(tmpdir) / "distrobox.log"
    container_output = (
        'echo "devbox | running | registry.fedoraproject.org/fedora-toolbox:latest"'
        if container_exists
        else "true"
    )
    mock_bin.write_text(f"""#!/usr/bin/env bash
echo "$@" >> "{log_file}"
if [ "$1" = "list" ]; then
    {container_output}
fi
exit 0
""")
    mock_bin.chmod(0o755)
    return mock_bin, log_file


class TestDevboxManifest(unittest.TestCase):
    def setUp(self):
        self.manifest_path = REPO_ROOT / "files" / "base" / "etc" / "distrobox" / "distrobox.ini"

    def test_manifest_file_exists(self):
        self.assertTrue(self.manifest_path.is_file(), f"Manifest not found at {self.manifest_path}")

    def test_manifest_configuration(self):
        if not self.manifest_path.is_file():
            self.skipTest("Manifest file does not exist yet")

        content = self.manifest_path.read_text()
        config = configparser.ConfigParser(strict=False, interpolation=None)
        config.read_string(content)

        self.assertIn("devbox", config.sections(), "Section [devbox] missing in distrobox.ini")
        devbox = config["devbox"]

        # Base image
        self.assertEqual(
            devbox.get("image"),
            "registry.fedoraproject.org/fedora-toolbox:latest",
            "Image must be registry.fedoraproject.org/fedora-toolbox:latest"
        )

        # Nvidia GPU forwarding
        self.assertEqual(devbox.get("nvidia"), "true", "Nvidia GPU forwarding must be enabled")

        # Additional packages
        packages = devbox.get("additional_packages", "")
        for pkg in ["git", "fish", "curl", "code"]:
            self.assertIn(pkg, packages, f"Package {pkg} missing in additional_packages")

        # pre_init_hooks (VS Code repo & GPG key, with idempotency check)
        self.assertIn("pre_init_hooks", devbox)
        pre_hooks = devbox.get("pre_init_hooks")
        self.assertIn("packages.microsoft.com", pre_hooks, "Microsoft repo/key must be in pre_init_hooks")
        self.assertIn("vscode", pre_hooks, "VS Code repository config must be in pre_init_hooks")
        self.assertIn("test -f", pre_hooks, "pre_init_hooks must contain an idempotency check for offline safety")

        # init_hooks (Zed & Antigravity)
        self.assertIn("init_hooks", devbox)
        init_hooks = devbox.get("init_hooks")
        self.assertIn("zed.dev/install.sh", init_hooks, "Zed installation hook missing in init_hooks")
        self.assertIn("antigravity", init_hooks, "Antigravity installation hook missing in init_hooks")

        # Exported apps and binaries
        apps = devbox.get("exported_apps", "").strip('"').split()
        self.assertIn("code", apps)
        self.assertIn("zed", apps)
        self.assertEqual(devbox.get("exported_bins", "").strip(' "'), "/usr/bin/code")


class TestDevboxWrapper(unittest.TestCase):
    def setUp(self):
        self.wrapper_path = REPO_ROOT / "files" / "base" / "usr" / "bin" / "devbox"
        self.completion_path = REPO_ROOT / "files" / "base" / "usr" / "share" / "fish" / "vendor_completions.d" / "devbox.fish"

    def test_wrapper_exists_and_executable(self):
        self.assertTrue(self.wrapper_path.is_file(), f"Wrapper script missing at {self.wrapper_path}")
        self.assertTrue(os.access(self.wrapper_path, os.X_OK), f"Wrapper script {self.wrapper_path} is not executable")

    def test_wrapper_syntax(self):
        if not self.wrapper_path.is_file():
            self.skipTest("Wrapper script does not exist yet")
        res = subprocess.run(["bash", "-n", str(self.wrapper_path)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Bash syntax error in wrapper: {res.stderr}")

    def test_fish_completion_exists(self):
        self.assertTrue(self.completion_path.is_file(), f"Fish completion missing at {self.completion_path}")
        content = self.completion_path.read_text()
        self.assertIn("distrobox enter", content)

    def test_wrapper_behavior_runs_enter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _, log_file = create_mock_distrobox(tmpdir, container_exists=True)
            env = os.environ.copy()
            env["PATH"] = f"{tmpdir}:{env['PATH']}"

            res = subprocess.run([str(self.wrapper_path)], env=env, capture_output=True, text=True)
            self.assertEqual(res.returncode, 0)
            calls = log_file.read_text().strip().splitlines()
            self.assertIn("list", calls[0])
            self.assertEqual(calls[1], "enter devbox")

    def test_wrapper_behavior_forwards_arguments(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _, log_file = create_mock_distrobox(tmpdir, container_exists=True)
            env = os.environ.copy()
            env["PATH"] = f"{tmpdir}:{env['PATH']}"

            res = subprocess.run([str(self.wrapper_path), "code", "/home/project"], env=env, capture_output=True, text=True)
            self.assertEqual(res.returncode, 0)
            calls = log_file.read_text().strip().splitlines()
            self.assertEqual(calls[1], "enter devbox -- code /home/project")

    def test_wrapper_behavior_when_container_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _, log_file = create_mock_distrobox(tmpdir, container_exists=False)
            env = os.environ.copy()
            env["PATH"] = f"{tmpdir}:{env['PATH']}"
            env["DEVBOX_MANIFEST"] = str(REPO_ROOT / "files" / "base" / "etc" / "distrobox" / "distrobox.ini")

            res = subprocess.run([str(self.wrapper_path)], env=env, capture_output=True, text=True)
            self.assertEqual(res.returncode, 0)
            calls = log_file.read_text().strip().splitlines()
            self.assertIn("list", calls[0])
            self.assertIn("assemble create", calls[1])
            self.assertEqual(calls[2], "enter devbox")

    def test_wrapper_assemble_subcommand(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _, log_file = create_mock_distrobox(tmpdir, container_exists=False)
            env = os.environ.copy()
            env["PATH"] = f"{tmpdir}:{env['PATH']}"
            env["DEVBOX_MANIFEST"] = str(REPO_ROOT / "files" / "base" / "etc" / "distrobox" / "distrobox.ini")

            res = subprocess.run([str(self.wrapper_path), "assemble"], env=env, capture_output=True, text=True)
            self.assertEqual(res.returncode, 0)
            calls = log_file.read_text().strip().splitlines()
            self.assertIn("list", calls[0])
            self.assertIn("assemble create", calls[1])
            # Should not enter after explicit assemble command
            self.assertEqual(len(calls), 2)


class TestDevboxUpdate(unittest.TestCase):
    def setUp(self):
        self.update_script_path = REPO_ROOT / "files" / "base" / "usr" / "libexec" / "devbox-update"
        self.timer_path = REPO_ROOT / "files" / "base" / "usr" / "lib" / "systemd" / "user" / "devbox-update.timer"
        self.service_path = REPO_ROOT / "files" / "base" / "usr" / "lib" / "systemd" / "user" / "devbox-update.service"

    def test_update_script_exists_and_executable(self):
        self.assertTrue(self.update_script_path.is_file(), f"Update script missing at {self.update_script_path}")
        self.assertTrue(os.access(self.update_script_path, os.X_OK), f"Update script {self.update_script_path} is not executable")

    def test_update_script_syntax(self):
        if not self.update_script_path.is_file():
            self.skipTest("Update script does not exist yet")
        res = subprocess.run(["bash", "-n", str(self.update_script_path)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Bash syntax error in update script: {res.stderr}")

    def test_timer_configuration(self):
        self.assertTrue(self.timer_path.is_file(), f"Timer file missing at {self.timer_path}")
        content = self.timer_path.read_text()
        self.assertIn("[Timer]", content)
        self.assertIn("OnStartupSec=5m", content)
        self.assertIn("WantedBy=timers.target", content)
        self.assertNotIn("Persistent=", content, "Monotonic timer should not set Persistent=true")

    def test_service_configuration(self):
        self.assertTrue(self.service_path.is_file(), f"Service file missing at {self.service_path}")
        content = self.service_path.read_text()
        self.assertIn("[Service]", content)
        self.assertIn("Type=oneshot", content)
        self.assertIn("ExecStart=/usr/libexec/devbox-update", content)
        self.assertIn("After=init-devbox.service", content)
        self.assertNotIn("WantedBy=", content, "Timer-activated service should not have [Install] WantedBy")

    def test_update_behavior_upgrades_and_notifies(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _, log_distrobox = create_mock_distrobox(tmpdir, container_exists=True)
            mock_notify = Path(tmpdir) / "notify-send"
            log_notify = Path(tmpdir) / "notify.log"

            mock_notify.write_text(f"""#!/usr/bin/env bash
echo "$@" >> "{log_notify}"
exit 0
""")
            mock_notify.chmod(0o755)

            env = os.environ.copy()
            env["PATH"] = f"{tmpdir}:{env['PATH']}"

            res = subprocess.run([str(self.update_script_path)], env=env, capture_output=True, text=True)
            self.assertEqual(res.returncode, 0)

            dbox_calls = log_distrobox.read_text().strip().splitlines()
            self.assertIn("list", dbox_calls[0])
            self.assertEqual(dbox_calls[1], "upgrade devbox")

            notify_calls = log_notify.read_text().strip().splitlines()
            self.assertTrue(any("-u low" in c for c in notify_calls), "Notification must be low urgency")

    def test_update_behavior_skips_when_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _, log_distrobox = create_mock_distrobox(tmpdir, container_exists=False)
            env = os.environ.copy()
            env["PATH"] = f"{tmpdir}:{env['PATH']}"

            res = subprocess.run([str(self.update_script_path)], env=env, capture_output=True, text=True)
            self.assertEqual(res.returncode, 0)

            dbox_calls = log_distrobox.read_text().strip().splitlines()
            self.assertEqual(len(dbox_calls), 1)
            self.assertIn("list", dbox_calls[0])


class TestSystemIntegration(unittest.TestCase):
    def setUp(self):
        self.init_service_path = REPO_ROOT / "files" / "base" / "usr" / "lib" / "systemd" / "user" / "init-devbox.service"
        self.recipe_path = REPO_ROOT / "recipes" / "base" / "common.yml"

    def test_init_devbox_service_uses_assemble(self):
        content = self.init_service_path.read_text()
        self.assertIn("devbox assemble", content, "init-devbox.service must call devbox assemble")
        self.assertIn("Description=Initialize Devbox", content, "init-devbox.service must use domain term Devbox")

    def test_recipe_enables_devbox_timer(self):
        content = self.recipe_path.read_text()
        self.assertIn("devbox-update.timer", content, "devbox-update.timer must be enabled in recipes/base/common.yml")


if __name__ == "__main__":
    unittest.main()
