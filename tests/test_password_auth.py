import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bryant_smarthome import auth
from bryant_smarthome.client import AuthenticationError
from bryant_smarthome.cli import main


class PasswordAuthenticationTests(unittest.TestCase):
    def call(self, args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    @patch("bryant_smarthome.auth.Client")
    def test_login_posts_only_username_and_password(self, client):
        client.return_value.execute.return_value = {"assistedLogin": {"success": True, "data": {"access_token": "header.eyJuYW1lIjoidXNlciJ9.signature"}}}
        credential = auth.login("user@example.com", "secret", 12)
        self.assertEqual(credential["username"], "user")
        request = client.return_value.execute.call_args.args[0]
        self.assertEqual(request["variables"]["input"], {"username": "user@example.com", "password": "secret"})

    @patch("bryant_smarthome.auth.Client")
    def test_refresh_posts_username_and_refresh_token(self, client):
        client.return_value.execute.return_value = {"fetchAccessToken": {"success": True, "data": {
            "access_token": "header.eyJuYW1lIjoidXNlciJ9.signature", "refresh_token": "NEW"}}}
        credential = auth.refresh("user@example.com", "OLD", 12)
        self.assertEqual(credential["refresh_token"], "NEW")
        request = client.return_value.execute.call_args.args[0]
        self.assertEqual(request["variables"]["input"], {"username": "user@example.com", "refreshToken": "OLD"})

    @patch("bryant_smarthome.auth._keyring")
    def test_saved_session_uses_keyring_without_password(self, keyring):
        keyring.return_value.get_password.return_value = json.dumps({"token": "ACCESS", "refresh_token": "REFRESH", "expires_at": 9999999999})
        saved = auth.load_saved("user@example.com")
        self.assertEqual(auth.usable_access_token(saved), "ACCESS")
        keyring.return_value.get_password.assert_called_once_with("bryant-smarthome", "user@example.com")

    @patch("bryant_smarthome.auth._keyring")
    def test_save_keeps_password_out_of_keyring_record(self, keyring):
        auth.save({"username": "user@example.com", "token": "ACCESS", "refresh_token": "REFRESH", "expires_at": 1,
                   "password": "PASSWORD"})
        stored = json.loads(keyring.return_value.set_password.call_args.args[2])
        self.assertNotIn("password", stored)
        self.assertEqual(stored["refresh_token"], "REFRESH")

    @patch("bryant_smarthome.cli.auth.login", return_value={"token": "SECRET", "username": "user"})
    @patch("bryant_smarthome.cli.Client")
    def test_dotenv_credentials_login_for_read_without_leaking_secret(self, client, login):
        client.return_value.execute.return_value = {"userLocations": []}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("BRYANT_USERNAME=user@example.com\nBRYANT_PASSWORD=PASSWORD\n", encoding="utf-8")
            code, output, error = self.call(["--non-interactive", "--env-file", str(path), "homes"])
        self.assertEqual(code, 0, error)
        self.assertNotIn("PASSWORD", output + error)
        login.assert_called_once_with("user@example.com", "PASSWORD", 30)
        self.assertEqual(json.loads(output), {"userLocations": []})

    def test_noninteractive_missing_password_fails_without_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("", encoding="utf-8")
            code, _, error = self.call(["--non-interactive", "--env-file", str(path), "--username", "user", "login"])
        self.assertEqual(code, 1)
        self.assertIn("BRYANT_USERNAME and BRYANT_PASSWORD", error)

    @patch("bryant_smarthome.cli.auth.save")
    @patch("bryant_smarthome.cli.auth.refresh", return_value={"token": "FRESH", "username": "user", "refresh_token": "REFRESH"})
    @patch("bryant_smarthome.cli.auth.load_saved", return_value={"refresh_token": "REFRESH"})
    @patch("bryant_smarthome.cli.auth.usable_access_token", return_value=None)
    @patch("bryant_smarthome.cli.Client")
    def test_read_refreshes_saved_session_without_password(self, client, usable, load, refresh, save):
        client.return_value.execute.return_value = {"userLocations": []}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("BRYANT_USERNAME=user@example.com\n", encoding="utf-8")
            code, output, error = self.call(["--non-interactive", "--env-file", str(path), "homes"])
        self.assertEqual(code, 0, error)
        refresh.assert_called_once_with("user@example.com", "REFRESH", 30)
        self.assertEqual(json.loads(output), {"userLocations": []})

    @patch("bryant_smarthome.cli.auth.clear")
    def test_logout_removes_saved_session(self, clear):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("BRYANT_USERNAME=user@example.com\n", encoding="utf-8")
            code, output, error = self.call(["--non-interactive", "--env-file", str(path), "logout"])
        self.assertEqual(code, 0, error)
        clear.assert_called_once_with("user@example.com")
        self.assertEqual(json.loads(output), {"logged_out": True})

    @patch("bryant_smarthome.cli.auth.refresh")
    @patch("bryant_smarthome.cli.auth.usable_access_token", return_value="ACCESS")
    @patch("bryant_smarthome.cli.auth.load_saved", return_value={"refresh_token": "REFRESH"})
    @patch("bryant_smarthome.cli.Client")
    def test_failed_control_is_not_retried_after_authentication_error(self, client, load, usable, refresh):
        client.return_value.execute.side_effect = AuthenticationError("expired")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("BRYANT_USERNAME=user@example.com\n", encoding="utf-8")
            code, _, error = self.call(["--non-interactive", "--env-file", str(path), "mode", "serial", "auto", "--execute"])
        self.assertEqual(code, 1)
        self.assertIn("expired", error)
        refresh.assert_not_called()
        self.assertEqual(client.return_value.execute.call_count, 1)

    @patch("bryant_smarthome.cli.auth.save")
    @patch("bryant_smarthome.cli.auth.refresh", return_value={"token": "FRESH", "username": "user", "refresh_token": "REFRESH"})
    @patch("bryant_smarthome.cli.auth.usable_access_token", return_value="ACCESS")
    @patch("bryant_smarthome.cli.auth.load_saved", return_value={"refresh_token": "REFRESH"})
    @patch("bryant_smarthome.cli.Client")
    def test_read_retries_once_after_authentication_error(self, client, load, usable, refresh, save):
        first, second = client.return_value, client.return_value
        first.execute.side_effect = [AuthenticationError("expired"), {"userLocations": []}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("BRYANT_USERNAME=user@example.com\n", encoding="utf-8")
            code, output, error = self.call(["--non-interactive", "--env-file", str(path), "homes"])
        self.assertEqual(code, 0, error)
        self.assertEqual(first.execute.call_count, 2)
        refresh.assert_called_once_with("user@example.com", "REFRESH", 30)
        self.assertEqual(json.loads(output), {"userLocations": []})

    def test_docs_json_catalog_is_offline_and_lists_commands(self):
        code, output, error = self.call(["docs", "--format", "json"])
        self.assertEqual(code, 0, error)
        catalog = json.loads(output)
        self.assertEqual(catalog["version"], 1)
        names = {command["name"] for command in catalog["commands"]}
        self.assertTrue({"homes", "mode", "temperature"}.issubset(names))
        self.assertTrue(all(isinstance(command["help"], str) and command["help"]
                            for command in catalog["commands"]))
