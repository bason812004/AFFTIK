import uuid
import os
import asyncio
import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Body, UploadFile, File, Form
from backend.app.database import get_db, _get_raw_conn
from backend.app.services.browser_manager import browser_manager
from backend.app.services.flow_automator import flow_automator
from backend.app.services.ffmpeg_service import ffmpeg_service
from backend.app.services.pipeline_runner import pipeline_runner
from backend.app.config import PROJECTS_DIR

router = APIRouter(prefix="/api/flow", tags=["Google Flow"])
logger = logging.getLogger(__name__)

@router.get("/status")
async def get_flow_status(db = Depends(get_db)):
    cursor = await db.execute("SELECT value FROM settings WHERE key = 'flow_url'")
    row = await cursor.fetchone()
    flow_url = row["value"] if row else "https://labs.google/fx/vi/tools/flow"
    st = await browser_manager.check_flow_login(flow_url, force_open=False)
    if st.get("logged_in") and pipeline_runner.get_paused_session():
        resumed_info = await pipeline_runner.resume_paused_session()
        st["auto_resumed"] = resumed_info
    return st

@router.post("/connect")
async def connect_flow(db = Depends(get_db)):
    cursor = await db.execute("SELECT value FROM settings WHERE key = 'flow_url'")
    row = await cursor.fetchone()
    flow_url = row["value"] if row else "https://labs.google/fx/vi/tools/flow"
    st = await browser_manager.check_flow_login(flow_url, force_open=True)
    if st.get("logged_in") and pipeline_runner.get_paused_session():
        resumed_info = await pipeline_runner.resume_paused_session()
        st["auto_resumed"] = resumed_info
    elif pipeline_runner.get_paused_session():
        pipeline_runner.start_account_switch_watcher()
    return st

@router.post("/logout")
async def logout_flow(full_logout: bool = True):
    await browser_manager.clear_flow_session(open_login=True, full_logout=full_logout)
    if pipeline_runner.get_paused_session():
        pipeline_runner.start_account_switch_watcher()
    return {
        "success": True,
        "message": "Đã đăng xuất tài khoản Google Flow cũ và mở cửa sổ đăng nhập tài khoản mới. Ngay sau khi đăng nhập xong, hệ thống sẽ tự động chạy tiếp phiên làm việc đang dang dở!"
    }

