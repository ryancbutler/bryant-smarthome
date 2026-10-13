import contextlib
import io
import json
import unittest
from unittest.mock import patch

from bryant_smarthome.cli import main


class EquipmentStatusTests(unittest.TestCase):
    @patch("bryant_smarthome.cli.load_environment", return_value={})
    @patch("bryant_smarthome.cli.credentials", return_value={"token": "MOCK", "username": "mock"})
    @patch("bryant_smarthome.cli.Client")
    def test_system_preserves_conflicting_mode_and_equipment_reports(self, client, credentials, environment):
        reported = {
            "status": {
                "mode": "off",
                "odu": {"opstat": "on", "opmode": "cooling", "comprpm": "na", "linevolt": None},
                "idu": {"opstat": "off", "cfm": "812", "blwrpm": "770"},
                "zones": [{"id": "1", "fan": "off"}],
            },
            "config": {"mode": "cool"},
        }
        client.return_value.execute.return_value = reported
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["--non-interactive", "system", "MOCK_SERIAL"]), 0)
        self.assertEqual(json.loads(output.getvalue()), reported)
        request = client.return_value.execute.call_args.args[0]
        self.assertEqual(request["variables"], {"serial": "MOCK_SERIAL"})
        self.assertIn("odu { type opstat opmode iducfm blwrpm comprpm linevolt }", request["query"])
        self.assertIn("idu { type opstat cfm iducfm blwrpm }", request["query"])
        self.assertIn("localTime localTimeOffset utcTime wcTime", request["query"])
        self.assertNotIn("mutation", request["query"])
        client.return_value.execute.assert_called_once()

    @patch("bryant_smarthome.cli.load_environment", return_value={})
    @patch("bryant_smarthome.cli.credentials", return_value={"token": "MOCK", "username": "mock"})
    @patch("bryant_smarthome.cli.Client")
    def test_systems_keeps_unavailable_equipment_unavailable(self, client, credentials, environment):
        reported = {"infinitySystems": [{"status": {"odu": None, "idu": None}}]}
        client.return_value.execute.return_value = reported
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["--non-interactive", "systems"]), 0)
        self.assertEqual(json.loads(output.getvalue()), reported)
        request = client.return_value.execute.call_args.args[0]
        self.assertIn("odu { type opstat opmode", request["query"])
        self.assertIn("idu { type opstat", request["query"])
        self.assertNotIn("mutation", request["query"])


if __name__ == "__main__":
    unittest.main()
