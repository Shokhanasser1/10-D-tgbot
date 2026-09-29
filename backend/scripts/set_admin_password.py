"""Give an existing admin a login and password from the terminal (Spec 7).

For the first owner on a machine where Telegram sign-in is not available (localhost, students):

    python -m scripts.set_admin_password 111111 --login owner

The password is asked twice and never shown. The admin row must exist already: owners listed in
ADMIN_BOOTSTRAP_TELEGRAM_IDS get one when the API starts.
"""

import argparse
import asyncio
import getpass
import sys

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.db.session import async_session_factory
from app.services import admin_service


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("telegram_id", type=int, help="the admin's Telegram ID")
    parser.add_argument("--login", help="login to sign in with (default: keep, or 'owner')")
    return parser.parse_args(argv)


async def _set(telegram_id: int, login: str | None, password: str) -> str:
    async with async_session_factory() as db:
        admin = await admin_service.set_password_from_terminal(db, telegram_id, login, password)
        return admin.login or ""


def main(argv: list[str] | None = None, ask=getpass.getpass) -> int:
    args = _parse_args(argv)
    password = ask("New password: ")
    if password != ask("Repeat it: "):
        print("error: the passwords do not match", file=sys.stderr)
        return 1
    try:
        login = asyncio.run(_set(args.telegram_id, args.login, password))
    except (BadRequestError, ConflictError, NotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Done. Sign in at /admin/login with the login '{login}'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
