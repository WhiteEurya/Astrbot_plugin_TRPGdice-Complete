# app/main.py
import os
from fastapi import FastAPI, Path
from fastapi.responses import FileResponse, JSONResponse
from config import EXPORT_ROOT
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 空白 JSON 结构
EMPTY_EXPORT = {"version": 1, "items": []}

@app.get("/export", response_class=JSONResponse)
async def get_blank_export():
    """
    不带文件名时，返回空白结构
    """
    return EMPTY_EXPORT

@app.get("/export/{file_name:path}")
async def get_export(
    file_name: str = Path(..., description="JSON 文件名，需包含 .json 后缀")
):
    """
    带文件名时：
    - 后缀不是 .json 或包含路径穿越标记，返回空白
    - 文件不存在，返回空白
    - 文件存在，直接以 application/json 返回
    """
    # 1. 后缀校验 & 防止路径穿越
    if ".." in file_name or not file_name.endswith(".json"):
        return EMPTY_EXPORT

    # 2. basename 保证不会访问导出目录以外的文件
    safe_name = os.path.basename(file_name)
    file_path = os.path.join(EXPORT_ROOT, safe_name)

    # 3. 文件不存在 → 返回空白
    if not os.path.isfile(file_path):
        return EMPTY_EXPORT

    # 4. 文件存在 → 返回原始 JSON
    return FileResponse(file_path, media_type="application/json")
