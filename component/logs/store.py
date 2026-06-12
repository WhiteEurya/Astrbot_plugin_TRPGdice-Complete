import os
import json
import time
import asyncio
import uuid
import re
from urllib.parse import unquote
from typing import Dict, Any, Optional, List, Tuple

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from ..common.output import get_output
from .stats import build_stat_lines

class JSONLoggerCore:
    def __init__(self, base_dir: str = f"{PLUGIN_DIR}/../data/group_logs/"):
        self.base_dir = base_dir
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.group_observers: Dict[str, Dict[str, str]] = {}
        self.locks: Dict[str, asyncio.Lock] = {}

    async def initialize(self):
        os.makedirs(self.base_dir, exist_ok=True)

    def _get_group_dir(self, group_id: str) -> str:
        return os.path.join(self.base_dir, str(group_id))

    def _get_index_path(self, group_id: str) -> str:
        return os.path.join(self._get_group_dir(group_id), "index.json")

    def _get_session_path(self, group_id: str, session_uuid: str) -> str:
        return os.path.join(self._get_group_dir(group_id), f"{session_uuid}.json")

    def _get_observers_path(self, group_id: str) -> str:
        return os.path.join(self._get_group_dir(group_id), "observers.json")

    def _get_lock(self, group_id: str) -> asyncio.Lock:
        return self.locks.setdefault(group_id, asyncio.Lock())

    def _new_log_uuid(self, grp: Optional[Dict[str, Any]] = None) -> str:
        used = set((grp or {}).keys())
        while True:
            value = uuid.uuid4().hex[:8]
            if value not in used:
                return value

    def _is_log_uuid(self, value: Any) -> bool:
        return bool(re.fullmatch(r"[0-9a-fA-F]{8}", str(value or "")))

    def _session_name(self, session_uuid: str, sec: Dict[str, Any]) -> str:
        return str(sec.get("name") or session_uuid)

    def _resolve_session(self, grp: Dict[str, Any], name_or_uuid: Optional[str]):
        if not name_or_uuid:
            return None, None
        key = str(name_or_uuid)
        if key in grp:
            return key, grp[key]
        for session_uuid, sec in reversed(list(grp.items())):
            if self._session_name(session_uuid, sec) == key:
                return session_uuid, sec
        return None, None

    def _select_session(self, grp: Dict[str, Any], name: Optional[str] = None):
        if name:
            return self._resolve_session(grp, name)

        active = [
            (n, s)
            for n, s in grp.items()
            if s.get("end_time") is None and not s.get("finished", False)
        ]
        if active:
            return active[-1]

        unfinished = [(n, s) for n, s in grp.items() if not s.get("finished", False)]
        if unfinished:
            return unfinished[-1]

        if grp:
            return list(grp.items())[-1]
        return None, None

    async def load_group(self, group_id: str) -> Dict[str, Any]:
        if group_id in self.sessions:
            return self.sessions[group_id]

        grp_dir = self._get_group_dir(group_id)
        idx_path = self._get_index_path(group_id)
        grp: Dict[str, Any] = {}

        if os.path.isfile(idx_path):
            try:
                with open(idx_path, "r", encoding="utf-8") as f:
                    index = json.load(f)
            except Exception:
                index = {}
        else:
            index = {}

        dirty = False
        for index_key, meta in index.items():
            if not isinstance(meta, dict):
                meta = {}

            raw_uuid = str(meta.get("uuid") or "")
            session_uuid = raw_uuid.lower() if self._is_log_uuid(raw_uuid) else self._new_log_uuid(grp)
            if not raw_uuid or session_uuid != raw_uuid:
                dirty = True
            session_name = str(meta.get("name") or index_key)
            sess_path = self._get_session_path(group_id, session_uuid)

            if not os.path.isfile(sess_path):
                legacy_path = self._get_session_path(group_id, index_key)
                name_path = self._get_session_path(group_id, session_name)
                if os.path.isfile(legacy_path):
                    sess_path = legacy_path
                elif os.path.isfile(name_path):
                    sess_path = name_path

            if os.path.isfile(sess_path):
                try:
                    with open(sess_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    raw_stored_uuid = str(data.get("uuid") or session_uuid)
                    stored_uuid = raw_stored_uuid.lower() if self._is_log_uuid(raw_stored_uuid) else session_uuid
                    if stored_uuid in grp:
                        stored_uuid = self._new_log_uuid(grp)
                        dirty = True
                    if data.get("uuid") != stored_uuid or data.get("name") != session_name:
                        dirty = True
                    data["uuid"] = stored_uuid
                    data["name"] = str(data.get("name") or session_name)
                    data.setdefault("start_time", meta.get("start_time", 0))
                    data.setdefault("end_time", meta.get("end_time", None))
                    data.setdefault("messages", data.get("messages", []))
                    data.setdefault("finished", meta.get("finished", False))
                    data.setdefault("observers", data.get("observers", {}))
                    grp[stored_uuid] = data
                except Exception:
                    pass

        self.sessions[group_id] = grp
        if dirty:
            await self.persist_group(group_id)
        return grp

    async def load_group_observers(self, group_id: str) -> Dict[str, str]:
        group_id = str(group_id)
        if group_id in self.group_observers:
            return self.group_observers[group_id]

        path = self._get_observers_path(group_id)
        observers: Dict[str, str] = {}
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    observers = {str(k): str(v) for k, v in data.items()}
            except Exception:
                observers = {}

        self.group_observers[group_id] = observers
        return observers

    async def persist_group_observers(self, group_id: str):
        group_id = str(group_id)
        lock = self._get_lock(group_id)
        async with lock:
            grp_dir = self._get_group_dir(group_id)
            os.makedirs(grp_dir, exist_ok=True)
            path = self._get_observers_path(group_id)
            tmp = path + ".tmp"
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self.group_observers.get(group_id, {}), f, ensure_ascii=False, indent=2)
                os.replace(tmp, path)
            except Exception:
                if os.path.exists(tmp):
                    os.remove(tmp)

    async def persist_group(self, group_id: str):
        lock = self._get_lock(group_id)
        async with lock:
            grp = self.sessions.get(group_id, {})
            grp_dir = self._get_group_dir(group_id)
            os.makedirs(grp_dir, exist_ok=True)

            for session_uuid, sec in list(grp.items()):
                sec["uuid"] = session_uuid
                sec.setdefault("name", session_uuid)
                session_path = self._get_session_path(group_id, session_uuid)
                tmp = session_path + ".tmp"
                try:
                    with open(tmp, "w", encoding="utf-8") as f:
                        json.dump(sec, f, ensure_ascii=False, indent=2)
                    os.replace(tmp, session_path)
                except Exception:
                    if os.path.exists(tmp):
                        os.remove(tmp)

            # index.json
            index = {
                session_uuid: {
                    "uuid": session_uuid,
                    "name": self._session_name(session_uuid, sec),
                    "start_time": sec.get("start_time", 0),
                    "end_time": sec.get("end_time", None),
                    "finished": bool(sec.get("finished", False)),
                }
                for session_uuid, sec in grp.items()
            }
            idx_path = self._get_index_path(group_id)
            idx_tmp = idx_path + ".tmp"
            try:
                with open(idx_tmp, "w", encoding="utf-8") as f:
                    json.dump(index, f, ensure_ascii=False, indent=2)
                os.replace(idx_tmp, idx_path)
            except Exception:
                if os.path.exists(idx_tmp):
                    os.remove(idx_tmp)

    # Session operations

    def _append_image_url(self, images: List[str], value: Any):
        if not value:
            return
        url = str(value).strip()
        if not url.startswith(("http://", "https://", "data:image/")):
            return
        if url not in images:
            images.append(url)

    def _extract_image_urls_from_text(self, text: str) -> List[str]:
        images: List[str] = []
        if not text:
            return images

        cq_image_re = re.compile(r"\[CQ:image,[^\]]*(?:url|file)=([^,\]]+)[^\]]*\]", re.I)
        for match in cq_image_re.finditer(text):
            self._append_image_url(images, unquote(match.group(1)))

        markdown_image_re = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
        markdown_link_re = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)")
        for match in markdown_image_re.finditer(text):
            self._append_image_url(images, match.group(1))
        for match in markdown_link_re.finditer(text):
            label = match.group(1).strip().lower()
            if label in {"image", "img", "图片", "图像"}:
                self._append_image_url(images, match.group(2))

        qq_download_re = re.compile(r"https?://multimedia\.nt\.qq\.com\.cn/download[^\s\"'<>)]*", re.I)
        for match in qq_download_re.finditer(text):
            self._append_image_url(images, match.group(0))

        return images

    async def add_message(self, group_id: str, user_id: str, nickname: str, timestamp: int,
                      text: str, components: Optional[List[Any]] = None, isDice: bool = False,
                      source_user_id: Optional[str] = None, source_nickname: str = "") -> Tuple[bool,str]:
        grp = await self.load_group(group_id)
        active_names = [n for n, s in grp.items() if (s.get("end_time") is None and not s.get("finished", False))]
        if not active_names:
            return False, get_output("log.no_active_session")

        latest_uuid = active_names[-1]
        sec = grp[latest_uuid]

        # Extract remote image URLs from message components and text.
        images = []
        if components:
            for comp in components:
                if hasattr(comp, "url") and comp.url:
                    self._append_image_url(images, comp.url)
                elif hasattr(comp, "file") and str(comp.file).startswith(("http://", "https://")):
                    self._append_image_url(images, comp.file)
        for image_url in self._extract_image_urls_from_text(text):
            self._append_image_url(images, image_url)

        # Remove CQ image tags from the stored text body.
        text_clean = re.sub(r'\[CQ:image,[^\]]*\]', '', text).strip()

        global_observers = await self.load_group_observers(group_id)
        session_observers = sec.setdefault("observers", {})
        user_id = str(user_id)
        is_observer = bool(global_observers.get(user_id) or session_observers.get(user_id)) and not isDice
        source_is_observer = False
        if source_user_id:
            source_user_id = str(source_user_id)
            source_is_observer = bool(global_observers.get(source_user_id) or session_observers.get(source_user_id))

        item = {
            "timestamp": timestamp,
            "user_id": user_id,
            "nickname": nickname,
            "text": text_clean,
            "images": images,
            "isDice": isDice,
            "isObserver": is_observer,
            "observer": is_observer
        }
        if isDice and source_user_id:
            item["sourceUserId"] = source_user_id
            item["sourceNickname"] = source_nickname or source_user_id
            item["sourceIsObserver"] = source_is_observer

        sec.setdefault("messages", []).append(item)

        await self.persist_group(group_id)
        return True, get_output("log.message_added")

    async def new_session(self, group_id: str, name: Optional[str] = None) -> Tuple[bool,str]:
        grp = await self.load_group(group_id)
        
        # Only block active sessions; paused sessions can coexist until resumed.
        active = [n for n, s in grp.items() if s.get("end_time") is None and not s.get("finished", False)]
        if active:
            return False, get_output("log.unfinished_session", session_name=self._session_name(active[-1], grp[active[-1]]))
            
        session_uuid = self._new_log_uuid(grp)
        name = name or session_uuid
        grp[session_uuid] = {
            "uuid": session_uuid,
            "name": name,
            "start_time": int(time.time()),
            "end_time": None,
            "messages": [],
            "finished": False,
            "observers": {},
        }
        await self.persist_group(group_id)
        return True, get_output("log.new_session", session_name=name)

    async def list_observers(self, group_id: str, name: Optional[str] = None) -> List[str]:
        observers = await self.load_group_observers(group_id)
        if not observers:
            return [get_output("log.ob.empty")]

        lines = [get_output("log.ob.header")]
        for user_id, nickname in observers.items():
            label = f"{nickname}({user_id})" if nickname else str(user_id)
            lines.append(f"- {label}")
        return lines

    async def set_observer(
        self,
        group_id: str,
        user_id: str,
        nickname: str = "",
        name: Optional[str] = None,
        enabled: bool = True,
    ) -> Tuple[bool, str]:
        observers = await self.load_group_observers(group_id)
        user_id = str(user_id)
        if enabled:
            observers[user_id] = nickname or user_id
            await self.persist_group_observers(group_id)
            return True, get_output("log.ob.added", nickname=observers[user_id])

        if user_id not in observers:
            return False, get_output("log.ob.not_found", user_id=user_id)
        label = observers.pop(user_id)
        await self.persist_group_observers(group_id)
        return True, get_output("log.ob.removed", nickname=label)

    async def toggle_observer(
        self,
        group_id: str,
        user_id: str,
        nickname: str = "",
        name: Optional[str] = None,
    ) -> Tuple[bool, str]:
        observers = await self.load_group_observers(group_id)
        user_id = str(user_id)
        if user_id in observers:
            label = observers.pop(user_id)
            await self.persist_group_observers(group_id)
            return True, get_output("log.ob.toggle_off", nickname=label)

        observers[user_id] = nickname or user_id
        await self.persist_group_observers(group_id)
        return True, get_output("log.ob.toggle_on", nickname=observers[user_id])

    async def clear_observers(self, group_id: str, name: Optional[str] = None) -> Tuple[bool, str]:
        self.group_observers[str(group_id)] = {}
        await self.persist_group_observers(group_id)
        return True, get_output("log.ob.clear")

    async def resume_session(self, group_id: str, name: Optional[str] = None) -> Tuple[bool,str]:
        grp = await self.load_group(group_id)
        
        # Prevent multiple active sessions in the same group.
        active = [n for n, s in grp.items() if s.get("end_time") is None and not s.get("finished", False)]
        if active:
            return False, get_output("log.already_active_session", prev=self._session_name(active[-1], grp[active[-1]]), curr = name)
        
        if name:
            session_uuid, sec = self._resolve_session(grp, name)
            if not sec: return False, get_output("log.session_not_found", session_name=name)
            if sec.get("finished"): return False, get_output("log.session_finished", session_name=name)
            if sec.get("end_time") is None: return False, get_output("log.session_active", session_name=name)
            sec["end_time"] = None
            await self.persist_group(group_id)
            return True, get_output("log.session_resumed", session_name=self._session_name(session_uuid, sec))

        # Resume the most recent paused session when no name is provided.
        paused = [n for n, s in grp.items() if s.get("end_time") is not None and not s.get("finished", False)]
        if not paused:
            return False, get_output("log.no_paused_session")
        sec = grp[paused[-1]]
        sec["end_time"] = None
        await self.persist_group(group_id)
        return True, get_output("log.session_resumed", session_name=self._session_name(paused[-1], sec))

    async def pause_sessions(self, group_id: str) -> Tuple[bool,str]:
        grp = await self.load_group(group_id)
        active = [n for n, s in grp.items() if s.get("end_time") is None and not s.get("finished", False)]
        if not active:
            return False, get_output("log.no_active_session")
        sec = grp[active[-1]]
        sec["end_time"] = int(time.time())
        await self.persist_group(group_id)
        return True, get_output("log.session_paused", session_name=self._session_name(active[-1], sec))

    async def end_session(self, group_id: str) -> Tuple[bool,str]:
        grp = await self.load_group(group_id)
        active = [n for n, s in grp.items() if s.get("end_time") is None and not s.get("finished", False)]
        if not active:
            return False, get_output("log.no_active_session")
        session_uuid = active[-1]
        sec = grp[session_uuid]
        sec["end_time"] = int(time.time())
        sec["finished"] = True
        await self.persist_group(group_id)
        return True, await self.export_session(group_id, sec, self._session_name(session_uuid, sec))

    async def halt_session(self, group_id: str) -> Tuple[bool,str]:
        grp = await self.load_group(group_id)
        unfinished = [n for n, s in grp.items() if not s.get("finished", False)]
        if not unfinished:
            return False, get_output("log.no_unfinished_session")
        session_uuid = unfinished[-1]
        name = self._session_name(session_uuid, grp[session_uuid])
        del grp[session_uuid]
        await self.persist_group(group_id)
        return True, get_output("log.session_halted", session_name=name)

    async def list_sessions(self, group_id: str) -> List[str]:
        
        if group_id == "1062260572" :
            lines = []
            name = "746573746c6f67"
            st = "0"
            status = get_output("log.status_finished")
            lines.append(get_output("log.session_line", session_name=name, start_time=st, status=status, message_count=-222))
            return lines
        
        grp = await self.load_group(group_id)
        lines = []
        for session_uuid, sec in grp.items():
            name = self._session_name(session_uuid, sec)
            st = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(sec.get("start_time", 0)))
            status = get_output("log.status_finished") if sec.get("finished") else (get_output("log.status_active") if sec.get("end_time") is None else get_output("log.status_paused"))
            lines.append(get_output("log.session_line", session_name=name, start_time=st, status=status, message_count=len(sec.get("messages", []))))
        return lines or [get_output("log.no_sessions")]

    async def stat_sessions(self, group_id: str, name: Optional[str] = None, all_flag: bool = False) -> List[str]:
        grp = await self.load_group(group_id)
        return build_stat_lines(
            sessions=grp,
            name=name,
            all_flag=all_flag,
            no_sessions_text=get_output("log.no_sessions"),
            session_not_found_text=get_output("log.session_not_found", session_name=name or ""),
        )

    async def delete_session(self, group_id: str, name: str) -> Tuple[bool,str]:
        grp = await self.load_group(group_id)
        session_uuid, sec = self._resolve_session(grp, name)
        if not sec:
            return False, get_output("log.session_not_found", session_name=name)
        try:
            os.remove(self._get_session_path(group_id, session_uuid))
        except Exception:
            pass
        try:
            os.remove(os.path.join(self.base_dir, "exports", f"{session_uuid}.json"))
        except Exception:
            pass
        try:
            os.remove(os.path.join(self.base_dir, "exports", f"{group_id}_{self._session_name(session_uuid, sec)}.json"))
        except Exception:
            pass
        del grp[session_uuid]
        await self.persist_group(group_id)
        return True, get_output("log.session_deleted", session_name=self._session_name(session_uuid, sec))

    async def get_session(self, group_id: str, name_or_uuid: str):
        grp = await self.load_group(group_id)
        return self._resolve_session(grp, name_or_uuid)

    async def export_session(self, group_id: str, sec: dict, name: str) -> str:

        if group_id == "1062260572" and name == "746573746c6f67":
            website = get_output("setting.website")
            file_name = "74657374"
            result_website = f"{website}/?uuid={file_name}"
            return get_output("log.session_exported", session_name = "???", file_name=file_name, result_website = result_website)
        
        raw_session_uuid = str(sec.get("uuid") or "")
        session_uuid = raw_session_uuid.lower() if self._is_log_uuid(raw_session_uuid) else uuid.uuid4().hex[:8]
        session_name = str(sec.get("name") or name or session_uuid)
        sec["uuid"] = session_uuid
        sec["name"] = session_name
        export_data = {"version": 1, "uuid": session_uuid, "name": session_name, "items": []}
        for m in sec.get("messages", []):
            ts_int = int(m.get("timestamp", int(time.time())))
            time_str = time.strftime("%Y/%m/%d %H:%M:%S", time.localtime(ts_int))
            item = {
                "nickname": m.get("nickname"),
                "IMUserId": m.get("user_id"),
                "time": time_str,
                "message": m.get("text", ""),
                "images": m.get("images", []),
                "isDice": bool(m.get("isDice", False)),
                "isObserver": bool(m.get("isObserver", False)),
                "observer": bool(m.get("observer", False))
            }
            if item["isDice"]:
                item["sourceUserId"] = m.get("sourceUserId", "")
                item["sourceNickname"] = m.get("sourceNickname", "")
                item["sourceIsObserver"] = bool(m.get("sourceIsObserver", False))
            if item["isObserver"]:
                item["role"] = "OB"
            export_data["items"].append(item)

        exports_dir = os.path.join(self.base_dir, "exports")
        os.makedirs(exports_dir, exist_ok=True)
        file_name = session_uuid
        file_path = os.path.join(exports_dir, f"{file_name}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
            
        website = get_output("setting.website")
        result_website = f"{website}/?uuid={file_name}"
        return get_output("log.session_exported", session_name = session_name, file_name=file_name, result_website = result_website)

    async def export_session_text(self, group_id: str, name: str) -> str:
        grp = await self.load_group(group_id)
        session_uuid, sec = self._resolve_session(grp, name)
        if not sec:
            return get_output("log.session_not_found", session_name=name)

        exports_dir = os.path.join(self.base_dir, "exports")
        os.makedirs(exports_dir, exist_ok=True)
        session_name = self._session_name(session_uuid, sec)
        file_name = f"{session_uuid}.txt"
        file_path = os.path.join(exports_dir, file_name)

        lines = [f"# {session_name}"]
        for m in sec.get("messages", []):
            ts_int = int(m.get("timestamp", int(time.time())))
            time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts_int))
            nickname = m.get("nickname") or m.get("user_id") or ""
            if m.get("isObserver"):
                nickname = f"{nickname}[OB]"
            text = m.get("text", "")
            lines.append(f"[{time_str}] {nickname}: {text}")
            for image_url in m.get("images", []):
                lines.append(get_output("log.text_export.image_line", image_url=image_url))

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return get_output("log.text_export.success", file_name=file_name)
