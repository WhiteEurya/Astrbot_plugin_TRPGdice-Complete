import os
import json
import time
import asyncio
import uuid
import re
from typing import Dict, Any, Optional, List, Tuple

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
from .output import get_output

class JSONLoggerCore:
    def __init__(self, base_dir: str = f"{PLUGIN_DIR}/../data/group_logs/"):
        self.base_dir = base_dir
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.locks: Dict[str, asyncio.Lock] = {}

    async def initialize(self):
        os.makedirs(self.base_dir, exist_ok=True)

    def _get_group_dir(self, group_id: str) -> str:
        return os.path.join(self.base_dir, str(group_id))

    def _get_index_path(self, group_id: str) -> str:
        return os.path.join(self._get_group_dir(group_id), "index.json")

    def _get_session_path(self, group_id: str, session_name: str) -> str:
        return os.path.join(self._get_group_dir(group_id), f"{session_name}.json")

    def _get_lock(self, group_id: str) -> asyncio.Lock:
        return self.locks.setdefault(group_id, asyncio.Lock())

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

        for name, meta in index.items():
            sess_path = self._get_session_path(group_id, name)
            if os.path.isfile(sess_path):
                try:
                    with open(sess_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    data.setdefault("start_time", meta.get("start_time", 0))
                    data.setdefault("end_time", meta.get("end_time", None))
                    data.setdefault("messages", data.get("messages", []))
                    data.setdefault("finished", meta.get("finished", False))
                    grp[name] = data
                except Exception:
                    pass

        self.sessions[group_id] = grp
        return grp

    async def persist_group(self, group_id: str):
        lock = self._get_lock(group_id)
        async with lock:
            grp = self.sessions.get(group_id, {})
            grp_dir = self._get_group_dir(group_id)
            os.makedirs(grp_dir, exist_ok=True)

            for name, sec in list(grp.items()):
                session_path = self._get_session_path(group_id, name)
                tmp = session_path + ".tmp"
                try:
                    with open(tmp, "w", encoding="utf-8") as f:
                        json.dump(sec, f, ensure_ascii=False, indent=2)
                    os.replace(tmp, session_path)
                except Exception:
                    if os.path.exists(tmp):
                        os.remove(tmp)

            # index.json
            index = {name: {"start_time": sec.get("start_time", 0),
                            "end_time": sec.get("end_time", None),
                            "finished": bool(sec.get("finished", False))}
                     for name, sec in grp.items()}
            idx_path = self._get_index_path(group_id)
            idx_tmp = idx_path + ".tmp"
            try:
                with open(idx_tmp, "w", encoding="utf-8") as f:
                    json.dump(index, f, ensure_ascii=False, indent=2)
                os.replace(idx_tmp, idx_path)
            except Exception:
                if os.path.exists(idx_tmp):
                    os.remove(idx_tmp)

    # ===== 功能性函数 =====

    async def add_message(self, group_id: str, user_id: str, nickname: str, timestamp: int,
                      text: str, components: Optional[List[Any]] = None, isDice: bool = False) -> Tuple[bool,str]:
        grp = await self.load_group(group_id)
        active_names = [n for n, s in grp.items() if (s.get("end_time") is None and not s.get("finished", False))]
        if not active_names:
            return False, get_output("log.no_active_session")

        latest_name = active_names[-1]
        sec = grp[latest_name]

        # 解析图片
        images = []
        if components:
            for comp in components:
                if hasattr(comp, "url") and comp.url:
                    images.append(comp.url)
                elif hasattr(comp, "file") and comp.file.startswith(("http://", "https://")):
                    images.append(comp.file)

        # 清理文本
        text_clean = re.sub(r'\[CQ:image,.*?url=.*?(?:,|])', '', text).strip()

        sec.setdefault("messages", []).append({
            "timestamp": timestamp,
            "user_id": user_id,
            "nickname": nickname,
            "text": text_clean,
            "images": images,
            "isDice": isDice
        })

        await self.persist_group(group_id)
        return True, get_output("log.message_added")

    async def new_session(self, group_id: str, name: Optional[str] = None) -> Tuple[bool,str]:
        grp = await self.load_group(group_id)
        unfinished = [n for n, s in grp.items() if not s.get("finished", False)]
        if unfinished:
            return False, get_output("log.unfinished_session", session_name=unfinished[-1])
        name = name or uuid.uuid4().hex[:8]
        grp[name] = {"start_time": int(time.time()), "end_time": None, "messages": [], "finished": False}
        await self.persist_group(group_id)
        return True, get_output("log.new_session", session_name=name)

    async def resume_session(self, group_id: str, name: Optional[str] = None) -> Tuple[bool,str]:
        grp = await self.load_group(group_id)
        if name:
            sec = grp.get(name)
            if not sec: return False, get_output("log.session_not_found", session_name=name)
            if sec.get("finished"): return False, get_output("log.session_finished", session_name=name)
            if sec.get("end_time") is None: return False, get_output("log.session_active", session_name=name)
            sec["end_time"] = None
            await self.persist_group(group_id)
            return True, get_output("log.session_resumed", session_name=name)

        # 自动恢复最后一个暂停会话
        paused = [n for n, s in grp.items() if s.get("end_time") is not None and not s.get("finished", False)]
        if not paused:
            return False, get_output("log.no_paused_session")
        sec = grp[paused[-1]]
        sec["end_time"] = None
        await self.persist_group(group_id)
        return True, get_output("log.session_resumed", session_name=paused[-1])

    async def pause_sessions(self, group_id: str) -> Tuple[bool,str]:
        grp = await self.load_group(group_id)
        active = [n for n, s in grp.items() if s.get("end_time") is None and not s.get("finished", False)]
        if not active:
            return False, get_output("log.no_active_session")
        sec = grp[active[-1]]
        sec["end_time"] = int(time.time())
        await self.persist_group(group_id)
        return True, get_output("log.session_paused", session_name=active[-1])

    async def end_session(self, group_id: str) -> Tuple[bool,str]:
        grp = await self.load_group(group_id)
        active = [n for n, s in grp.items() if s.get("end_time") is None and not s.get("finished", False)]
        if not active:
            return False, get_output("log.no_active_session")
        name = active[-1]
        sec = grp[name]
        sec["end_time"] = int(time.time())
        sec["finished"] = True
        await self.persist_group(group_id)
        return True, await self.export_session(group_id, sec, name)

    async def halt_session(self, group_id: str) -> Tuple[bool,str]:
        grp = await self.load_group(group_id)
        unfinished = [n for n, s in grp.items() if not s.get("finished", False)]
        if not unfinished:
            return False, get_output("log.no_unfinished_session")
        name = unfinished[-1]
        del grp[name]
        await self.persist_group(group_id)
        return True, get_output("log.session_halted", session_name=name)

    async def list_sessions(self, group_id: str) -> List[str]:
        grp = await self.load_group(group_id)
        lines = []
        for name, sec in grp.items():
            st = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(sec.get("start_time", 0)))
            status = "已结束" if sec.get("finished") else ("进行中" if sec.get("end_time") is None else "已暂停")
            lines.append(get_output("log.session_line", session_name=name, start_time=st, status=status, message_count=len(sec.get("messages", []))))
        return lines or [get_output("log.no_sessions")]

    async def delete_session(self, group_id: str, name: str) -> Tuple[bool,str]:
        grp = await self.load_group(group_id)
        if name not in grp:
            return False, get_output("log.session_not_found", session_name=name)
        try:
            os.remove(self._get_session_path(group_id, name))
        except Exception:
            pass
        try:
            os.remove(os.path.join(self.base_dir, "exports", f"{group_id}_{name}.json"))
        except Exception:
            pass
        del grp[name]
        await self.persist_group(group_id)
        return True, get_output("log.session_deleted", session_name=name)

    async def export_session(self, group_id: str, sec: dict, name: str) -> str:
        export_data = {"version": 1, "items": []}
        for m in sec.get("messages", []):
            ts_int = int(m.get("timestamp", int(time.time())))
            time_str = time.strftime("%Y/%m/%d %H:%M:%S", time.localtime(ts_int + 8*3600))
            export_data["items"].append({
                "nickname": m.get("nickname"),
                "IMUserId": m.get("user_id"),
                "time": time_str,
                "message": m.get("text", ""),
                "images": m.get("images", []),
                "isDice": False
            })

        exports_dir = os.path.join(self.base_dir, "exports")
        os.makedirs(exports_dir, exist_ok=True)
        file_name = f"{group_id}_{name}.json"
        file_path = os.path.join(exports_dir, file_name)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
            
        website = get_output("setting.website")
        result_website = f"{website}/?file={file_name}" 
        return get_output("log.session_exported", file_name=file_name, result_website = result_website)
