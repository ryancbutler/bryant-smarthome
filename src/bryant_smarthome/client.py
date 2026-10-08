import json
import urllib.error
import urllib.request

ENDPOINT = "https://dataservice.infinity.iot.carrier.com/graphql"
AUTH_ENDPOINT = "https://dataservice.infinity.iot.carrier.com/graphql-no-auth"


class ClientError(Exception):
    pass


class AuthenticationError(ClientError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, token=None, timeout=30):
        if token is not None and (not isinstance(token, str) or not token.strip() or any(c in token for c in "\r\n")):
            raise ClientError("Access token must be nonempty and contain no line breaks.")
        self.token = token
        self.timeout = timeout
        self.opener = urllib.request.build_opener(NoRedirect())

    def execute(self, payload, *, authenticated=True):
        headers = {"Content-Type": "application/json", "Mobile-App-Brand": "Bryant"}
        if authenticated:
            if self.token is None:
                raise AuthenticationError("An access token is required.")
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(
            ENDPOINT if authenticated else AUTH_ENDPOINT,
            data=json.dumps(payload).encode("utf-8"), method="POST", headers=headers,
        )
        result = self.request_json(request)
        if result.get("errors"):
            # Do not echo arbitrary server messages that may contain credentials.
            raise ClientError("GraphQL reported errors; operation did not fully succeed.")
        if not isinstance(result.get("data"), dict):
            raise ClientError("GraphQL response has no data field.")
        data = result["data"]
        for value in data.values():
            if isinstance(value, dict) and value.get("success") is False:
                if value.get("provider") == "SOCIAL":
                    raise AuthenticationError("This account cannot use username/password authentication.")
                raise ClientError("API reported an unsuccessful operation.")
        return data

    def request_json(self, request):
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                result = json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                raise AuthenticationError("API returned HTTP 401. Check username/password and try again.") from None
            raise ClientError(f"API returned HTTP {exc.code}.") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise ClientError("API connection failed or timed out.") from None
        except (ValueError, UnicodeError):
            raise ClientError("API returned invalid JSON.") from None
        if not isinstance(result, dict):
            raise ClientError("API returned an unexpected response.")
        return result
