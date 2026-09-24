import io
import json
import urllib.error
import urllib.request
from typing import Any

import pytest

from app.config import get_settings
from scripts import set_telegram_webhook as script

TOKEN = "123456:SECRET-BOT-TOKEN"
SECRET = "webhook_secret-1"


class FakeResponse(io.BytesIO):
    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


@pytest.fixture(autouse=True)
def configured(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_bot_token", TOKEN)
    monkeypatch.setattr(settings, "telegram_webhook_secret", SECRET)


@pytest.fixture
def telegram(monkeypatch: pytest.MonkeyPatch) -> list[urllib.request.Request]:
    """Replace the network with a scripted Telegram; returns the requests made."""
    requests: list[urllib.request.Request] = []
    reply: dict[str, Any] = {"ok": True, "result": True}

    def fake_urlopen(request: urllib.request.Request, timeout: float = 0) -> FakeResponse:
        requests.append(request)
        return FakeResponse(json.dumps(reply).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return requests


def test_the_api_path_is_appended_to_the_public_origin() -> None:
    assert script.build_webhook_url("https://shop.example.com") == (
        "https://shop.example.com/api/webhooks/telegram"
    )
    assert script.build_webhook_url("https://shop.example.com/", "/hook") == (
        "https://shop.example.com/hook"
    )


@pytest.mark.parametrize("origin", ["http://shop.example.com", "shop.example.com", "https://", ""])
def test_only_an_https_origin_is_accepted(origin: str) -> None:
    with pytest.raises(ValueError, match="https"):
        script.build_webhook_url(origin)


def test_the_path_must_be_absolute() -> None:
    with pytest.raises(ValueError, match="--path"):
        script.build_webhook_url("https://shop.example.com", "hook")


def test_the_payload_carries_the_secret_and_only_the_updates_we_read() -> None:
    payload = script.build_set_payload("https://x.example/api/webhooks/telegram", SECRET)

    assert payload == {
        "url": "https://x.example/api/webhooks/telegram",
        "secret_token": SECRET,
        "allowed_updates": ["message", "edited_message"],
    }


def test_optional_payload_fields_appear_only_when_requested() -> None:
    payload = script.build_set_payload("https://x", SECRET, max_connections=5, drop_pending=True)

    assert payload["max_connections"] == 5
    assert payload["drop_pending_updates"] is True


def test_set_posts_to_the_bot_api_and_never_prints_the_token(
    telegram: list[urllib.request.Request], capsys: pytest.CaptureFixture[str]
) -> None:
    code = script.main(["https://shop.example.com"])

    assert code == 0
    (request,) = telegram
    assert request.full_url.endswith("/setWebhook")
    body = json.loads(request.data)
    assert body["url"] == "https://shop.example.com/api/webhooks/telegram"
    assert body["secret_token"] == SECRET
    out = capsys.readouterr()
    assert TOKEN not in out.out + out.err
    assert SECRET not in out.out + out.err


def test_info_prints_telegrams_view(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    info = {"url": "https://x/api", "pending_update_count": 3, "last_error_message": "boom"}
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda request, timeout=0: FakeResponse(json.dumps({"ok": True, "result": info}).encode()),
    )

    assert script.main(["--info"]) == 0

    out = capsys.readouterr().out
    assert "pending_update_count: 3" in out and "boom" in out and TOKEN not in out


def test_delete_removes_the_webhook(
    telegram: list[urllib.request.Request], capsys: pytest.CaptureFixture[str]
) -> None:
    assert script.main(["--delete"]) == 0

    assert telegram[0].full_url.endswith("/deleteWebhook")
    assert "removed" in capsys.readouterr().out


def test_an_http_origin_fails_before_any_request(
    telegram: list[urllib.request.Request], capsys: pytest.CaptureFixture[str]
) -> None:
    assert script.main(["http://shop.example.com"]) == 1

    assert telegram == []
    assert "https" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("setting", "argv"),
    [
        ("telegram_bot_token", ["https://shop.example.com"]),
        ("telegram_webhook_secret", ["https://shop.example.com"]),
    ],
)
def test_missing_configuration_is_reported_without_a_request(
    monkeypatch: pytest.MonkeyPatch,
    telegram: list[urllib.request.Request],
    capsys: pytest.CaptureFixture[str],
    setting: str,
    argv: list[str],
) -> None:
    monkeypatch.setattr(get_settings(), setting, "")

    assert script.main(argv) == 2

    assert telegram == []
    assert setting.upper() in capsys.readouterr().err


def test_no_origin_and_no_flag_is_a_usage_error(
    telegram: list[urllib.request.Request],
) -> None:
    assert script.main([]) == 2


def test_a_telegram_error_is_reported_by_its_description_only(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def rejecting(request: urllib.request.Request, timeout: float = 0) -> None:
        raise urllib.error.HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            {},  # type: ignore[arg-type]
            io.BytesIO(b'{"ok": false, "description": "Unauthorized"}'),
        )

    monkeypatch.setattr(urllib.request, "urlopen", rejecting)

    assert script.main(["https://shop.example.com"]) == 1

    out = capsys.readouterr()
    assert "Unauthorized" in out.err
    assert TOKEN not in out.out + out.err


def test_a_network_failure_does_not_leak_the_token(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def unreachable(request: urllib.request.Request, timeout: float = 0) -> None:
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", unreachable)

    assert script.main(["https://shop.example.com"]) == 1

    out = capsys.readouterr()
    assert "connection refused" in out.err
    assert TOKEN not in out.out + out.err
