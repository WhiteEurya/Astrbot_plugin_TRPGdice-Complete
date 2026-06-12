# app/main.py
import os
import re
from fastapi import FastAPI, Path, Query
from fastapi.responses import FileResponse, JSONResponse
from config import EXPORT_ROOT
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 也可以指定 ["http://localhost:5173"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 空白 JSON 结构
EMPTY_EXPORT = {"version": 1, "items": []}

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
FALLBACK_EXPORT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", "data", "group_logs", "exports"))

def iter_export_roots():
    roots = [EXPORT_ROOT, FALLBACK_EXPORT_ROOT]
    seen = set()
    for root in roots:
        if not root:
            continue
        normalized = os.path.abspath(root)
        if normalized in seen:
            continue
        seen.add(normalized)
        yield normalized

def resolve_export_path_by_uuid(log_uuid: str):
    if not re.fullmatch(r"[0-9a-fA-F]{8}", log_uuid or ""):
        return None
    safe_name = f"{log_uuid.lower()}.json"
    for root in iter_export_roots():
        file_path = os.path.join(root, safe_name)
        if os.path.isfile(file_path):
            return file_path
    return os.path.join(EXPORT_ROOT, safe_name)

@app.get("/export", response_class=JSONResponse)
async def get_export_by_uuid(uuid: str = Query("", description="8 位日志 uuid")):
    """
    不带 uuid 时，返回空白结构；带 uuid 时，解析 exports/<uuid>.json。
    """
    if not uuid:
        return EMPTY_EXPORT

    file_path = resolve_export_path_by_uuid(uuid)
    if not file_path or not os.path.isfile(file_path):
        return EMPTY_EXPORT
    return FileResponse(file_path, media_type="application/json")

@app.get("/export/{file_name:path}")
async def get_export(
    file_name: str = Path(..., description="JSON 文件名，需包含 .json 后缀")
):
    """
    兼容旧链接 /export/{file}.json。
    """
    if re.fullmatch(r"[0-9a-fA-F]{8}", file_name or ""):
        file_path = resolve_export_path_by_uuid(file_name)
        if file_path and os.path.isfile(file_path):
            return FileResponse(file_path, media_type="application/json")
        return EMPTY_EXPORT

    # 1. 后缀校验 & 防止路径穿越
    if ".." in file_name or not file_name.endswith(".json"):
        return EMPTY_EXPORT

    # 2. basename 保证不会访问导出目录以外的文件
    safe_name = os.path.basename(file_name)
    file_path = None
    for root in iter_export_roots():
        candidate = os.path.join(root, safe_name)
        if os.path.isfile(candidate):
            file_path = candidate
            break

    # 3. 文件不存在 → 返回空白
    if not file_path:
        return EMPTY_EXPORT

    # 4. 文件存在 → 返回原始 JSON
    return FileResponse(file_path, media_type="application/json")