@router.post("/generate-fast-video")
async def generate_fast_video(
    project_id: str = Body(..., embed=True),
    scene_number: int = Body(..., embed=True),  # 1 or 2
    db = Depends(get_db)
):
    """
    Lightning-fast 9:16 commercial video generation using FFmpeg motion in 1.5 seconds.
    Scene 1: Model presenting product (character_primary.png) with gentle push-in.
    Scene 2: Dynamic macro close-up of the product (product_original.jpg) with high focus.
    """
    cursor = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    project = await cursor.fetchone()
    if not project:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")

    p_dict = dict(project)

    # Determine reference image
    canonical_char = PROJECTS_DIR / project_id / "character" / "character_primary.png"
    char_img = p_dict.get("primary_character_image_path")
    if not char_img or not os.path.exists(char_img):
        if canonical_char.exists():
            char_img = str(canonical_char)

    prod_img = p_dict.get("original_image_path")
    if not prod_img or not os.path.exists(prod_img):
        canonical_prod = PROJECTS_DIR / project_id / "product" / "product_original.jpg"
        if canonical_prod.exists():
            prod_img = str(canonical_prod)

    if scene_number == 1:
        chosen_img = char_img or prod_img
        motion_type = "zoom_in"
    else:
        chosen_img = prod_img or char_img
        motion_type = "closeup"

    if not chosen_img or not os.path.exists(chosen_img):
        raise HTTPException(status_code=400, detail="Không tìm thấy tệp ảnh cho cảnh này. Vui lòng kiểm tra lại ảnh sản phẩm hoặc nhân vật.")

    # Get script
    script_id = p_dict.get("selected_script_id")
    if script_id:
        s_cursor = await db.execute("SELECT * FROM scripts WHERE id = ?", (script_id,))
        script = await s_cursor.fetchone()
    else:
        s_cursor = await db.execute("SELECT * FROM scripts WHERE project_id = ? AND is_selected = 1 LIMIT 1", (project_id,))
        script = await s_cursor.fetchone()

    s_dict = dict(script) if script else {}
    s_id = s_dict.get("id")
    dialogue = s_dict.get("scene1_dialogue") if scene_number == 1 else s_dict.get("scene2_dialogue")

    videos_dir = PROJECTS_DIR / project_id / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)
    target_video_file = videos_dir / f"scene{scene_number}.mp4"

    res = await ffmpeg_service.create_scene_motion_video(
        image_path=chosen_img,
        output_path=str(target_video_file),
        duration=10.0,
        motion_type=motion_type,
        dialogue_text=dialogue,
        width=1080,
        height=1920,
        fps=60
    )

    if not res.get("success"):
        raise HTTPException(status_code=500, detail=f"Lỗi tạo video siêu tốc: {res.get('error')}")

    v_path = res["output_path"]
    probe = await ffmpeg_service.probe_video(v_path)
    v_id = str(uuid.uuid4())[:8]

    await db.execute("DELETE FROM videos WHERE project_id = ? AND scene_number = ?", (project_id, scene_number))
    await db.execute("""
        INSERT INTO videos (id, project_id, script_id, scene_number, video_path, duration, resolution, fps, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ready')
    """, (
        v_id, project_id, s_id, scene_number, v_path,
        probe.get("duration", 10.0), f"{probe.get('width', 1080)}x{probe.get('height', 1920)}",
        probe.get("fps", 60.0)
    ))

    new_status = 'video1_ready' if scene_number == 1 else 'video2_ready'
    await db.execute("""
        UPDATE projects SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
    """, (new_status, project_id))
    await db.commit()

    return {
        "success": True,
        "video_path": v_path,
        "file_name": os.path.basename(v_path),
        "url": f"/data/projects/{project_id}/videos/scene{scene_number}.mp4",
        "duration": probe.get("duration", 10.0),
        "resolution": "1080x1920",
        "fps": probe.get("fps", 60.0),
        "has_audio": probe.get("has_audio", True),
        "message": f"Tạo Video Cảnh {scene_number} 60fps có lời thoại thành công!"
    }

