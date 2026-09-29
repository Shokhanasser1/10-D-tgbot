"""The production image installs only requirements.txt, so runtime imports must be listed there."""

from pathlib import Path

REQUIREMENTS = Path(__file__).resolve().parent.parent / "requirements.txt"


def _packages() -> set[str]:
    names = set()
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            names.add(line.split("[", 1)[0].split(">", 1)[0].split("=", 1)[0].strip().lower())
    return names


def test_stripe_async_http_client_is_a_runtime_dependency() -> None:
    # Without httpx every stripe *_async call fails with ImportError, and only in production:
    # the dev requirements (where the tests run) have it for the test client anyway.
    assert {"stripe", "httpx"} <= _packages()


def test_sqlalchemy_is_installed_with_its_asyncio_extra() -> None:
    # Newer SQLAlchemy releases no longer pull in greenlet by default; without it the async
    # engine (and alembic's env.py) fails at import time and the API never starts.
    text = REQUIREMENTS.read_text(encoding="utf-8")
    assert "sqlalchemy[asyncio]" in text
