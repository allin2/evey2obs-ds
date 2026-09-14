"""Tests for security sanitization and KeyringStore."""

from unittest.mock import MagicMock

from evey2obs.security import (
    KeyringStore,
    canonicalize_url,
    redact_text,
    sanitize_url_for_output,
)


def test_canonicalize_url():
    url = "https://www.bilibili.com/video/BV1xx?utm_source=share&utm_medium=ios&spm_id_from=333"
    canonical = canonicalize_url(url)
    assert "utm_source" not in canonical
    assert "utm_medium" not in canonical
    assert "spm_id_from=333" in canonical


def test_sanitize_url_for_output():
    url = "https://example.com/api?token=secret123&api_key=sk-abc&item=42"
    sanitized = sanitize_url_for_output(url)
    assert "token" not in sanitized
    assert "api_key" not in sanitized
    assert "item=42" in sanitized


def test_redact_text():
    text = "Authorization: Bearer sk-12345678 and api_key=secretval"
    redacted = redact_text(text, secrets=("sk-12345678",))
    assert "sk-12345678" not in redacted
    assert "secretval" not in redacted
    assert "[REDACTED]" in redacted


def test_keyring_store_mock():
    store = KeyringStore(service="test_evey2obs")
    mock_keyring = MagicMock()
    mock_keyring.get_password.return_value = "sk-test-pass"
    mock_keyring.set_password.return_value = None

    store._keyring = mock_keyring
    store._available = True

    assert store.get_password("llm") == "sk-test-pass"
    assert store.set_password("llm", "new-pass") is True
    assert store.delete_password("llm") is True
