"""Security, credential scrubbing, and system keychain storage."""

from __future__ import annotations

import logging
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

logger = logging.getLogger(__name__)

_SECRET_KEYS = re.compile(
    r"(?:api[-_]?key|authorization|cookie|token|secret|password|auth[-_]?token)",
    re.IGNORECASE,
)
_TRACKING_PARAMETERS = {
    "appuid",
    "share_id",
    "shareredid",
    "share_source",
    "source",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
}
_URL_IN_TEXT = re.compile(r"https?://[^\s<>\"'，。；！？、]+", re.IGNORECASE)


# ── URL & Text Redaction ──────────────────────────────────────────────────────


def canonicalize_url(url: str) -> str:
    """Remove user tracking query fields while retaining functional routing parameters."""
    parts = urlsplit(url)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.casefold() not in _TRACKING_PARAMETERS
    ]
    host = (parts.hostname or "").lower()
    netloc = host
    if parts.port:
        netloc = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme.lower(), netloc, parts.path, urlencode(query), ""))


def sanitize_url_for_output(url: str) -> str:
    """Remove credentials and tracking parameters from URLs to be persisted in notes."""
    parts = urlsplit(url)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not _SECRET_KEYS.search(key) and key.casefold() not in _TRACKING_PARAMETERS
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def redact_text(text: str, secrets: tuple[str, ...] = ()) -> str:
    """Redact known secrets and common sensitive patterns from free-form text."""
    redacted = text
    for secret in secrets:
        if secret and len(secret) > 3:
            redacted = redacted.replace(secret, "[REDACTED]")
    redacted = re.sub(
        r"(?i)\b(api[-_]?key|authorization|cookie|password|secret|token|auth[-_]?token)"
        r"\b\s*[:=]\s*([^\s,;]+)",
        r"\1=[REDACTED]",
        redacted,
    )
    return redacted


# ── System Keyring Storage ────────────────────────────────────────────────────


class KeyringStore:
    """Secure credential store backed by the operating system keychain (keyring).

    Falls back cleanly when keyring is unavailable (e.g. headless server, container,
    or library not installed).
    """

    SERVICE_NAME = "evey2obs"
    DEFAULT_ACCOUNT = "llm_api_key"

    def __init__(self, service: str = SERVICE_NAME) -> None:
        self.service = service
        self._keyring = None
        self._available: bool | None = None

    def is_available(self) -> bool:
        """Check if system keyring is usable."""
        if self._available is not None:
            return self._available

        try:
            import keyring

            # Test backend
            backend = keyring.get_keyring()
            if "fail" in backend.__class__.__name__.lower():
                self._available = False
            else:
                self._keyring = keyring
                self._available = True
        except Exception as exc:
            logger.debug("Keyring is not available: %s", exc)
            self._available = False

        return self._available

    def get_password(self, account: str = DEFAULT_ACCOUNT) -> str | None:
        """Retrieve password from system keychain."""
        if not self.is_available() or self._keyring is None:
            return None
        try:
            return self._keyring.get_password(self.service, account)
        except Exception as exc:
            logger.warning("Failed to read from keyring: %s", exc)
            return None

    def set_password(self, account: str = DEFAULT_ACCOUNT, password: str = "") -> bool:
        """Save password into system keychain."""
        if not self.is_available() or self._keyring is None:
            return False
        try:
            self._keyring.set_password(self.service, account, password)
            return True
        except Exception as exc:
            logger.warning("Failed to write to keyring: %s", exc)
            return False

    def delete_password(self, account: str = DEFAULT_ACCOUNT) -> bool:
        """Delete password from system keychain."""
        if not self.is_available() or self._keyring is None:
            return False
        try:
            self._keyring.delete_password(self.service, account)
            return True
        except Exception as exc:
            logger.debug("Password delete failed: %s", exc)
            return False
