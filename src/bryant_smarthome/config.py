"""Read only the chosen dotenv file, without changing process environment."""
import os
from pathlib import Path

from dotenv import dotenv_values

from .client import ClientError

KEYS = ("BRYANT_USERNAME", "BRYANT_PASSWORD")


def load_environment(path=None):
    selected = Path(path) if path is not None else Path.cwd() / ".env"
    values = {}
    try:
        if selected.is_file():
            # No interpolation: passwords containing ${...} remain literal.
            with selected.open(encoding="utf-8-sig") as source:
                values = dotenv_values(stream=source, interpolate=False)
        elif path is not None:
            raise ClientError("The specified environment file does not exist or is not a file.")
    except (OSError, UnicodeError):
        raise ClientError("Unable to read the environment file.") from None
    return {key: os.environ[key] if key in os.environ else values.get(key) for key in KEYS}
