import os
import stat
import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestMonctl(unittest.TestCase):
    def setUp(self):
        self.monctl_path = REPO_ROOT / "files" / "base" / "usr" / "bin" / "monctl"
        self.assertTrue(self.monctl_path.is_file(), f"Missing {self.monctl_path}")
        self.namespace = {}
        exec(self.monctl_path.read_text(), self.namespace)

    def test_monctl_executable_and_permissions(self):
        """Verify monctl exists and has executable permissions."""
        mode = self.monctl_path.stat().st_mode
        self.assertTrue(bool(mode & stat.S_IXUSR), "monctl must be executable by user")

    def test_monctl_import_and_constants(self):
        """Verify monctl defines hardware bus targets and VCP presets."""
        self.assertIn("DELL_U3225QE_BUS", self.namespace)
        self.assertEqual(self.namespace["DELL_U3225QE_BUS"], 6)
        self.assertIn("DELL_P2425D_BUS", self.namespace)
        self.assertEqual(self.namespace["DELL_P2425D_BUS"], 4)

        presets = self.namespace.get("COLOR_PRESETS", {})
        self.assertEqual(presets.get("srgb"), 0x01)
        self.assertEqual(presets.get("p3"), 0x05)
        self.assertEqual(presets.get("6500k"), 0x05)
        self.assertEqual(presets.get("5000k"), 0x04)
        self.assertEqual(presets.get("7500k"), 0x06)
        self.assertEqual(presets.get("9300k"), 0x08)

    def test_compute_brightness_target(self):
        """Verify brightness calculation for absolute, relative positive, and relative negative steps."""
        compute_brightness = self.namespace["compute_brightness"]

        # Absolute values
        self.assertEqual(compute_brightness(current=50, arg="75"), 75)
        self.assertEqual(compute_brightness(current=50, arg="150"), 100)
        self.assertEqual(compute_brightness(current=50, arg="-10", is_relative=False), 0)

        # Relative values
        self.assertEqual(compute_brightness(current=65, arg="+5"), 70)
        self.assertEqual(compute_brightness(current=65, arg="-5"), 60)
        self.assertEqual(compute_brightness(current=98, arg="+5"), 100)
        self.assertEqual(compute_brightness(current=3, arg="-5"), 0)

    def test_toggle_preset_logic(self):
        """Verify toggling presets alternates between sRGB (0x01) and DCI-P3 (0x05)."""
        get_next_preset = self.namespace["get_next_preset"]

        self.assertEqual(get_next_preset(current_code=0x01), "p3")
        self.assertEqual(get_next_preset(current_code=0x05), "srgb")
        self.assertEqual(get_next_preset(current_code=0x04), "srgb")

    @patch("subprocess.run")
    def test_set_brightness_concurrent_dispatch(self, mock_run):
        """Verify brightness dispatch triggers internal and external hardware commands."""
        set_all_brightness = self.namespace["set_all_brightness"]
        mock_run.return_value = MagicMock(returncode=0, stdout="")

        with patch("os.path.exists", return_value=True), patch.dict(self.namespace, {"is_bus_available": lambda bus: True}):
            success = set_all_brightness(75)

        self.assertTrue(success)
        called_cmds = [call.args[0] for call in mock_run.call_args_list]

        # Should execute ddcutil on bus 6, bus 4, and backlight/dms
        bus6_calls = [cmd for cmd in called_cmds if "ddcutil" in cmd and "--bus" in cmd and "6" in cmd]
        bus4_calls = [cmd for cmd in called_cmds if "ddcutil" in cmd and "--bus" in cmd and "4" in cmd]
        backlight_calls = [
            cmd for cmd in called_cmds if "brightnessctl" in cmd or ("dms" in cmd and "brightness" in cmd)
        ]

        self.assertTrue(len(bus6_calls) > 0, "Expected ddcutil call on bus 6")
        self.assertTrue(len(bus4_calls) > 0, "Expected ddcutil call on bus 4")
        self.assertTrue(len(backlight_calls) > 0, "Expected brightnessctl or dms backlight call")

    @patch("subprocess.run")
    def test_set_preset_dispatch(self, mock_run):
        """Verify setting preset executes ddcutil setvcp 14 on bus 6 and sends notification."""
        set_preset = self.namespace["set_preset"]
        mock_run.return_value = MagicMock(returncode=0, stdout="")

        with patch("os.path.exists", return_value=True), patch.dict(self.namespace, {"is_bus_available": lambda bus: True}), patch("sys.stdout"):
            success = set_preset("srgb")

        self.assertTrue(success)
        called_cmds = [call.args[0] for call in mock_run.call_args_list]

        preset_calls = [
            cmd
            for cmd in called_cmds
            if "ddcutil" in cmd and "--bus" in cmd and "6" in cmd and "setvcp" in cmd and ("0x14" in cmd or "14" in cmd)
        ]
        self.assertTrue(len(preset_calls) > 0, "Expected ddcutil setvcp 0x14 call on bus 6")
        self.assertEqual(preset_calls[0][-1], "0x01")

    @patch("subprocess.run")
    def test_graceful_missing_devices(self, mock_run):
        """Verify monctl handles missing /dev/i2c devices gracefully without throwing."""
        set_all_brightness = self.namespace["set_all_brightness"]
        mock_run.return_value = MagicMock(returncode=0, stdout="")

        # Simulate buses missing / disconnected (e.g. mobile mode)
        with patch.dict(self.namespace, {"is_bus_available": lambda bus: False}):
            success = set_all_brightness(50)

        self.assertTrue(success)
        called_cmds = [call.args[0] for call in mock_run.call_args_list]
        ddc_calls = [cmd for cmd in called_cmds if "ddcutil" in cmd]
        self.assertEqual(len(ddc_calls), 0, "Should not invoke ddcutil when bus paths do not exist")

    def test_drm_connector_detection(self):
        """Verify is_bus_available checks DRM connector status."""
        is_bus_available = self.namespace["is_bus_available"]

        # When DP-2 is connected and HDMI-A-1 is disconnected
        with patch("os.path.exists", return_value=True), patch.dict(
            self.namespace, {"is_connector_connected": lambda conn: conn == "DP-2"}
        ):
            self.assertTrue(is_bus_available(6))
            self.assertFalse(is_bus_available(4))

    def test_niri_binds_configuration(self):
        """Verify Niri binds.kdl configures monctl and dms/binds.kdl contains no duplicate brightness keys."""
        binds_path = REPO_ROOT / "files" / "niri" / "etc" / "skel" / ".config" / "niri" / "binds.kdl"
        dms_binds_path = (
            REPO_ROOT / "files" / "niri" / "etc" / "skel" / ".config" / "niri" / "dms" / "binds.kdl"
        )
        home_path = (
            REPO_ROOT / "files" / "niri" / "etc" / "skel" / ".config" / "niri" / "display" / "home.kdl"
        )

        self.assertTrue(binds_path.is_file(), f"Missing {binds_path}")
        self.assertTrue(dms_binds_path.is_file(), f"Missing {dms_binds_path}")
        self.assertTrue(home_path.is_file(), f"Missing {home_path}")

        binds_content = binds_path.read_text()
        dms_content = dms_binds_path.read_text()
        home_content = home_path.read_text()

        # Check binds.kdl has monctl brightness and preset toggle
        self.assertIn('spawn "monctl" "brightness" "+5"', binds_content)
        self.assertIn('spawn "monctl" "brightness" "-5"', binds_content)
        self.assertIn('spawn "monctl" "preset" "toggle"', binds_content)

        # Check dms/binds.kdl does NOT duplicate XF86MonBrightness keys
        self.assertNotIn("XF86MonBrightnessUp", dms_content)
        self.assertNotIn("XF86MonBrightnessDown", dms_content)

        # Check home.kdl documents the 120Hz vs 4K 60Hz mode trade-off
        self.assertIn("119.998", home_content)
        self.assertIn("3840x2160", home_content)


if __name__ == "__main__":
    unittest.main()
