import time
import uuid
from dataclasses import dataclass, field


@dataclass
class Session:
    session_id: str
    created_at: float = field(default_factory=time.time)
    messages: list = field(default_factory=list)
    artifacts: list = field(default_factory=list)

    def add_message(self, role: str, content: str, metadata: dict | None = None):
        self.messages.append({
            "role": role,
            "content": content,
            "metadata": metadata or {},
            "timestamp": time.time(),
        })

    def add_artifact(self, artifact_type: str, path: str, description: str = ""):
        self.artifacts.append({
            "type": artifact_type,
            "path": path,
            "description": description,
            "timestamp": time.time(),
        })

    def get_history(self, max_messages: int = 20) -> list[dict]:
        return self.messages[-max_messages:]


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def create_session(self) -> Session:
        session_id = uuid.uuid4().hex
        session = Session(session_id=session_id)
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def get_or_create_session(self, session_id: str | None = None) -> Session:
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        return self.create_session()

    def delete_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def list_sessions(self) -> list[str]:
        return list(self._sessions.keys())
