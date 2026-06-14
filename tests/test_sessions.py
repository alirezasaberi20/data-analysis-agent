"""Tests for session management."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.sessions.manager import SessionManager, Session


class TestSessionManager:
    def test_create_session(self):
        mgr = SessionManager()
        session = mgr.create_session()
        assert session.session_id is not None
        assert len(session.messages) == 0

    def test_get_session(self):
        mgr = SessionManager()
        session = mgr.create_session()
        retrieved = mgr.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.session_id == session.session_id

    def test_get_nonexistent(self):
        mgr = SessionManager()
        assert mgr.get_session("nonexistent") is None

    def test_get_or_create(self):
        mgr = SessionManager()
        s1 = mgr.get_or_create_session()
        s2 = mgr.get_or_create_session(s1.session_id)
        assert s1.session_id == s2.session_id

        s3 = mgr.get_or_create_session("new-id")
        assert s3.session_id != s1.session_id

    def test_delete_session(self):
        mgr = SessionManager()
        session = mgr.create_session()
        assert mgr.delete_session(session.session_id) is True
        assert mgr.get_session(session.session_id) is None
        assert mgr.delete_session(session.session_id) is False

    def test_list_sessions(self):
        mgr = SessionManager()
        mgr.create_session()
        mgr.create_session()
        assert len(mgr.list_sessions()) == 2


class TestSession:
    def test_add_message(self):
        session = Session(session_id="test-123")
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi there")
        assert len(session.messages) == 2
        assert session.messages[0]["role"] == "user"
        assert session.messages[1]["role"] == "assistant"

    def test_get_history_limit(self):
        session = Session(session_id="test-456")
        for i in range(30):
            session.add_message("user", f"Message {i}")
        history = session.get_history(max_messages=10)
        assert len(history) == 10

    def test_add_artifact(self):
        session = Session(session_id="test-789")
        session.add_artifact("chart", "/path/chart.png", "Sales chart")
        assert len(session.artifacts) == 1
        assert session.artifacts[0]["type"] == "chart"
