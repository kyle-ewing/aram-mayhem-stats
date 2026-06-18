"""Domain errors and their HTTP representations."""
from __future__ import annotations


class ApiError(Exception):
    """Base class for errors that should be returned to the client as JSON.

    ``status_code`` controls the HTTP response code; ``message`` is surfaced to
    the user, so keep it free of secrets (never include the API key).
    """

    status_code = 500

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code

    def to_dict(self) -> dict[str, str]:
        return {"error": self.message}


class ConfigError(ApiError):
    """Server is misconfigured (e.g. missing API key)."""

    status_code = 500


class ValidationError(ApiError):
    """Client sent an invalid payload (failed schema/contract validation)."""

    status_code = 400


class RiotApiError(ApiError):
    """The upstream Riot API returned an error or could not be reached."""

    status_code = 502


class NotFoundError(ApiError):
    """A requested resource (player, matches) does not exist."""

    status_code = 404


class RateLimitError(RiotApiError):
    """Riot rate limit hit. ``retry_after`` is seconds to wait, if known."""

    status_code = 429

    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after
