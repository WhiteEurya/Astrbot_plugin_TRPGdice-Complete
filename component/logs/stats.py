from typing import Any, Dict, List, Optional, Tuple

from ..common.output import get_output


SessionMap = Dict[str, Dict[str, Any]]
SessionEntry = Tuple[str, Dict[str, Any]]


def select_sessions(
    sessions: SessionMap,
    name: Optional[str] = None,
    all_flag: bool = False,
) -> Tuple[List[SessionEntry], bool]:
    if name:
        session = sessions.get(name)
        if session is not None:
            return [(name, session)], True
        for session_id, session in reversed(list(sessions.items())):
            if str(session.get("name") or session_id) == name:
                return [(session_id, session)], True
        return [], False

    if all_flag:
        return list(sessions.items()), True

    active = [
        (n, s)
        for n, s in sessions.items()
        if s.get("end_time") is None and not s.get("finished", False)
    ]
    paused = [
        (n, s)
        for n, s in sessions.items()
        if s.get("end_time") is not None and not s.get("finished", False)
    ]
    return active[-1:] or paused[-1:] or list(sessions.items())[-1:], True


def format_session_stats(session_name: str, session: Dict[str, Any]) -> str:
    display_name = str(session.get("name") or session_name)
    messages = session.get("messages", [])
    users = {str(m.get("user_id", "")) for m in messages if m.get("user_id")}
    dice_count = sum(1 for m in messages if m.get("isDice"))
    observer_count = sum(1 for m in messages if m.get("isObserver"))
    image_count = sum(len(m.get("images", [])) for m in messages)
    return get_output(
        "log.stat.line",
        session_name=display_name,
        message_count=len(messages),
        user_count=len(users),
        dice_count=dice_count,
        observer_count=observer_count,
        image_count=image_count,
    )


def build_stat_lines(
    sessions: SessionMap,
    name: Optional[str],
    all_flag: bool,
    no_sessions_text: str,
    session_not_found_text: str,
) -> List[str]:
    if not sessions:
        return [no_sessions_text]

    selected, exists = select_sessions(sessions, name, all_flag)
    if not exists:
        return [session_not_found_text]

    lines = [format_session_stats(session_name, session) for session_name, session in selected]
    return lines or [no_sessions_text]
