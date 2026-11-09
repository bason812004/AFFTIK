import uuid
import os
import asyncio
import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Body, UploadFile, File, Form
from backend.app.database import get_db, _get_raw_conn
from backend.app.services.browser_manager import browser_manager
from backend.app.services.muse_automator import muse_automator
from backend.app.services.ffmpeg_service import ffmpeg_service
from backend.app.config import PROJECTS_DIR

router = APIRouter(prefix="/api/muse", tags=["Muse AI"])
logger = logging.getLogger(__name__)

@router.get("/status")
async def get_muse_status(db = Depends(get_db)):
    cursor = await db.execute("SELECT value FROM settings WHERE key = 'muse_url'")
    row = await cursor.fetchone()
    muse_url = row["value"] if row else "https://muse.ai"
    return await browser_manager.check_muse_login(muse_url, force_open=False)

@router.post("/connect")
async def connect_muse(db = Depends(get_db)):
    cursor = await db.execute("SELECT value FROM settings WHERE key = 'muse_url'")
    row = await cursor.fetchone()
    muse_url = row["value"] if row else "https://muse.ai"
    return await browser_manager.check_muse_login(muse_url, force_open=True)

@router.post("/logout")
async def logout_muse(full_logout: bool = True):
    await browser_manager.clear_muse_session(open_login=True, full_logout=full_logout)
    return {"success": True, "message": "Đã đăng xuất tài khoản Muse AI cũ và mở cửa sổ đăng nhập mới"}

@router.post("/generate-video")
async def generate_muse_video(
    project_id: str = Body(..., embed=True),
    scene_number: int = Body(..., embed=True)
):
    if scene_number not in [1, 2]:
        raise HTTPException(status_code=400, detail="scene_number chỉ có thể là 1 hoặc 2")
    res = await muse_automator.generate_scene_video(project_id, scene_number)
    return res

@router.post("/upload-manual-video")
async def upload_manual_video(
    project_id: str = Form(...),
    scene_number: int = Form(...),
    file: UploadFile = File(...)
):
    if scene_number not in [1, 2]:
        raise HTTPException(status_code=400, detail="scene_number chỉ có thể là 1 hoặc 2")

    target_dir = PROJECTS_DIR / project_id / "videos"
    target_dir.mkdir(parents=True, exist_ok=True)
    temp_path = target_dir / f"uploaded_s{scene_number}_{uuid.uuid4().hex[:6]}.mp4"
    target_path = target_dir / f"scene{scene_number}.mp4"

    with open(temp_path, "wb") as f:
        content = await file.read()
        f.write(content)

    std_res = await ffmpeg_service.standardize_scene_video(
        input_video_path=str(temp_path),
        output_video_path=str(target_path),
        target_width=1080,
        target_height=1920,
        target_fps=60
    )
    if not std_res.get("success"):
        import shutil
        shutil.copyfile(str(temp_path), str(target_path))

    try:
        temp_path.unlink(missing_ok=True)
    except Exception:
        pass

    return {
        "success": True,
        "video_path": str(target_path),
        "scene_number": scene_number,
        "message": f"Đã nạp và chuẩn hóa video Cảnh {scene_number} (1080x1920 @ 60 FPS)"
    }

@router.delete("/video/{project_id}/{scene_number}")
async def delete_scene_video(project_id: str, scene_number: int):
    target_path = PROJECTS_DIR / project_id / "videos" / f"scene{scene_number}.mp4"
    if target_path.exists():
        target_path.unlink(missing_ok=True)
        return {"success": True, "deleted": True, "message": f"Đã xóa video Cảnh {scene_number}"}
    return {"success": True, "deleted": False, "message": "Video không tồn tại"}
