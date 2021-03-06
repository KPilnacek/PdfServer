from functools import partial, wraps
from time import sleep
from typing import Callable

from pony.orm import set_sql_debug

from pdf_server.backend import app
from pdf_server.exceptions import DatabaseException

from . import db

__all__ = ["DatabaseConnection"]


def retry(function: Callable = None, /, *, n_retries: int, wait_time: float = 3) -> Callable:
    """Retry the execution of the decorated function :ref:`n_retries` or until it does not raise.

    :param function: Function to decorate.
    :param n_retries: Number of times to retry the execution.
    :param wait_time: Amount of time to wait in-between retries.
    """
    # Called with brackets: @retry()
    if function is None:
        return partial(retry, n_retries=n_retries)

    # Called without brackets: @retry

    @wraps(function)
    def wrapper(*args, **kwargs):
        retries = n_retries

        while True:
            try:
                return function(*args, **kwargs)
            except Exception:
                if (retries := retries - 1) == 0:
                    raise

                sleep(wait_time)

    return wrapper


class DatabaseConnection:
    """Database connection manager."""

    def __init__(self, debug: bool = False):
        self._connected = False

        set_sql_debug(debug)

    @retry(n_retries=5)
    def connect(self) -> None:
        """Connect to the database."""
        try:
            db.bind(provider="postgres", **app.config["database"])
        except Exception as ex:
            raise DatabaseException(f"Unable to connect to the database: {ex}") from None

        db.generate_mapping(create_tables=True)

        self._connected = True

    def disconnect(self) -> None:
        """Disconnect from the database."""
        if self._connected:
            db.disconnect()

    def __del__(self) -> None:
        self.disconnect()

    def __enter__(self) -> "DatabaseConnection":
        self.connect()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
