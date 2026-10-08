"""Password and refresh-token authentication for CLI invocations.

JWT decoding is only a routing/expiry hint, never signature validation or proof
of authentication. The API remains the authority for whether a token is valid.
"""
import base64
import json
import time

from .client import Client, ClientError

LOGIN = '''mutation assistedLogin($input: AssistedLoginInput!) {
  assistedLogin(input: $input) {
    success status errorMessage provider
    data { token_type expires_in access_token scope refresh_token }
  }
}'''
REFRESH = '''mutation fetchAccessToken($input: FetchAccessTokenInput!) {
  fetchAccessToken(input: $input) {
    success status errorMessage provider
    data { token_type expires_in access_token scope refresh_token }
  }
}'''
KEYRING_SERVICE = "bryant-smarthome"
def claims(token):
    try:
        part = token.split(".")[1]
        value = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError, IndexError, AttributeError):
        return {}


def token_credentials(data, fallback_username, previous_refresh_token=None):
    if not isinstance(data, dict):
        raise ClientError("Authentication returned no token data.")
    token = data.get("access_token")
    if not isinstance(token, str) or not token.strip() or any(c in token for c in "\r\n"):
        raise ClientError("Authentication returned no valid access token.")
    token_type = data.get("token_type", "Bearer")
    if not isinstance(token_type, str) or token_type.lower() != "bearer":
        raise ClientError("Authentication returned an unsupported token type.")
    decoded = claims(token)
    # Matches the app's getUserNameFromToken: name, falling back to sub.
    username = decoded.get("name") or decoded.get("sub") or fallback_username
    if username is not None and (not isinstance(username, str) or not username):
        raise ClientError("Invalid API username; supply --username.")
    refresh_token = data.get("refresh_token") or previous_refresh_token
    if refresh_token is not None and (not isinstance(refresh_token, str) or not refresh_token.strip()
                                      or any(c in refresh_token for c in "\r\n")):
        raise ClientError("Authentication returned an invalid refresh token.")
    expires_in = data.get("expires_in")
    if not isinstance(expires_in, (int, float)) or isinstance(expires_in, bool) or expires_in <= 0:
        expires_in = None
    result = {"token": token, "username": username, "refresh_token": refresh_token,
              "expires_at": time.time() + expires_in if expires_in else None}
    return result


def exchange(name, document, fields, timeout, previous_refresh_token=None):
    payload = {"operationName": name, "query": document, "variables": {"input": fields}}
    result = Client(timeout=timeout).execute(payload, authenticated=False)
    envelope = result.get(name)
    if not isinstance(envelope, dict) or envelope.get("success") is not True:
        raise ClientError("Authentication was unsuccessful.")
    return token_credentials(envelope.get("data"), fields["username"], previous_refresh_token)


def login(username, password, timeout=30):
    if not username or not password:
        raise ClientError("Username and password cannot be empty.")
    return exchange("assistedLogin", LOGIN, {"username": username, "password": password}, timeout)


def refresh(username, refresh_token, timeout=30):
    if not username or not refresh_token:
        raise ClientError("A username and refresh token are required.")
    return exchange("fetchAccessToken", REFRESH,
                    {"username": username, "refreshToken": refresh_token}, timeout, refresh_token)


def _keyring():
    try:
        import keyring
        return keyring
    except ImportError:
        raise ClientError("Secure credential storage is unavailable; install the keyring dependency.") from None


def load_saved(username):
    try:
        value = _keyring().get_password(KEYRING_SERVICE, username)
    except Exception:
        raise ClientError("Unable to read the OS credential store.") from None
    if not value:
        return None
    try:
        result = json.loads(value)
    except (TypeError, ValueError):
        return None
    if not isinstance(result, dict) or not isinstance(result.get("refresh_token"), str):
        return None
    return result


def save(credential, storage_username=None):
    refresh_token = credential.get("refresh_token")
    username = storage_username or credential.get("username")
    if not isinstance(username, str) or not username or not isinstance(refresh_token, str) or not refresh_token:
        return
    # The keyring protects the refresh token and optional short-lived token; passwords never enter this record.
    record = {key: credential.get(key) for key in ("token", "refresh_token", "expires_at", "username")}
    try:
        _keyring().set_password(KEYRING_SERVICE, username, json.dumps(record, separators=(",", ":")))
    except Exception:
        raise ClientError("Unable to save the session in the OS credential store.") from None


def clear(username):
    try:
        _keyring().delete_password(KEYRING_SERVICE, username)
    except Exception as exc:
        # keyring uses a backend-specific exception for an absent item; logout remains idempotent.
        if exc.__class__.__name__ != "PasswordDeleteError":
            raise ClientError("Unable to clear the OS credential store.") from None


def usable_access_token(saved):
    token, expires_at = saved.get("token"), saved.get("expires_at")
    return (token if isinstance(token, str) and token and isinstance(expires_at, (int, float))
            and not isinstance(expires_at, bool) and expires_at > time.time() + 60 else None)


