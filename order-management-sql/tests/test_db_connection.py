from __future__ import annotations

import pyodbc
import pytest

from app import db


class FakeCursor:
    def __init__(self) -> None:
        self.executed: list[str] = []
        self.closed = False

    def execute(self, statement: str) -> None:
        self.executed.append(statement)

    def fetchone(self) -> tuple[int]:
        return (1,)

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self) -> None:
        self.fake_cursor = FakeCursor()
        self.closed = False

    def cursor(self) -> FakeCursor:
        return self.fake_cursor

    def close(self) -> None:
        self.closed = True


def test_get_connection_retries_transient_link_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeConnection()
    calls = 0

    def connect(*args: object, **kwargs: object) -> FakeConnection:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise pyodbc.Error("08S01", "Communication link failure")
        return connection

    monkeypatch.setattr(db, "build_connection_string", lambda: "test connection")
    monkeypatch.setattr(db.pyodbc, "connect", connect)
    monkeypatch.setattr(db.time, "sleep", lambda _: None)

    result = db.get_connection()

    assert result is connection
    assert calls == 2
    assert connection.fake_cursor.executed == ["SELECT 1;"]
    assert connection.fake_cursor.closed


def test_get_connection_does_not_retry_nontransient_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def connect(*args: object, **kwargs: object) -> FakeConnection:
        nonlocal calls
        calls += 1
        raise pyodbc.Error("28000", "Login failed")

    monkeypatch.setattr(db, "build_connection_string", lambda: "test connection")
    monkeypatch.setattr(db.pyodbc, "connect", connect)
    monkeypatch.setattr(db.time, "sleep", lambda _: None)

    with pytest.raises(pyodbc.Error, match="Login failed"):
        db.get_connection()

    assert calls == 1
