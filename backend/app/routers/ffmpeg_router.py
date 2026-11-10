import os
import re
import uuid
import subprocess
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends, Body
from fastapi.responses import FileResponse
from backend.app.database import get_db
from backend.app.models import StitchRequest
from backend.app.services.ffmpeg_service import ffmpeg_service
from backend.app.config import PROJECTS_DIR

router = APIRouter(prefix="/api/ffmpeg", tags=["FFmpeg"])

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[àáạảãâầấậẩẫăằắặẳẵ]', 'a', text)
    text = re.sub(r'[èéẹẻẽêềếệểễ]', 'e', text)
    text = re.sub(r'[ìíịỉĩ]', 'i', text)
    text = re.sub(r'[òóọỏõôồốộổỗơờớợởỡ]', 'o', text)
    text = re.sub(r'[ùúụủũưừứựửữ]', 'u', text)
    text = re.sub(r'[ỳýỵỷỹ]', 'y', text)
    text = re.sub(r'[đ]', 'd', text)
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[\s-]+', '-', text)
    return text.strip('-')

@router.get("/status")
async def get_ffmpeg_status():
    installed = ffmpeg_service.check_installed()
    version = await ffmpeg_service.get_version() if installed else "Chưa phát hiện FFmpeg"
    return {
        "installed": installed,
        "path": ffmpeg_service.ffmpeg_bin,
        "version": version
    }

@router.post("/probe")
async def probe_file(file_path: str = Body(..., embed=True)):
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File không tồn tại")
    return await ffmpeg_service.probe_video(file_path)

@router.post("/stitch")
async def stitch_videos(req: StitchRequest, db = Depends(get_db)):
    cursor = await db.execute("SELECT * FROM projects WHERE id = ?", (req.project_id,))
    project = await cursor.fetchone()
    if not project:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")

    p_dict = dict(project)
    
    # Strictly verify both Scene 1 and Scene 2 exist in database and on disk
    c1 = await db.execute("SELECT video_path FROM videos WHERE project_id = ? AND scene_number = 1 ORDER BY created_at DESC LIMIT 1", (req.project_id,))
    r1 = await c1.fetchone()
    c2 = await db.execute("SELECT video_path FROM videos WHERE project_id = ? AND scene_number = 2 ORDER BY created_at DESC LIMIT 1", (req.project_id,))
    r2 = await c2.fetchone()

    v1_str = r1["video_path"] if r1 and r1["video_path"] else str(PROJECTS_DIR / req.project_id / "videos" / "scene1.mp4")
    v2_str = r2["video_path"] if r2 and r2["video_path"] else str(PROJECTS_DIR / req.project_id / "videos" / "scene2.mp4")

    v1_path = Path(v1_str)
    v2_path = Path(v2_str)

    if not r1 or not v1_path.exists() or v1_path.stat().st_size < 10000:
        raise HTTPException(status_code=400, detail="Chưa có Video Cảnh 1 trong dự án. Vui lòng nạp hoặc tạo Video Cảnh 1 trước khi ghép!")
    if not r2 or not v2_path.exists() or v2_path.stat().st_size < 10000:
        raise HTTPException(status_code=400, detail="Chưa có Video Cảnh 2 trong dự án. Bắt buộc phải có đủ 2 cảnh video riêng biệt mới có thể ghép!")

    # Guard against identical duplicate scene videos
    if v1_path.stat().st_size == v2_path.stat().st_size:
        raise HTTPException(
            status_code=400,
            detail="Video Cảnh 1 và Video Cảnh 2 hiện đang là 2 video trùng lặp (giống hệt nhau). Vui lòng bấm 'Tạo Muse AI' hoặc nạp video Cảnh 2 riêng biệt trước khi ghép!"
        )

    # Destination
    exports_dir = PROJECTS_DIR / req.project_id / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    
    slug_name = slugify(p_dict["name"] or "video") or "video"
    out_filename = req.custom_name if req.custom_name else f"{slug_name}_tiktok-affiliate.mp4"
    out_path = exports_dir / out_filename

    # Execute FFmpeg Stitching
    result = await ffmpeg_service.stitch_videos(
        video1_path=str(v1_path),
        video2_path=str(v2_path),
        output_path=str(out_path),
        transition=req.transition or "none",
        transition_duration=req.transition_duration or 0.5,
        volume=req.volume or 1.0,
        trim_v1_start=req.trim_v1_start or 0.0,
        trim_v2_end=req.trim_v2_end or 0.0
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=f"Lỗi ghép video FFmpeg: {result.get('error', 'Lỗi không xác định')}")

    # Record in exports table (replace previous export record so get_project always returns the latest)
    export_id = str(uuid.uuid4())[:8]
    await db.execute("DELETE FROM exports WHERE project_id = ?", (req.project_id,))
    await db.execute("""
        INSERT INTO exports (id, project_id, final_video_path, file_name, duration, resolution, fps, file_size, audio_info)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        export_id, req.project_id, str(out_path), out_filename,
        result.get("duration", 0), result.get("resolution", "1080x1920"),
        result.get("fps", 60), result.get("file_size", 0),
        "AAC Stereo" if result.get("has_audio") else "Không có âm thanh"
    ))

    await db.execute("UPDATE projects SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (req.project_id,))
    await db.commit()

    export_obj = {
        "id": export_id,
        "project_id": req.project_id,
        "final_video_path": str(out_path),
        "file_name": out_filename,
        "duration": result.get("duration", 20.0),
        "resolution": result.get("resolution", "1080x1920"),
        "fps": result.get("fps", 60),
        "file_size": result.get("file_size", 0),
        "audio_info": "AAC Stereo" if result.get("has_audio") else "Không có âm thanh"
    }
    result["export_id"] = export_id
    result["export"] = export_obj
    result["url"] = f"/data/projects/{req.project_id}/exports/{out_filename}?v={export_id}"
    return result

@router.post("/open-folder")
async def open_folder(project_id: str = Body(..., embed=True)):
    folder_path = PROJECTS_DIR / project_id / "exports"
    if not folder_path.exists():
        folder_path = PROJECTS_DIR / project_id
    
    # Open folder in Windows File Explorer
    try:
        subprocess.Popen(f'explorer "{str(folder_path)}"')
        return {"success": True, "message": "Đã mở thư mục lưu video"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/download/{project_id}/{filename}")
async def download_export(project_id: str, filename: str):
    file_path = PROJECTS_DIR / project_id / "exports" / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File không tồn tại")
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="video/mp4"
    )

