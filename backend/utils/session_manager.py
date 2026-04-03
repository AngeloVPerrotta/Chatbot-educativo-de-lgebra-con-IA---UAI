from datetime import datetime


_sessions: dict[str, dict] = {}


def get_session(session_id: str) -> dict:
    if session_id not in _sessions:
        _sessions[session_id] = {
            "messages": [],
            "created_at": datetime.utcnow().isoformat(),
            "agent": "algebra",
        }
    return _sessions[session_id]


def append_message(session_id: str, role: str, content: str) -> None:
    session = get_session(session_id)
    session["messages"].append({"role": role, "content": content})


def get_messages(session_id: str) -> list[dict]:
    return get_session(session_id)["messages"]


def clear_session(session_id: str) -> None:
    _sessions.pop(session_id, None)