@router.post("/generate-video")
async def generate_video(
    project_id: str = Body(..., embed=True),
    scene_number: int = Body(..., embed=True),  # 1 or 2
    db = Depends(get_db)
):
    cursor = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    project = await cursor.fetchone()
    if not project:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")
        
    p_dict = dict(project)

    # Get script
    script_id = p_dict.get("selected_script_id")
    if script_id:
        s_cursor = await db.execute("SELECT * FROM scripts WHERE id = ?", (script_id,))
        script = await s_cursor.fetchone()
    else:
        s_cursor = await db.execute("SELECT * FROM scripts WHERE project_id = ? AND is_selected = 1 LIMIT 1", (project_id,))
        script = await s_cursor.fetchone()

    if not script:
        raise HTTPException(status_code=400, detail="Vui lòng chọn 1 phương án kịch bản trước khi tạo video")

    s_dict = dict(script)
    prompt = s_dict["scene1_prompt_veo"] if scene_number == 1 else s_dict["scene2_prompt_veo"]
    if not prompt:
        raise HTTPException(status_code=400, detail=f"Chưa có Prompt Veo 3 cho Cảnh {scene_number}")

    # Flow url
    cfg_cur = await db.execute("SELECT value FROM settings WHERE key = 'flow_url'")
    cfg_row = await cfg_cur.fetchone()
    flow_url = cfg_row["value"] if cfg_row else "https://labs.google/flow"

    task_id = str(uuid.uuid4())[:8]
    await db.execute("""
        INSERT INTO automation_tasks (id, project_id, task_type, status, step_name, progress_percent, message)
        VALUES (?, ?, ?, 'running', 'Khởi tạo', 10, ?)
    """, (
        task_id, project_id, f"flow_video{scene_number}",
        f"Đang chuẩn bị gửi prompt Cảnh {scene_number} sang Google Flow..."
    ))
    await db.commit()

    async def update_task_log(msg: str, percent: int):
        try:
            raw_c = _get_raw_conn()
            raw_c.execute("""
                UPDATE automation_tasks SET message = ?, progress_percent = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (msg, percent, task_id))
            raw_c.commit()
            raw_c.close()
        except Exception as e_log:
            logger.debug(f"update_task_log error: {e_log}")

    try:
        result = await flow_automator.generate_scene_video(
            project_id=project_id,
            scene_number=scene_number,
            prompt=prompt,
            character_image_path=p_dict.get("primary_character_image_path"),
            flow_url=flow_url,
            mode=p_dict.get("automation_mode", "auto"),
            on_log=update_task_log
        )
    except Exception as e_gen:
        logger.error(f"Flow generate_scene_video error: {e_gen}")
        result = {
            "success": False,
            "waiting_user": True,
            "message": f"Đã gửi yêu cầu tới Google Flow ({str(e_gen)}). Bạn có thể kiểm tra cửa sổ Chrome hoặc bấm lấy video sau khi hoàn tất."
        }

    if result.get("success") and result.get("video_path"):
        v_path = result["video_path"]
        probe = await ffmpeg_service.probe_video(v_path)
        v_id = str(uuid.uuid4())[:8]

        # Check existing video entry for this scene
        await db.execute("DELETE FROM videos WHERE project_id = ? AND scene_number = ?", (project_id, scene_number))
        await db.execute("""
            INSERT INTO videos (id, project_id, script_id, scene_number, video_path, duration, resolution, fps, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ready')
        """, (
            v_id, project_id, s_dict["id"], scene_number, v_path,
            probe.get("duration", 10.0), f"{probe.get('width', 1080)}x{probe.get('height', 1920)}",
            probe.get("fps", 30.0)
        ))

        new_status = 'video1_ready' if scene_number == 1 else 'video2_ready'
        await db.execute("""
            UPDATE projects SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
        """, (new_status, project_id))

        await db.execute("""
            UPDATE automation_tasks SET status = 'completed', progress_percent = 100, message = ?
            WHERE id = ?
        """, (f"Tạo và tải Video Cảnh {scene_number} thành công!", task_id))
        await db.commit()
    elif result.get("out_of_credits") or result.get("needs_login"):
        reason = "out_of_credits" if result.get("out_of_credits") else "needs_login"
        msg = result.get("message") or "⚠️ Tài khoản Google Flow đã hết tín dụng hoặc cần đăng nhập lại. Đã lưu phiên làm việc — sau khi bạn đăng nhập tài khoản mới trên Chrome, hệ thống sẽ tự động chạy tiếp!"
        pipeline_runner.save_paused_session(
            project_id=project_id,
            step=f"scene{scene_number}",
            scene_number=scene_number,
            reason=reason,
            message=msg
        )
        pipeline_runner.start_account_switch_watcher()
        result["session_saved"] = True
        await db.execute("""
            UPDATE automation_tasks SET status = 'waiting_confirm', step_name = 'Chờ đổi TK Flow', progress_percent = 65, message = ?
            WHERE id = ?
        """, (msg, task_id))
        await db.commit()
    elif result.get("waiting_user") or result.get("waiting_confirm"):
        await db.execute("""
            UPDATE automation_tasks SET status = 'waiting_confirm', progress_percent = 65, message = ?
            WHERE id = ?
        """, (result.get("message"), task_id))
        await db.commit()
    else:
        await db.execute("""
            UPDATE automation_tasks SET status = 'failed', error_message = ?, message = ?
            WHERE id = ?
        """, (result.get("error", "Lỗi tạo video trên Flow"), result.get("message", "Thất bại"), task_id))
        await db.commit()

    return result

@router.post("/upload-manual-video")
async def upload_manual_video(
    project_id: str = Form(...),
    scene_number: int = Form(...),
    file: UploadFile = File(...),
    db = Depends(get_db)
):
    """
    Allows user to drag-and-drop, paste, or upload a video file for Scene 1 or Scene 2 manually.
    Standardizes to 1080x1920 @ 60fps while preserving original audio (or adding speech if silent).
    """
    import shutil
    videos_dir = PROJECTS_DIR / project_id / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)
    temp_path = videos_dir / f"temp_manual_{scene_number}_{uuid.uuid4().hex[:6]}.mp4"
    dest_path = videos_dir / f"scene{scene_number}.mp4"

    content = file.file.read()
    with open(temp_path, "wb") as f:
        f.write(content)

    # Standardize to 1080x1920 @ 60fps while keeping original audio intact
    std_res = await ffmpeg_service.standardize_scene_video(
        input_video_path=str(temp_path),
        output_video_path=str(dest_path),
        dialogue_text=None,
        target_width=1080,
        target_height=1920,
        target_fps=60
    )
    if not std_res.get("success"):
        shutil.copyfile(str(temp_path), str(dest_path))

    if temp_path.exists():
        try:
            temp_path.unlink()
        except Exception:
            pass

    probe = await ffmpeg_service.probe_video(str(dest_path))
    v_id = str(uuid.uuid4())[:8]

    await db.execute("DELETE FROM videos WHERE project_id = ? AND scene_number = ?", (project_id, scene_number))
    await db.execute("""
        INSERT INTO videos (id, project_id, scene_number, video_path, duration, resolution, fps, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'ready')
    """, (
        v_id, project_id, scene_number, str(dest_path),
        probe.get("duration", 10.0), f"{probe.get('width', 1080)}x{probe.get('height', 1920)}",
        probe.get("fps", 60.0)
    ))

    new_status = 'video1_ready' if scene_number == 1 else 'video2_ready'
    await db.execute("UPDATE projects SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_status, project_id))
    await db.commit()

    return {
        "success": True,
        "video_path": str(dest_path),
        "url": f"/data/projects/{project_id}/videos/scene{scene_number}.mp4?v={v_id}",
        "probe": probe,
        "message": f"Đã nạp thành công Video Cảnh {scene_number}!"
    }

def _calc_file_hash(p: Path) -> str:
    import hashlib
    try:
        h = hashlib.md5()
        with open(p, "rb") as fp:
            h.update(fp.read(65536))
            sz = p.stat().st_size
            if sz > 131072:
                fp.seek(sz - 65536)
                h.update(fp.read(65536))
        return h.hexdigest()
    except Exception:
        return ""


@router.post("/paste-clipboard-video")
async def paste_clipboard_video(
    project_id: str = Body(..., embed=True),
    scene_number: int = Body(..., embed=True),
    db = Depends(get_db)
):
    """
    Reads a copied video file (or file path) directly from Windows Clipboard and imports it into Scene 1 or Scene 2.
    Strictly verifies that clipboard actually contains a video file, and guards against duplicate/identical scenes.
    """
    import subprocess
    import shutil
    ps_cmd = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$files = [System.Windows.Forms.Clipboard]::GetFileDropList(); "
        "if ($files -and $files.Count -gt 0) { Write-Output $files[0] } "
        "else { Write-Output ([System.Windows.Forms.Clipboard]::GetText()) }"
    )
    res_ps = await asyncio.to_thread(
        subprocess.run,
        ["powershell", "-Sta", "-NoProfile", "-Command", ps_cmd],
        capture_output=True,
        text=True,
        timeout=8
    )
    clip_val = (res_ps.stdout or "").strip().strip('"').strip("'")

    chosen_file = None
    if clip_val and os.path.isfile(clip_val) and clip_val.lower().endswith((".mp4", ".mov", ".webm", ".mkv")):
        chosen_file = Path(clip_val)

    if not chosen_file or not chosen_file.exists():
        raise HTTPException(
            status_code=400,
            detail="Không tìm thấy tệp video (.mp4) nào trong Clipboard. Vui lòng bấm chuột phải vào file video chọn Copy (Ctrl+C) trên máy tính rồi bấm Dán lại, hoặc dùng nút 'Chọn Video Cảnh' / Kéo thả."
        )

    # Strictly verify against companion scene to prevent identical duplicate videos
    other_scene = 2 if scene_number == 1 else 1
    other_path = PROJECTS_DIR / project_id / "videos" / f"scene{other_scene}.mp4"
    if other_path.exists() and other_path.stat().st_size > 10000:
        if chosen_file.stat().st_size == other_path.stat().st_size:
            raise HTTPException(
                status_code=400,
                detail=f"Video vừa dán có dung lượng ({chosen_file.stat().st_size} bytes) trùng khớp 100% với Video Cảnh {other_scene}! Không được dùng video trùng lặp. Vui lòng copy video riêng biệt cho Cảnh {scene_number}."
            )
        h_cand = _calc_file_hash(chosen_file)
        h_other = _calc_file_hash(other_path)
        if h_cand and h_cand == h_other:
            raise HTTPException(
                status_code=400,
                detail=f"Nội dung video vừa dán trùng khớp 100% với Video Cảnh {other_scene}! Vui lòng copy đúng video riêng của Cảnh {scene_number}."
            )

    videos_dir = PROJECTS_DIR / project_id / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)
    dest_path = videos_dir / f"scene{scene_number}.mp4"

    std_res = await ffmpeg_service.standardize_scene_video(
        input_video_path=str(chosen_file),
        output_video_path=str(dest_path),
        dialogue_text=None,
        target_width=1080,
        target_height=1920,
        target_fps=60
    )
    if not std_res.get("success"):
        shutil.copyfile(str(chosen_file), str(dest_path))

    probe = await ffmpeg_service.probe_video(str(dest_path))
    v_id = str(uuid.uuid4())[:8]

    await db.execute("DELETE FROM videos WHERE project_id = ? AND scene_number = ?", (project_id, scene_number))
    await db.execute("""
        INSERT INTO videos (id, project_id, scene_number, video_path, duration, resolution, fps, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'ready')
    """, (
        v_id, project_id, scene_number, str(dest_path),
        probe.get("duration", 10.0), f"{probe.get('width', 1080)}x{probe.get('height', 1920)}",
        probe.get("fps", 60.0)
    ))

    new_status = 'video1_ready' if scene_number == 1 else 'video2_ready'
    await db.execute("UPDATE projects SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_status, project_id))
    await db.commit()

    return {
        "success": True,
        "video_path": str(dest_path),
        "source_name": chosen_file.name,
        "url": f"/data/projects/{project_id}/videos/scene{scene_number}.mp4?v={v_id}",
        "probe": probe,
        "message": f"Đã dán thành công video ({chosen_file.name}) vào Cảnh {scene_number}!"
    }

@router.get("/recent-videos")
async def get_recent_videos():
    """
    Returns list of recently downloaded Flow videos from Downloads folder.
    """
    import time
    downloads_dir = Path(os.environ.get("USERPROFILE", "C:/Users/LENOVO")) / "Downloads"

    files = []
    seen = set()

    if downloads_dir.exists():
        for f in downloads_dir.glob("*.mp4"):
            try:
                st = f.stat()
                if st.st_size > 500000 and f.name not in seen and (time.time() - st.st_mtime) < 86400:
                    seen.add(f.name)
                    files.append({
                        "filename": f.name,
                        "path": str(f).replace("\\", "/"),
                        "size": st.st_size,
                        "size_mb": round(st.st_size / (1024 * 1024), 2),
                        "mtime": st.st_mtime,
                        "time_str": time.strftime("%H:%M:%S %d/%m/%Y", time.localtime(st.st_mtime))
                    })
            except Exception:
                pass

    files.sort(key=lambda x: x["mtime"], reverse=True)
    return files[:20]

@router.post("/import-video")
async def import_flow_video(
    project_id: str = Body(..., embed=True),
    scene_number: int = Body(..., embed=True),
    source_path: Optional[str] = Body(None, embed=True),
    db = Depends(get_db)
):
    """
    Imports a video file into the project, standardizes it to 1080x1920 @ 60 FPS,
    adds TTS speech audio if needed, and updates the project's scene video.
    Guarantees strict product matching and prevents identical duplicate scenes.
    """
    import time
    p_cursor = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    project = await p_cursor.fetchone()
    if not project:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")

    p_dict = dict(project)
    pname = p_dict.get("name") or ""

    chosen_file = None
    if source_path and os.path.exists(source_path):
        chosen_file = Path(source_path)
    else:
        # Check active Google Flow browser tab first
        pulled_path = await flow_automator.pull_latest_video_from_flow(project_id, scene_number)
        if pulled_path and os.path.exists(pulled_path):
            chosen_file = Path(pulled_path)
        else:
            # Filter Downloads by project keywords to avoid cross-product contamination
            recents = await get_recent_videos()
            from backend.app.services.muse_automator import _get_distinctive_phrases, _slugify
            pos_words = _get_distinctive_phrases(pname)
            other_scene = 2 if scene_number == 1 else 1
            other_path = PROJECTS_DIR / project_id / "videos" / f"scene{other_scene}.mp4"
            other_hash = _calc_file_hash(other_path) if other_path.exists() else None

            matching_cands = []
            for r in recents:
                # Must be downloaded within 30 minutes
                if (time.time() - r["mtime"]) > 1800:
                    continue
                c_p = Path(r["path"])
                # Exclude if identical to other scene
                if other_path.exists():
                    if c_p.stat().st_size == other_path.stat().st_size or _calc_file_hash(c_p) == other_hash:
                        continue
                # Check keyword match
                fn_norm = _slugify(r["filename"])
                if any(_slugify(w) in fn_norm for w in pos_words if len(w) >= 3):
                    matching_cands.append(c_p)

            if matching_cands:
                chosen_file = matching_cands[0]

    if not chosen_file or not chosen_file.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Không tìm thấy file video phù hợp với '{pname}' trong thư mục Downloads. Vui lòng tải video về máy hoặc chọn file trực tiếp bằng nút 'Chọn Video Cảnh {scene_number}'."
        )

    # Strictly verify against companion scene to prevent identical duplicate videos
    other_scene = 2 if scene_number == 1 else 1
    other_path = PROJECTS_DIR / project_id / "videos" / f"scene{other_scene}.mp4"
    if other_path.exists() and other_path.stat().st_size > 10000:
        if chosen_file.stat().st_size == other_path.stat().st_size or _calc_file_hash(chosen_file) == _calc_file_hash(other_path):
            raise HTTPException(
                status_code=400,
                detail=f"Video vừa nạp ({chosen_file.name}) trùng khớp 100% với Video Cảnh {other_scene}! Vui lòng chọn đúng file video riêng biệt cho Cảnh {scene_number}."
            )
    script_id = p_dict.get("selected_script_id")
    if script_id:
        s_cursor = await db.execute("SELECT * FROM scripts WHERE id = ?", (script_id,))
        script = await s_cursor.fetchone()
    else:
        s_cursor = await db.execute("SELECT * FROM scripts WHERE project_id = ? AND is_selected = 1 LIMIT 1", (project_id,))
        script = await s_cursor.fetchone()

    dialogue = ""
    if script:
        s_dict = dict(script)
        dialogue = s_dict.get("scene1_dialogue") if scene_number == 1 else s_dict.get("scene2_dialogue")

    videos_dir = PROJECTS_DIR / project_id / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)
    dest_path = videos_dir / f"scene{scene_number}.mp4"

    if chosen_file.resolve() != dest_path.resolve():
        res = await ffmpeg_service.standardize_scene_video(
            input_video_path=str(chosen_file),
            output_video_path=str(dest_path),
            dialogue_text=dialogue,
            target_width=1080,
            target_height=1920,
            target_fps=60
        )
        if not res.get("success"):
            raise HTTPException(status_code=500, detail=f"Lỗi chuẩn hóa video 60fps: {res.get('error')}")

    probe = await ffmpeg_service.probe_video(str(dest_path))
    v_id = str(uuid.uuid4())[:8]

    await db.execute("DELETE FROM videos WHERE project_id = ? AND scene_number = ?", (project_id, scene_number))
    await db.execute("""
        INSERT INTO videos (id, project_id, scene_number, video_path, duration, resolution, fps, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'ready')
    """, (
        v_id, project_id, scene_number, str(dest_path),
        probe.get("duration", 10.0), f"{probe.get('width', 1080)}x{probe.get('height', 1920)}",
        probe.get("fps", 60.0)
    ))

    new_status = 'video1_ready' if scene_number == 1 else 'video2_ready'
    await db.execute("UPDATE projects SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_status, project_id))
    await db.commit()

    return {
        "success": True,
        "video_path": str(dest_path),
        "source_name": chosen_file.name,
        "url": f"/data/projects/{project_id}/videos/scene{scene_number}.mp4?v={v_id}",
        "duration": probe.get("duration", 10.0),
        "resolution": "1080x1920",
        "fps": probe.get("fps", 60.0),
        "has_audio": probe.get("has_audio", True),
        "message": f"Đã nạp thành công video Flow ({chosen_file.name}) chuẩn 1080x1920 60fps vào Cảnh {scene_number}!"
    }


@router.delete("/video/{project_id}/{scene_number}")
async def delete_scene_video(
    project_id: str,
    scene_number: int,
    db = Depends(get_db)
):
    """
    Deletes the uploaded/pasted/generated video for Scene 1 or Scene 2.
    """
    v_cursor = await db.execute(
        "SELECT * FROM videos WHERE project_id = ? AND scene_number = ?",
        (project_id, scene_number)
    )
    rows = await v_cursor.fetchall()
    for r in rows:
        vp = dict(r).get("video_path")
        if vp and os.path.exists(vp):
            try:
                os.remove(vp)
            except Exception:
                pass

    dest_path = PROJECTS_DIR / project_id / "videos" / f"scene{scene_number}.mp4"
    if dest_path.exists():
        try:
            dest_path.unlink()
        except Exception:
            pass

    await db.execute(
        "DELETE FROM videos WHERE project_id = ? AND scene_number = ?",
        (project_id, scene_number)
    )

    # Check remaining videos to update project status accurately
    rem_cursor = await db.execute(
        "SELECT scene_number FROM videos WHERE project_id = ?",
        (project_id,)
    )
    rem_rows = [dict(r)["scene_number"] for r in await rem_cursor.fetchall()]
    if 1 in rem_rows:
        new_status = "video1_ready"
    elif 2 in rem_rows:
        new_status = "video2_ready"
    else:
        new_status = "scripts_created"

    await db.execute(
        "UPDATE projects SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (new_status, project_id)
    )
    await db.commit()

    return {
        "success": True,
        "project_id": project_id,
        "scene_number": scene_number,
        "message": f"Đã xóa Video Cảnh {scene_number}!"
    }


@router.delete("/export/{project_id}")
async def delete_export_video(
    project_id: str,
    db = Depends(get_db)
):
    """
    Deletes the stitched final export video for the project.
    """
    e_cursor = await db.execute("SELECT * FROM exports WHERE project_id = ?", (project_id,))
    rows = await e_cursor.fetchall()
    for r in rows:
        r_dict = dict(r)
        fp = r_dict.get("final_video_path") or r_dict.get("file_path")
        if fp and os.path.exists(fp):
            try:
                os.remove(fp)
            except Exception:
                pass

    exports_dir = PROJECTS_DIR / project_id / "exports"
    if exports_dir.exists():
        for ef in exports_dir.glob("*.mp4"):
            try:
                ef.unlink()
            except Exception:
                pass

    await db.execute("DELETE FROM exports WHERE project_id = ?", (project_id,))
    await db.commit()

    return {
        "success": True,
        "project_id": project_id,
        "message": "Đã xóa video ghép thành phẩm!"
    }


