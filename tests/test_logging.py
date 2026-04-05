from app.lib.logging import _redact, setup_logging


def test_redact_password() -> None:
    assert "password=***REDACTED***" in _redact("password=secret123")


def test_redact_token() -> None:
    assert "token=***REDACTED***" in _redact("token=eyJhbG.xyz")


def test_redact_preserves_non_sensitive() -> None:
    assert _redact("email=user@test.com") == "email=user@test.com"


def test_redact_authorization_header() -> None:
    result = _redact("Authorization: Bearer eyJhbG")
    assert "***REDACTED***" in result


def test_setup_logging_does_not_crash() -> None:
    setup_logging()
