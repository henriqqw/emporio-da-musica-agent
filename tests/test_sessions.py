from datetime import datetime, timedelta

from emporio.sessions import SessionStore

START = datetime(2026, 3, 25, 14, 0)


def test_same_phone_keeps_history_while_active():
    sessions = SessionStore(ttl=timedelta(minutes=30))
    sessions.get("67996547821", START).messages.append({"role": "user", "content": "oi"})
    later = sessions.get("67996547821", START + timedelta(minutes=29))
    assert len(later.messages) == 1


def test_activity_extends_the_session():
    sessions = SessionStore(ttl=timedelta(minutes=30))
    sessions.get("p", START).messages.append({"role": "user", "content": "oi"})
    sessions.get("p", START + timedelta(minutes=20))
    assert len(sessions.get("p", START + timedelta(minutes=40)).messages) == 1


def test_idle_session_starts_over():
    sessions = SessionStore(ttl=timedelta(minutes=30))
    sessions.get("p", START).messages.append({"role": "user", "content": "oi"})
    assert sessions.get("p", START + timedelta(minutes=31)).messages == []


def test_phones_are_isolated_and_reset_clears():
    sessions = SessionStore(ttl=timedelta(minutes=30))
    sessions.get("a", START).messages.append({"role": "user", "content": "oi"})
    assert sessions.get("b", START).messages == []
    sessions.reset("a")
    assert sessions.get("a", START).messages == []
