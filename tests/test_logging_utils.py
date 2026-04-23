import json
import logging

from devwrapped.logging_utils import (
    JsonFormatter,
    configure_logging,
    log_event,
    new_correlation_id,
    redact,
)


def test_redact_dict_with_sensitive_keys():
    payload = {
        "password": "hunter2",
        "AUTHORIZATION": "Bearer secret",
        "nested": {"api_key": "x", "ok": "fine"},
    }
    cleaned = redact(payload)
    assert cleaned["password"] == "[REDACTED]"
    assert cleaned["AUTHORIZATION"] == "[REDACTED]"
    assert cleaned["nested"]["api_key"] == "[REDACTED]"
    assert cleaned["nested"]["ok"] == "fine"


def test_redact_strings_with_known_secret_patterns():
    token = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    assert redact(token) == "[REDACTED]"
    assert "[REDACTED]" in redact("prefix " + token + " suffix")


def test_redact_query_string_secrets():
    url = "https://example.com/path?token=supersecret&ok=1"
    cleaned = redact(url)
    assert "supersecret" not in cleaned
    assert "ok=1" in cleaned


def test_json_formatter_emits_single_line_json(capsys, caplog):
    configure_logging(level="DEBUG", json_output=True)
    cid = new_correlation_id()
    logger = logging.getLogger("devwrapped.test.logging")
    log_event(logger, logging.INFO, "test.event", owner="alice", token="ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")

    captured = capsys.readouterr().err.strip().splitlines()
    # At least one structured record matches.
    parsed = None
    for line in captured:
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if obj.get("message") == "test.event":
            parsed = obj
            break

    assert parsed is not None, f"no matching JSON log line in {captured!r}"
    assert parsed["level"] == "INFO"
    assert parsed["owner"] == "alice"
    assert parsed["token"] == "[REDACTED]"
    assert parsed["correlation_id"] == cid


def test_json_formatter_strips_control_chars():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="t",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello\r\nworld",
        args=None,
        exc_info=None,
    )
    output = json.loads(formatter.format(record))
    assert output["message"] == "helloworld"
