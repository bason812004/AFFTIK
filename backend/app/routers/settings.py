from fastapi import APIRouter, Depends, Body
from backend.app.database import get_db
from backend.app.services.ffmpeg_service import ffmpeg_service
from backend.app.services.browser_manager import browser_manager

router = APIRouter(prefix="/api/settings", tags=["Settings"])

@router.get("")
async def get_settings(db = Depends(get_db)):
    cursor = await db.execute("SELECT key, value FROM settings")
    rows = await cursor.fetchall()
    settings_dict = {r["key"]: r["value"] for r in rows}
    
    # Check services status
    ffmpeg_ok = ffmpeg_service.check_installed()
    ffmpeg_ver = await ffmpeg_service.get_version() if ffmpeg_ok else "Chưa cài đặt"
    
    return {
        "settings": settings_dict,
        "services": {
            "ffmpeg": {
                "available": ffmpeg_ok,
                "version": ffmpeg_ver,
                "path": ffmpeg_service.ffmpeg_bin
            }
        }
    }

@router.post("")
async def update_settings(data: dict = Body(...), db = Depends(get_db)):
    for k, v in data.items():
        await db.execute("""
            INSERT INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
        """, (k, str(v)))
    await db.commit()
    return {"success": True, "message": "Đã lưu cài đặt"}

@router.get("/dashboard-stats")
async def get_dashboard_stats(db = Depends(get_db)):
    # Total projects
    p_cur = await db.execute("SELECT COUNT(*) FROM projects")
    total_projects = (await p_cur.fetchone())[0]

    # Completed projects
    c_cur = await db.execute("SELECT COUNT(*) FROM projects WHERE status = 'completed'")
    completed_projects = (await c_cur.fetchone())[0]

    # In progress projects
    ongoing_projects = max(0, total_projects - completed_projects)

    # Characters generated
    char_cur = await db.execute("SELECT COUNT(*) FROM assets WHERE asset_type = 'ai_character'")
    total_characters = (await char_cur.fetchone())[0]

    # Scene videos created
    vid_cur = await db.execute("SELECT COUNT(*) FROM videos")
    total_scene_videos = (await vid_cur.fetchone())[0]

    # Final stitched exports
    exp_cur = await db.execute("SELECT COUNT(*) FROM exports")
    total_exports = (await exp_cur.fetchone())[0]

    # Status of services
    ffmpeg_ok = ffmpeg_service.check_installed()

    return {
        "total_projects": total_projects,
        "completed_projects": completed_projects,
        "ongoing_projects": ongoing_projects,
        "total_characters": total_characters,
        "total_scene_videos": total_scene_videos,
        "total_exports": total_exports,
        "ffmpeg_status": "ready" if ffmpeg_ok else "missing"
    }

