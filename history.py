"""Local history of observed USB power connections."""

from contextlib import contextmanager
from pathlib import Path
import sqlite3
import time


PATH = Path.home() / ".config" / "framey" / "frame-charge-history.sqlite3"


@contextmanager
def database(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=1)
    try:
        with connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS sessions ("
                "id INTEGER PRIMARY KEY, started INTEGER NOT NULL, "
                "ended INTEGER NOT NULL, seconds INTEGER NOT NULL)"
            )
            yield connection
    finally:
        connection.close()


def trim(connection, limit):
    connection.execute(
        "DELETE FROM sessions WHERE id IN "
        "(SELECT id FROM sessions ORDER BY id DESC LIMIT -1 OFFSET ?)", (limit,)
    )


def sessions(limit, path=PATH):
    if not path.exists():
        return []
    with database(path) as connection:
        return [
            {"started": started, "ended": ended, "seconds": seconds}
            for started, ended, seconds in connection.execute(
                "SELECT started, ended, seconds FROM sessions ORDER BY id DESC LIMIT ?", (limit,)
            )
        ]


def prune(limit, path=PATH):
    if path.exists():
        with database(path) as connection:
            trim(connection, limit)


def clear(path=PATH):
    if path.exists():
        with database(path) as connection:
            connection.execute("DELETE FROM sessions")


def elapsed_clock():
    if hasattr(time, "CLOCK_BOOTTIME"):
        return time.clock_gettime(time.CLOCK_BOOTTIME)
    return time.monotonic()


class Recorder:
    def __init__(self, path=PATH):
        self.path = path
        self.connected = None
        self.candidate = None
        self.started = None

    def update(self, connected, settings):
        if not settings["record_history"]:
            self.connected = self.candidate = self.started = None
            return
        if connected is None or connected == self.connected:
            self.candidate = None
            return
        if self.candidate is None or self.candidate[0] != connected:
            self.candidate = (connected, time.time(), elapsed_clock())
            return

        # Confirm the edge on a second sample and keep its first observed time.
        _, observed_at, elapsed_at = self.candidate
        if connected and self.connected is False:
            self.started = (observed_at, elapsed_at)
        elif not connected and self.started is not None:
            started_at, elapsed_start = self.started
            with database(self.path) as connection:
                connection.execute(
                    "INSERT INTO sessions (started, ended, seconds) VALUES (?, ?, ?)",
                    (int(started_at), int(observed_at), int(elapsed_at - elapsed_start)),
                )
                trim(connection, settings["history_limit"])
            self.started = None
        self.connected = connected
        self.candidate = None
