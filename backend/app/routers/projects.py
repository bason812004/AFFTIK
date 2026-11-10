import os
import uuid
import shutil
import zipfile
import asyncio
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, Query
from fastapi.responses import FileResponse
from backend.app.database import get_db
from backend.app.models import ProjectCreate, ProjectUpdate
from backend.app.config import PROJECTS_DIR, DATA_DIR
from backend.app.services.ffmpeg_service import ffmpeg_service
from backend.app.services.pipeline_runner import pipeline_runner
from backend.app.services.prompt_templates import render_prompt, DEFAULT_SYSTEM_PROMPTS

router = APIRouter(prefix="/api/projects", tags=["Projects"])

def create_project_folders(project_id: str):
    base = PROJECTS_DIR / project_id
    for folder in ["product", "character", "scripts", "prompts", "videos", "exports", "history"]:
        (base / folder).mkdir(parents=True, exist_ok=True)
    return base

@router.get("")
async def list_projects(db = Depends(get_db)):
    cursor = await db.execute("SELECT * FROM projects ORDER BY updated_at DESC")
    rows = await cursor.fetchall()
    batch = pipeline_runner.get_batch_state()
    running_pid = pipeline_runner.current_running_project_id
    queue_ids = batch.get("project_ids") or []
    done_ids = set(batch.get("completed_ids") or [])
    paused_ids = set(batch.get("paused_ids") or [])
    force_regen_ids = set(batch.get("force_regenerate_ids") or [])
    global_paused = bool(batch.get("paused_by_user"))
    pending_list = [pid for pid in queue_ids if pid not in done_ids and pid not in paused_ids]

    projects = []
    for r in rows:
        p = dict(r)
        pid = p["id"]

        # Verify file existence on disk for original_image_path and primary_character_image_path
        if p.get("original_image_path") and not os.path.exists(p["original_image_path"]):
            prod_cands = list((PROJECTS_DIR / pid / "product").glob("*"))
            if prod_cands and os.path.exists(str(prod_cands[0])):
                p["original_image_path"] = str(prod_cands[0])
            else:
                p["original_image_path"] = None

        if p.get("primary_character_image_path") and not os.path.exists(p["primary_character_image_path"]):
            char_cands = list((PROJECTS_DIR / pid / "character").glob("*"))
            if char_cands and os.path.exists(str(char_cands[0])):
                p["primary_character_image_path"] = str(char_cands[0])
            else:
                p["primary_character_image_path"] = None

        # Fetch counts (only counting files that actually exist on disk)
        c_cursor = await db.execute("SELECT file_path FROM assets WHERE project_id = ? AND asset_type = 'ai_character'", (pid,))
        c_rows = await c_cursor.fetchall()
        c_count = sum(1 for cr in c_rows if cr["file_path"] and os.path.exists(cr["file_path"]))

        v_cursor = await db.execute("SELECT video_path FROM videos WHERE project_id = ?", (pid,))
        v_rows = await v_cursor.fetchall()
        v_count = sum(1 for vr in v_rows if vr["video_path"] and os.path.exists(vr["video_path"]))

        e_cursor = await db.execute("SELECT * FROM exports WHERE project_id = ? ORDER BY created_at DESC LIMIT 1", (pid,))
        e_row = await e_cursor.fetchone()
        raw_has_export = bool(
            e_row and e_row["final_video_path"]
            and os.path.exists(e_row["final_video_path"])
            and os.path.getsize(e_row["final_video_path"]) > 1000
        )

        t_cursor = await db.execute("""
            SELECT status, step_name, progress_percent, message
            FROM automation_tasks
            WHERE project_id = ? AND task_type = 'full_pipeline'
            ORDER BY updated_at DESC, rowid DESC LIMIT 1
        """, (pid,))
        t_row = await t_cursor.fetchone()

        is_running_now = (pid == running_pid) and not global_paused and (pid not in paused_ids)
        is_requeued_from_start = (pid in force_regen_ids) and (pid not in done_ids)
        has_valid_export = raw_has_export and not is_running_now and not is_requeued_from_start and v_count >= 2

        in_queue = (pid in pending_list) and not global_paused and (pid not in paused_ids) and not has_valid_export and not is_running_now
        is_paused = (
            (pid in paused_ids)
            or (global_paused and not has_valid_export)
            or (not has_valid_export and not is_running_now and not in_queue)
        )
        queue_pos = (pending_list.index(pid) + 1) if pid in pending_list else None

        if is_running_now or in_queue:
            section_group = "running"
        elif has_valid_export:
            section_group = "completed"
        else:
            section_group = "paused"

        p["character_count"] = c_count
        p["video_count"] = v_count
        p["has_export"] = has_valid_export
        p["final_video_path"] = e_row["final_video_path"] if has_valid_export else None
        p["is_running_now"] = is_running_now
        p["is_paused"] = is_paused
        p["in_queue"] = in_queue
        p["queue_position"] = queue_pos
        p["section_group"] = section_group
        p["task_status"] = t_row["status"] if t_row else ("completed" if has_valid_export else ("paused" if is_paused else "idle"))
        p["step_name"] = t_row["step_name"] if t_row else ("Hoàn thành" if has_valid_export else ("Đã tạm dừng" if is_paused else "Sẵn sàng"))
        p["progress_percent"] = t_row["progress_percent"] if t_row else (100 if has_valid_export else 0)
        p["task_message"] = t_row["message"] if t_row else ""
        projects.append(p)
    return projects

@router.post("")
async def create_project(data: ProjectCreate, db = Depends(get_db)):
    project_id = str(uuid.uuid4())[:8]
    create_project_folders(project_id)
    project_name = (data.name or "").strip()
    if not project_name:
        project_name = f"Sản phẩm mới {project_id}"

    category = data.category or "Thương mại & Bán lẻ"
    description = data.description or f"Sản phẩm {project_name} cao cấp"
    benefits = data.benefits or f"Công dụng vượt trội của {project_name}, mang lại hiệu quả cao và tiện ích tối đa khi sử dụng."
    highlights = data.highlights or "Chất lượng cao cấp, thiết kế hiện đại, an toàn tuyệt đối."
    price = data.price or "Ưu đãi giá tốt"
    offer = data.offer or "Tặng kèm ưu đãi trợ giá và miễn phí giao hàng hôm nay"
    
    await db.execute("""
        INSERT INTO projects (
            id, name, category, description, benefits, highlights, materials,
            target_customer, usage_guide, price, offer, warranty, notes,
            tiktok_url, automation_mode, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'created', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """, (
        project_id, project_name, category, description, benefits,
        highlights, data.materials, data.target_customer or "Khách hàng mua sắm thông minh", data.usage_guide,
        price, offer, data.warranty, data.notes, data.tiktok_url,
        data.automation_mode or "auto"
    ))
    await db.commit()
    
    cursor = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    row = await cursor.fetchone()
    return dict(row)

@router.get("/clipboard-image-blob")
async def get_clipboard_image_blob():
    """
    Reads an image bitmap or copied image file directly from the Windows OS Clipboard
    and returns it as an image file response so the frontend can turn it into a File/Blob.
    """
    import subprocess
    temp_dir = DATA_DIR / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_file = temp_dir / f"clip_{uuid.uuid4().hex[:8]}.png"
    safe_dest = str(temp_file.resolve()).replace("'", "''")

    ps_cmd = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "Add-Type -AssemblyName System.Drawing; "
        "$img = [System.Windows.Forms.Clipboard]::GetImage(); "
        "if ($img -ne $null) { "
        f"  $img.Save('{safe_dest}', [System.Drawing.Imaging.ImageFormat]::Png); "
        "  $img.Dispose(); "
        "  Write-Output 'SAVED_BITMAP'; "
        "} else { "
        "  $files = [System.Windows.Forms.Clipboard]::GetFileDropList(); "
        "  if ($files -and $files.Count -gt 0) { Write-Output $files[0] } "
        "}"
    )
    res_ps = await asyncio.to_thread(
        subprocess.run,
        ["powershell", "-Sta", "-NoProfile", "-Command", ps_cmd],
        capture_output=True,
        text=True,
        timeout=10
    )
    out = (res_ps.stdout or "").strip()

    if out != "SAVED_BITMAP":
        clip_file = out.strip('"').strip("'")
        if clip_file and os.path.isfile(clip_file) and clip_file.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")):
            shutil.copyfile(clip_file, str(temp_file))
        else:
            raise HTTPException(
                status_code=400,
                detail="Không tìm thấy hình ảnh trong Clipboard! Hãy bấm Copy ảnh (Ctrl+C hoặc chụp màn hình Win+Shift+S) rồi bấm Dán Ảnh."
            )

    if not temp_file.exists() or temp_file.stat().st_size < 100:
        raise HTTPException(status_code=400, detail="Không tìm thấy dữ liệu ảnh hợp lệ trong Clipboard.")

    return FileResponse(
        path=str(temp_file),
        filename="san_pham_clipboard.png",
        media_type="image/png"
    )

async def _create_single_product_project(
    db,
    file_bytes: bytes,
    orig_filename: str,
    hint_name: str = "",
    auto_run: bool = True,
    trigger_pipeline_immediately: bool = True
) -> dict:
    project_id = str(uuid.uuid4())[:8]
    create_project_folders(project_id)

    ext = Path(orig_filename or "").suffix.lower() or ".jpg"
    if ext not in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]:
        ext = ".jpg"
    filename = f"product_original{ext}"
    dest_path = PROJECTS_DIR / project_id / "product" / filename

    with open(dest_path, "wb") as f:
        f.write(file_bytes)

    abs_path = str(dest_path)

    from backend.app.services.product_analyzer import analyze_product_image_hybrid, is_valid_recognized_product_name
    analyzed_data = {}
    needs_product_name = False
    clean_hint = (hint_name or "").strip()

    try:
        a_res = await analyze_product_image_hybrid(
            abs_path,
            hint_name=clean_hint,
            allow_gemini_vision=False,
            orig_filename=orig_filename
        )
        if a_res.get("data"):
            analyzed_data = a_res["data"]
    except Exception:
        pass

    if is_valid_recognized_product_name(clean_hint):
        clean_name = clean_hint
        needs_product_name = False
    elif is_valid_recognized_product_name(analyzed_data.get("product_name", "")):
        clean_name = analyzed_data["product_name"]
        needs_product_name = False
    else:
        needs_product_name = False
        clean_name = "Đang nhận diện sản phẩm..."

    category = analyzed_data.get("category") or "Thương mại & Bán lẻ"
    description = f"Sản phẩm {clean_name}"
    benefits = analyzed_data.get("benefits") or ""
    highlights = analyzed_data.get("highlights") or ""
    price = "Ưu đãi giá tốt"
    offer = "Tặng kèm ưu đãi trợ giá và miễn phí giao hàng hôm nay"

    # Compose 1 studio character preview image (9:16) introducing the uploaded product
    # Never copy raw product image into character box!
    char_dest = PROJECTS_DIR / project_id / "character" / "character_instant_preview.png"
    char_abs = ""
    try:
        from backend.app.services.character_composer import compose_studio_character_with_product
        await asyncio.to_thread(compose_studio_character_with_product, abs_path, str(char_dest))
        if char_dest.exists():
            char_abs = str(char_dest)
    except Exception:
        char_abs = ""

    init_status = "character_created"

    await db.execute("""
        INSERT INTO projects (
            id, name, category, description, benefits, highlights, price, offer,
            original_image_path, primary_character_image_path, status, automation_mode, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """, (
        project_id, clean_name, category, description, benefits, highlights, price, offer,
        abs_path, char_abs, init_status, "auto"
    ))

    asset_id = str(uuid.uuid4())[:8]
    await db.execute("""
        INSERT INTO assets (id, project_id, asset_type, file_path, file_name, file_size, is_primary)
        VALUES (?, ?, 'original_product', ?, ?, ?, 1)
    """, (asset_id, project_id, abs_path, filename, len(file_bytes)))

    await db.execute("DELETE FROM assets WHERE project_id = ? AND asset_type = 'ai_character'", (project_id,))
    if char_abs and os.path.exists(char_abs):
        char_asset_id = str(uuid.uuid4())[:8]
        char_size = os.path.getsize(char_abs)
        await db.execute("""
            INSERT INTO assets (id, project_id, asset_type, file_path, file_name, file_size, is_primary)
            VALUES (?, ?, 'ai_character', ?, 'character_instant_preview.png', ?, 1)
        """, (char_asset_id, project_id, char_abs, char_size))

    if is_valid_recognized_product_name(clean_name):
        from backend.app.services.pipeline_runner import build_fallback_scripts
        init_scripts = build_fallback_scripts(
            product_name=clean_name,
            category=category,
            benefits=benefits,
            highlights=highlights,
            offer=offer,
            price=price,
            custom_scene1_dialogue=analyzed_data.get("scene1_dialogue", ""),
            custom_scene2_dialogue=analyzed_data.get("scene2_dialogue", "")
        )
        for s in init_scripts:
            s_id = str(uuid.uuid4())[:8]
            await db.execute("""
                INSERT INTO scripts (
                    id, project_id, option_label, option_title, hook_concept,
                    scene1_dialogue, scene1_word_count, scene1_prompt_veo,
                    scene2_dialogue, scene2_word_count, scene2_prompt_veo,
                    is_selected, raw_response
                ) VALUES (?, ?, 'A', ?, ?, ?, ?, ?, ?, ?, ?, 1, 'Initial product script')
            """, (
                s_id, project_id, s["title"], s["hook"],
                s["scene1_dialogue"], s["scene1_words"], s["scene1_prompt_veo"],
                s["scene2_dialogue"], s["scene2_words"], s["scene2_prompt_veo"]
            ))
            await db.execute("UPDATE projects SET selected_script_id = ? WHERE id = ?", (s_id, project_id))

    await db.commit()

    task_id = str(uuid.uuid4())[:8]
    if trigger_pipeline_immediately:
        pipeline_runner.enqueue_batch([project_id], auto_run=True, force_regenerate=True)

    return {
        "success": True,
        "project_id": project_id,
        "task_id": task_id,
        "status": "running",
        "needs_product_name": False,
        "name": clean_name
    }


@router.post("/quick-create")
async def quick_create_project(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    auto_run: bool = Form(True),
    db = Depends(get_db)
):
    content = file.file.read()
    return await _create_single_product_project(
        db=db,
        file_bytes=content,
        orig_filename=file.filename or "product.jpg",
        hint_name=(name or "").strip(),
        auto_run=auto_run,
        trigger_pipeline_immediately=True
    )


@router.post("/batch-create")
async def batch_create_projects(
    files: List[UploadFile] = File(...),
    names_json: Optional[str] = Form(None),
    auto_run: bool = Form(True),
    db = Depends(get_db)
):
    """
    Batch creation for multiple product images at once!
    Each uploaded product image creates 1 project = 1 complete 20s video (Scene 1 10s + Scene 2 10s).
    """
    import json
    if not files:
        raise HTTPException(status_code=400, detail="Vui lòng chọn ít nhất 1 ảnh sản phẩm.")

    hint_names: List[str] = []
    if names_json:
        try:
            parsed = json.loads(names_json)
            if isinstance(parsed, list):
                hint_names = [str(x or "").strip() for x in parsed]
        except Exception:
            pass

    created_projects = []
    created_ids = []

    for idx, uf in enumerate(files):
        content = uf.file.read()
        if not content:
            continue
        h_name = hint_names[idx] if idx < len(hint_names) else ""
        res = await _create_single_product_project(
            db=db,
            file_bytes=content,
            orig_filename=uf.filename or f"product_{idx+1}.jpg",
            hint_name=h_name,
            auto_run=True,
            trigger_pipeline_immediately=False
        )
        created_projects.append(res)
        created_ids.append(res["project_id"])

    if created_ids:
        pipeline_runner.enqueue_batch(created_ids, auto_run=True, force_regenerate=True)

    return {
        "success": True,
        "count": len(created_projects),
        "projects": created_projects,
        "first_project_id": created_ids[0] if created_ids else None,
        "waiting_name_count": 0,
        "message": f"Đã thêm {len(created_projects)} dự án sản phẩm vào hàng đợi tự động (mỗi ảnh 1 video 20s)!"
    }


@router.get("/session-state")
async def get_session_and_batch_state(db = Depends(get_db)):
    """
    Returns any paused Google Flow session (waiting for account switch / login)
    and the active multi-product batch queue status with rich per-project progress.
    """
    paused = pipeline_runner.get_paused_session()
    batch = pipeline_runner.get_batch_state()
    running_pid = pipeline_runner.current_running_project_id

    batch_projects = []
    for pid in (batch.get("project_ids") or []):
        cur = await db.execute("""
            SELECT id, name, category, status, original_image_path, primary_character_image_path
            FROM projects WHERE id = ?
        """, (pid,))
        r = await cur.fetchone()
        if r:
            p_item = dict(r)
            v_cur = await db.execute("SELECT COUNT(*) FROM videos WHERE project_id = ?", (pid,))
            p_item["video_count"] = (await v_cur.fetchone())[0]
            e_cur = await db.execute("SELECT COUNT(*) FROM exports WHERE project_id = ?", (pid,))
            p_item["has_export"] = (await e_cur.fetchone())[0] > 0

            t_cur = await db.execute("""
                SELECT status, step_name, progress_percent, message
                FROM automation_tasks
                WHERE project_id = ?
                ORDER BY updated_at DESC, rowid DESC LIMIT 1
            """, (pid,))
            t_row = await t_cur.fetchone()
            if t_row:
                p_item["task_status"] = t_row["status"]
                p_item["step_name"] = t_row["step_name"]
                p_item["progress_percent"] = t_row["progress_percent"]
                p_item["task_message"] = t_row["message"]
            else:
                p_item["task_status"] = "completed" if p_item.get("status") == "completed" else "idle"
                p_item["step_name"] = "Hoàn thành" if p_item.get("status") == "completed" else "Sẵn sàng"
                p_item["progress_percent"] = 100 if p_item.get("status") == "completed" else 0
                p_item["task_message"] = ""
            batch_projects.append(p_item)

    paused_project_name = None
    if paused and paused.get("project_id"):
        cur = await db.execute("SELECT name FROM projects WHERE id = ?", (paused["project_id"],))
        r = await cur.fetchone()
        if r:
            paused_project_name = r["name"]

    return {
        "paused_session": paused,
        "paused_project_name": paused_project_name,
        "running_project_id": running_pid,
        "batch_state": batch,
        "batch_projects": batch_projects
    }


@router.post("/clear-batch-queue")
async def clear_batch_queue():
    """Clears completed batch items from the queue banner (keeps currently running/pending items if active)."""
    state = pipeline_runner.get_batch_state()
    if not state.get("active") and not pipeline_runner.is_running():
        pipeline_runner.clear_batch_state()
        return {"success": True, "cleared": True}
    all_ids = state.get("project_ids") or []
    done_ids = set(state.get("completed_ids") or [])
    remaining = [pid for pid in all_ids if pid not in done_ids or pid == pipeline_runner.current_running_project_id]
    if not remaining:
        pipeline_runner.clear_batch_state()
    else:
        state["project_ids"] = remaining
        state["completed_ids"] = []
        pipeline_runner.save_batch_state(state)
    return {"success": True, "cleared": True}


@router.post("/resume-session")
async def resume_saved_session(
    project_id: Optional[str] = Query(None),
):
    """
    Manually or automatically resumes the paused Google Flow session / batch queue
    after switching to a new Google account.
    """
    return await pipeline_runner.resume_paused_session(manual_project_id=project_id)


@router.post("/queue/pause")
async def pause_project_or_queue(
    project_id: Optional[str] = Query(None),
):
    """
    Pauses a specific project in the queue (if project_id is provided) or pauses the entire batch queue.
    """
    return pipeline_runner.pause_queue(project_id=project_id)


@router.post("/queue/resume")
async def resume_project_or_queue(
    project_id: Optional[str] = Query(None),
    all_incomplete: bool = Query(False),
):
    """
    Resumes/enqueues a specific project (if project_id is provided) or resumes the entire queue / all incomplete projects.
    """
    return pipeline_runner.resume_queue(project_id=project_id, all_incomplete=all_incomplete)


async def _reset_project_keep_product_only(project_id: str, db):
    """
    Deletes all generated character images, scene videos, and merged exported videos
    for a project (both on disk and in the database), keeping ONLY the original product image
    so the project can run cleanly from scratch (Step 1 -> Step 4).
    """
    cur = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án.")
    p = dict(row)
    orig_img = p.get("original_image_path") or ""

    # 1. Delete character assets on disk & DB (never delete original product image)
    a_cur = await db.execute(
        "SELECT file_path FROM assets WHERE project_id = ? AND asset_type != 'original_product'",
        (project_id,)
    )
    for ar in await a_cur.fetchall():
        fp = ar["file_path"]
        if fp and os.path.exists(fp) and os.path.abspath(fp) != os.path.abspath(orig_img) if orig_img else True:
            try:
                os.remove(fp)
            except Exception:
                pass
    char_dir = PROJECTS_DIR / project_id / "character"
    if char_dir.exists():
        for cf in char_dir.glob("*"):
            if orig_img and os.path.exists(orig_img) and os.path.abspath(str(cf)) == os.path.abspath(orig_img):
                continue
            try:
                cf.unlink()
            except Exception:
                pass
    await db.execute("DELETE FROM assets WHERE project_id = ? AND asset_type != 'original_product'", (project_id,))

    # 2. Delete scene videos on disk & DB
    v_cur = await db.execute("SELECT video_path FROM videos WHERE project_id = ?", (project_id,))
    for vr in await v_cur.fetchall():
        vp = vr["video_path"]
        if vp and os.path.exists(vp):
            try:
                os.remove(vp)
            except Exception:
                pass
    vid_dir = PROJECTS_DIR / project_id / "videos"
    if vid_dir.exists():
        for vf in vid_dir.glob("*"):
            try:
                vf.unlink()
            except Exception:
                pass
    await db.execute("DELETE FROM videos WHERE project_id = ?", (project_id,))

    # 3. Delete merged/exported videos on disk & DB
    e_cur = await db.execute("SELECT final_video_path FROM exports WHERE project_id = ?", (project_id,))
    for er in await e_cur.fetchall():
        ep = er["final_video_path"]
        if ep and os.path.exists(ep):
            try:
                os.remove(ep)
            except Exception:
                pass
    exp_dir = PROJECTS_DIR / project_id / "exports"
    if exp_dir.exists():
        for ef in exp_dir.glob("*"):
            try:
                ef.unlink()
            except Exception:
                pass
    await db.execute("DELETE FROM exports WHERE project_id = ?", (project_id,))

    # 4. Regenerate tailored product-specific script & prompts from product name/benefits
    from backend.app.services.product_analyzer import generate_smart_product_profile_from_name, is_generic_benefits
    from backend.app.services.pipeline_runner import build_fallback_scripts

    pname = p.get("name") or "Sản phẩm chính hãng"
    prof = generate_smart_product_profile_from_name(pname, p.get("benefits") or "")
    p_cat = prof.get("category") or p.get("category") or "Thương mại & Bán lẻ"
    p_ben = prof.get("benefits") if is_generic_benefits(p.get("benefits") or "") else (p.get("benefits") or prof.get("benefits") or "")
    p_high = p.get("highlights") or prof.get("highlights") or ""
    p_price = p.get("price") or prof.get("price") or "Ưu đãi giá tốt"
    p_offer = p.get("offer") or prof.get("offer") or "Tặng kèm ưu đãi trợ giá và miễn phí ship hôm nay"

    opts = build_fallback_scripts(
        product_name=pname,
        category=p_cat,
        benefits=p_ben,
        highlights=p_high,
        offer=p_offer,
        price=p_price,
        custom_scene1_dialogue=prof.get("scene1_dialogue", ""),
        custom_scene2_dialogue=prof.get("scene2_dialogue", "")
    )
    opt = opts[0]
    await db.execute("DELETE FROM scripts WHERE project_id = ?", (project_id,))
    sid = str(uuid.uuid4())[:8]
    await db.execute("""
        INSERT INTO scripts (
            id, project_id, option_label, option_title, hook_concept,
            scene1_dialogue, scene1_word_count, scene1_prompt_veo,
            scene2_dialogue, scene2_word_count, scene2_prompt_veo,
            is_selected, raw_response
        ) VALUES (?, ?, 'A', ?, ?, ?, ?, ?, ?, ?, ?, 1, 'Reset & regenerated tailored script')
    """, (
        sid, project_id, opt["title"], opt["hook"],
        opt["scene1_dialogue"], opt["scene1_words"], opt["scene1_prompt_veo"],
        opt["scene2_dialogue"], opt["scene2_words"], opt["scene2_prompt_veo"]
    ))

    # 5. Reset project status & clear primary_character_image_path (keeping original_image_path intact)
    await db.execute("""
        UPDATE projects SET
            category = ?,
            benefits = ?,
            highlights = ?,
            primary_character_image_path = NULL,
            selected_script_id = ?,
            status = 'image_uploaded',
            automation_mode = 'auto',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (p_cat, p_ben, p_high, sid, project_id))

    # 6. Reset automation_tasks so progress starts fresh at 10%
    await db.execute("DELETE FROM automation_tasks WHERE project_id = ?", (project_id,))
    tid = str(uuid.uuid4())[:8]
    await db.execute("""
        INSERT INTO automation_tasks (id, project_id, task_type, status, step_name, progress_percent, message, updated_at)
        VALUES (?, ?, 'full_pipeline', 'running', 'Đang chờ tới lượt (Chạy lại từ đầu)', 10, 'Đã xóa ảnh nhân vật & video cũ (giữ nguyên ảnh sản phẩm gốc), đang xếp hàng chạy lại từ đầu!', CURRENT_TIMESTAMP)
    """, (tid, project_id))
    await db.commit()


@router.post("/{project_id}/enqueue")
async def enqueue_single_project(
    project_id: str,
    force_regenerate: bool = Query(False),
    prioritize: bool = Query(False),
    db = Depends(get_db)
):
    """
    Adds a project directly into the central automatic queue from the external project card.
    When force_regenerate=True (Chạy lại), deletes all generated character images and videos
    except the original product image so the project runs completely from scratch.
    """
    cur = await db.execute("SELECT id FROM projects WHERE id = ?", (project_id,))
    if not await cur.fetchone():
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án.")

    if force_regenerate:
        await _reset_project_keep_product_only(project_id, db)
    else:
        await db.execute("UPDATE projects SET automation_mode = 'auto', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (project_id,))
        await db.commit()

    state = pipeline_runner.enqueue_batch([project_id], auto_run=True, force_regenerate=force_regenerate, prioritize=prioritize)
    return {
        "success": True,
        "project_id": project_id,
        "reset_from_scratch": force_regenerate,
        "batch_state": state,
        "message": (
            "Đã xóa ảnh nhân vật & video cũ (giữ nguyên ảnh sản phẩm) và đưa vào hàng đợi chạy lại từ đầu!"
            if force_regenerate
            else "Đã thêm dự án vào hàng đợi tự động! Hệ thống sẽ tự động làm tiếp cho tới khi xuất video."
        )
    }


@router.post("/{project_id}/confirm-product-name")
async def confirm_product_name(
    project_id: str,
    product_name: str = Form(None),
    auto_run: bool = Form(True),
    db = Depends(get_db)
):
    """
    When an uploaded product image did not have recognizable text, the user submits
    the exact product name here. Generates accurate, non-rambling prompts & 42-word scripts,
    and automatically continues the pipeline!
    """
    clean_name = (product_name or "").strip()
    if len(clean_name) < 2:
        raise HTTPException(status_code=400, detail="Vui lòng nhập tên sản phẩm hợp lệ (tối thiểu 2 ký tự).")

    cur = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án.")

    from backend.app.services.product_analyzer import generate_smart_product_profile_from_name
    from backend.app.services.pipeline_runner import build_fallback_scripts

    profile = generate_smart_product_profile_from_name(clean_name)
    p_cat = profile.get("category") or "Thương mại & Bán lẻ"
    p_ben = profile.get("benefits") or ""
    p_high = profile.get("highlights") or ""
    p_price = row["price"] or "Ưu đãi giá tốt"
    p_offer = row["offer"] or "Tặng kèm ưu đãi trợ giá và miễn phí giao hàng hôm nay"

    await db.execute("""
        UPDATE projects SET
            name = ?, category = ?, benefits = ?, highlights = ?,
            status = 'character_created', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (clean_name, p_cat, p_ben, p_high, project_id))

    scripts = build_fallback_scripts(
        product_name=clean_name,
        category=p_cat,
        benefits=p_ben,
        highlights=p_high,
        offer=p_offer,
        price=p_price,
        custom_scene1_dialogue=profile.get("scene1_dialogue", ""),
        custom_scene2_dialogue=profile.get("scene2_dialogue", "")
    )
    await db.execute("DELETE FROM scripts WHERE project_id = ?", (project_id,))
    s = scripts[0]
    s_id = str(uuid.uuid4())[:8]
    await db.execute("""
        INSERT INTO scripts (
            id, project_id, option_label, option_title, hook_concept,
            scene1_dialogue, scene1_word_count, scene1_prompt_veo,
            scene2_dialogue, scene2_word_count, scene2_prompt_veo,
            is_selected, raw_response
        ) VALUES (?, ?, 'A', ?, ?, ?, ?, ?, ?, ?, ?, 1, 'Confirmed product name script')
    """, (
        s_id, project_id, s["title"], s["hook"],
        s["scene1_dialogue"], s["scene1_words"], s["scene1_prompt_veo"],
        s["scene2_dialogue"], s["scene2_words"], s["scene2_prompt_veo"]
    ))
    await db.execute("UPDATE projects SET selected_script_id = ? WHERE id = ?", (s_id, project_id))
    await db.commit()

    # Always enqueue and run through to final 20s video!
    pipeline_runner.enqueue_batch([project_id], auto_run=True, force_regenerate=False, prioritize=True)

    return {
        "success": True,
        "project_id": project_id,
        "name": clean_name,
        "category": p_cat,
        "script": s,
        "message": f"Đã cập nhật tên sản phẩm '{clean_name}', đưa vào hàng đợi và tiếp tục chạy tự động tới khi ra video!"
    }


@router.post("/quick-create-from-clipboard")
async def quick_create_from_clipboard(
    auto_run: bool = Query(True),
    name: Optional[str] = Query(None),
    db = Depends(get_db)
):
    import subprocess
    temp_dir = DATA_DIR / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"clip_new_{uuid.uuid4().hex[:8]}.png"
    safe_dest = str(temp_path.resolve()).replace("'", "''")

    ps_cmd = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "Add-Type -AssemblyName System.Drawing; "
        "$img = [System.Windows.Forms.Clipboard]::GetImage(); "
        "if ($img -ne $null) { "
        f"  $img.Save('{safe_dest}', [System.Drawing.Imaging.ImageFormat]::Png); "
        "  $img.Dispose(); "
        "  Write-Output 'SAVED_BITMAP'; "
        "} else { "
        "  $files = [System.Windows.Forms.Clipboard]::GetFileDropList(); "
        "  if ($files -and $files.Count -gt 0) { Write-Output $files[0] } "
        "}"
    )
    res_ps = await asyncio.to_thread(
        subprocess.run,
        ["powershell", "-Sta", "-NoProfile", "-Command", ps_cmd],
        capture_output=True,
        text=True,
        timeout=10
    )
    out = (res_ps.stdout or "").strip()

    if out != "SAVED_BITMAP":
        clip_file = out.strip('"').strip("'")
        if clip_file and os.path.isfile(clip_file) and clip_file.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")):
            shutil.copyfile(clip_file, str(temp_path))
        else:
            raise HTTPException(
                status_code=400,
                detail="Không tìm thấy hình ảnh trong Clipboard! Hãy bấm Copy ảnh (Ctrl+C hoặc chụp màn hình Win+Shift+S) rồi bấm Dán Ảnh Tạo Dự Án Mới."
            )

    if not temp_path.exists() or temp_path.stat().st_size < 100:
        raise HTTPException(status_code=400, detail="Không tìm thấy dữ liệu ảnh hợp lệ trong Clipboard.")

    with open(temp_path, "rb") as f:
        file_bytes = f.read()
    try:
        temp_path.unlink()
    except Exception:
        pass

    return await _create_single_product_project(
        db=db,
        file_bytes=file_bytes,
        orig_filename="product_clipboard.png",
        hint_name=(name or "").strip(),
        auto_run=auto_run,
        trigger_pipeline_immediately=True
    )

@router.post("/ensure-manual")
async def ensure_manual_project(db = Depends(get_db)):
    """
    Ensures there is always at least one valid project for the Manual Studio page
    so the page never renders blank even if all previous projects were deleted.
    """
    cursor = await db.execute("SELECT * FROM projects ORDER BY updated_at DESC LIMIT 1")
    row = await cursor.fetchone()
    if row:
        return await get_project(row["id"], db)

    project_id = "manual01"
    create_project_folders(project_id)
    p_name = "Cặp da nam công sở cao cấp LECOS"
    p_cat = "Thời trang & Phụ kiện công sở"
    p_benefits = "Chất liệu da thật cao cấp chống thấm nước, chống bong tróc, form đứng sang trọng, ngăn đựng laptop 14 inch và tài liệu A4 cực kỳ tiện lợi"
    p_highlights = "Da bò cao cấp mềm mịn, khóa kéo kim loại chống gỉ, đường may tỉ mỉ, có dây đeo chéo tháo rời"
    p_price = "Ưu đãi giá tốt hôm nay"
    p_offer = "Tặng kèm ưu đãi trợ giá và miễn phí giao hàng toàn quốc hôm nay"

    assets_dir = Path(__file__).resolve().parent.parent / "assets"
    prod_ref = assets_dir / "lecos_product_ref.jpg"
    char_ref = assets_dir / "lecos_character_ref.png"
    prod_dest = PROJECTS_DIR / project_id / "product" / "product_original.jpg"
    char_dest = PROJECTS_DIR / project_id / "character" / "character_primary.png"
    orig_path_str = None
    char_path_str = None
    if prod_ref.exists():
        shutil.copyfile(str(prod_ref), str(prod_dest))
        orig_path_str = str(prod_dest)
    if char_ref.exists():
        shutil.copyfile(str(char_ref), str(char_dest))
        char_path_str = str(char_dest)

    await db.execute("""
        INSERT INTO projects (
            id, name, category, description, benefits, highlights, price, offer,
            original_image_path, primary_character_image_path,
            status, automation_mode, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'character_created', 'manual', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """, (project_id, p_name, p_cat, p_name, p_benefits, p_highlights, p_price, p_offer, orig_path_str, char_path_str))

    from backend.app.services.pipeline_runner import build_fallback_scripts
    init_scripts = build_fallback_scripts(
        product_name=p_name,
        category=p_cat,
        benefits=p_benefits,
        highlights=p_highlights,
        offer=p_offer,
        price=p_price
    )
    for s in init_scripts:
        s_id = str(uuid.uuid4())[:8]
        await db.execute("""
            INSERT INTO scripts (
                id, project_id, option_label, option_title, hook_concept,
                scene1_dialogue, scene1_word_count, scene1_prompt_veo,
                scene2_dialogue, scene2_word_count, scene2_prompt_veo,
                is_selected, raw_response
            ) VALUES (?, ?, 'A', ?, ?, ?, ?, ?, ?, ?, ?, 1, 'Manual ready script')
        """, (
            s_id, project_id, s["title"], s["hook"],
            s["scene1_dialogue"], s["scene1_words"], s["scene1_prompt_veo"],
            s["scene2_dialogue"], s["scene2_words"], s["scene2_prompt_veo"]
        ))
        await db.execute("UPDATE projects SET selected_script_id = ? WHERE id = ?", (s_id, project_id))

    await db.commit()
    return await get_project(project_id, db)

@router.get("/{project_id}")
async def get_project(project_id: str, db = Depends(get_db)):
    cursor = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")
    
    project = dict(row)
    
    # Get assets (only return assets whose file exists on disk)
    a_cursor = await db.execute("SELECT * FROM assets WHERE project_id = ? ORDER BY created_at DESC", (project_id,))
    raw_assets = [dict(a) for a in await a_cursor.fetchall()]
    assets = [a for a in raw_assets if a.get("file_path") and os.path.exists(a["file_path"])]
    project["assets"] = assets
    project["character_images"] = [a for a in assets if a["asset_type"] == "ai_character"]

    if project.get("original_image_path") and not os.path.exists(project["original_image_path"]):
        project["original_image_path"] = None
    if project.get("primary_character_image_path") and not os.path.exists(project["primary_character_image_path"]):
        project["primary_character_image_path"] = None
    
    # Get scripts
    s_cursor = await db.execute("SELECT * FROM scripts WHERE project_id = ? ORDER BY option_label ASC", (project_id,))
    scripts = [dict(s) for s in await s_cursor.fetchall()]
    project["scripts"] = scripts
    
    # Get videos (only return videos whose file actually exists on disk)
    v_cursor = await db.execute("SELECT * FROM videos WHERE project_id = ? ORDER BY scene_number ASC", (project_id,))
    raw_videos = [dict(v) for v in await v_cursor.fetchall()]
    import hashlib
    videos = []
    for v in raw_videos:
        p = v.get("video_path")
        if p and os.path.exists(p) and os.path.getsize(p) > 1000:
            v["file_size"] = os.path.getsize(p)
            try:
                h = hashlib.md5()
                with open(p, "rb") as fp:
                    h.update(fp.read(65536))
                v["file_hash"] = h.hexdigest()
            except Exception:
                v["file_hash"] = ""
            videos.append(v)
    project["videos"] = videos
    
    # STRICT CHECK: Export is ONLY valid if BOTH Scene 1 and Scene 2 genuinely exist (>10KB)!
    has_scene1 = any(v.get("scene_number") == 1 and v.get("file_size", 0) > 10000 for v in project.get("videos", []))
    has_scene2 = any(v.get("scene_number") == 2 and v.get("file_size", 0) > 10000 for v in project.get("videos", []))
    has_both_scenes = has_scene1 and has_scene2

    # Get export (only if both scenes exist and export file exists on disk)
    e_cursor = await db.execute("SELECT * FROM exports WHERE project_id = ? ORDER BY created_at DESC LIMIT 1", (project_id,))
    e_row = await e_cursor.fetchone()
    if e_row:
        exp_dict = dict(e_row)
        exp_path = exp_dict.get("final_video_path") or exp_dict.get("file_path")
        if exp_path and os.path.exists(exp_path) and os.path.getsize(exp_path) > 1000 and has_both_scenes:
            project["export"] = exp_dict
        else:
            # Purge invalid orphan export record where Scene 2 was missing
            if not has_both_scenes:
                if exp_path and os.path.exists(exp_path):
                    try:
                        os.unlink(exp_path)
                    except Exception:
                        pass
                await db.execute("DELETE FROM exports WHERE project_id = ?", (project_id,))
                if project.get("status") == "completed":
                    new_st = "video1_ready" if has_scene1 else "scripts_created"
                    await db.execute("UPDATE projects SET status = ? WHERE id = ?", (new_st, project_id))
                await db.commit()
            project["export"] = None
    else:
        project["export"] = None
    
    # Attach Female Model character generation prompt
    try:
        p_cur = await db.execute("SELECT content FROM prompts WHERE id = 'sys_prompt_char_gen' OR (category = 'character_gen' AND is_default = 1) LIMIT 1")
        p_tpl = await p_cur.fetchone()
        char_tpl = p_tpl["content"] if p_tpl else DEFAULT_SYSTEM_PROMPTS[0]["content"]
        project["character_prompt"] = render_prompt(char_tpl, {
            "product_name": project.get("name", "Sản phẩm thương mại"),
            "category": project.get("category", "Thương mại & Bán lẻ"),
            "description": project.get("description", ""),
            "benefits": project.get("benefits", "Công dụng tiện ích và hiệu quả vượt trội"),
            "highlights": project.get("highlights", "Thiết kế chính hãng, chi tiết sắc nét"),
            "target_customer": project.get("target_customer", "Khách hàng tiêu dùng thông thái")
        })
    except Exception:
        project["character_prompt"] = DEFAULT_SYSTEM_PROMPTS[0]["content"]

    return project

@router.put("/{project_id}")
async def update_project(project_id: str, data: ProjectUpdate, db = Depends(get_db)):
    fields = []
    values = []
    for k, v in data.model_dump(exclude_unset=True).items():
        fields.append(f"{k} = ?")
        values.append(v)
    
    if not fields:
        return {"message": "Không có thay đổi"}
        
    values.append(project_id)
    query = f"UPDATE projects SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
    await db.execute(query, values)
    await db.commit()
    
    cursor = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    return dict(await cursor.fetchone())

@router.delete("/{project_id}")
async def delete_project(project_id: str, db = Depends(get_db)):
    await db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    await db.commit()
    
    p_dir = PROJECTS_DIR / project_id
    if p_dir.exists():
        shutil.rmtree(p_dir, ignore_errors=True)
        
    return {"success": True, "message": "Đã xóa dự án thành công"}

@router.post("/{project_id}/upload-product-image")
async def upload_product_image(project_id: str, file: UploadFile = File(...), db = Depends(get_db)):
    create_project_folders(project_id)
    ext = Path(file.filename or "").suffix.lower() or ".jpg"
    filename = f"product_original{ext}"
    dest_path = PROJECTS_DIR / project_id / "product" / filename
    
    content = file.file.read()
    with open(dest_path, "wb") as f:
        f.write(content)
        
    rel_path = f"/data/projects/{project_id}/product/{filename}"
    abs_path = str(dest_path)

    # Clear old videos & exports when replacing product image so stale videos never leak
    v_dir = PROJECTS_DIR / project_id / "videos"
    if v_dir.exists():
        for vf in v_dir.glob("*.mp4"):
            try:
                vf.unlink()
            except Exception:
                pass
    await db.execute("DELETE FROM videos WHERE project_id = ?", (project_id,))
    await db.execute("DELETE FROM exports WHERE project_id = ?", (project_id,))

    # Automatically compose 9:16 AI Character standing with the new product as instant preview
    # Never copy raw product image into character box!
    char_dest = PROJECTS_DIR / project_id / "character" / "character_instant_preview.png"
    char_abs = ""
    try:
        from backend.app.services.character_composer import compose_studio_character_with_product
        await asyncio.to_thread(compose_studio_character_with_product, abs_path, str(char_dest))
        if char_dest.exists():
            char_abs = str(char_dest)
    except Exception:
        char_abs = ""
    
    # Record assets
    asset_id = str(uuid.uuid4())[:8]
    await db.execute("""
        INSERT INTO assets (id, project_id, asset_type, file_path, file_name, file_size, is_primary)
        VALUES (?, ?, 'original_product', ?, ?, ?, 1)
    """, (asset_id, project_id, abs_path, filename, len(content)))

    await db.execute("DELETE FROM assets WHERE project_id = ? AND asset_type = 'ai_character'", (project_id,))
    if char_abs and os.path.exists(char_abs):
        char_asset_id = str(uuid.uuid4())[:8]
        char_size = os.path.getsize(char_abs)
        await db.execute("""
            INSERT INTO assets (id, project_id, asset_type, file_path, file_name, file_size, is_primary)
            VALUES (?, ?, 'ai_character', ?, 'character_instant_preview.png', ?, 1)
        """, (char_asset_id, project_id, char_abs, char_size))
    
    # Immediately analyze new product image via fast local OCR
    from backend.app.services.product_analyzer import analyze_product_image_hybrid, is_valid_recognized_product_name
    analyzed_data = {}
    needs_product_name = False
    try:
        a_res = await analyze_product_image_hybrid(abs_path, hint_name="", allow_gemini_vision=False)
        if a_res.get("needs_product_name"):
            needs_product_name = True
        if a_res.get("data"):
            analyzed_data = a_res["data"]
    except Exception:
        needs_product_name = True

    if not needs_product_name and is_valid_recognized_product_name(analyzed_data.get("product_name", "")):
        new_name = analyzed_data["product_name"]
    else:
        needs_product_name = True
        new_name = "⚠️ Cần nhập tên sản phẩm"

    new_cat = analyzed_data.get("category") or ("Chờ nhập tên sản phẩm" if needs_product_name else "Thương mại & Bán lẻ")
    new_ben = analyzed_data.get("benefits") or ""
    new_high = analyzed_data.get("highlights") or ""
    new_status = "needs_product_name" if needs_product_name else "character_created"

    await db.execute("""
        UPDATE projects SET
            name = ?,
            category = ?,
            benefits = ?,
            highlights = ?,
            original_image_path = ?,
            primary_character_image_path = ?,
            status = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (new_name, new_cat, new_ben, new_high, abs_path, char_abs, new_status, project_id))

    if not needs_product_name:
        from backend.app.services.pipeline_runner import build_fallback_scripts
        new_scripts = build_fallback_scripts(
            product_name=new_name,
            category=new_cat,
            benefits=new_ben,
            highlights=new_high,
            custom_scene1_dialogue=analyzed_data.get("scene1_dialogue", ""),
            custom_scene2_dialogue=analyzed_data.get("scene2_dialogue", "")
        )
        for s in new_scripts:
            s_id = str(uuid.uuid4())[:8]
            await db.execute("DELETE FROM scripts WHERE project_id = ?", (project_id,))
            await db.execute("""
                INSERT INTO scripts (
                    id, project_id, option_label, option_title, hook_concept,
                    scene1_dialogue, scene1_word_count, scene1_prompt_veo,
                    scene2_dialogue, scene2_word_count, scene2_prompt_veo,
                    is_selected, raw_response
                ) VALUES (?, ?, 'A', ?, ?, ?, ?, ?, ?, ?, ?, 1, 'Product tailored script')
            """, (
                s_id, project_id, s["title"], s["hook"],
                s["scene1_dialogue"], s["scene1_words"], s["scene1_prompt_veo"],
                s["scene2_dialogue"], s["scene2_words"], s["scene2_prompt_veo"]
            ))
            await db.execute("UPDATE projects SET selected_script_id = ? WHERE id = ?", (s_id, project_id))

    await db.commit()

    # Always enqueue into the central automatic queue so it runs through to the final 20s video!
    task_id = str(uuid.uuid4())[:8]
    pipeline_runner.enqueue_batch([project_id], auto_run=True, force_regenerate=True, prioritize=True)
    
    return {
        "success": True,
        "image_path": abs_path,
        "character_image_path": char_abs,
        "url": rel_path,
        "file_name": filename,
        "task_id": task_id
    }

@router.post("/{project_id}/manual-prepare")
async def manual_prepare_project(
    project_id: str,
    name: Optional[str] = Form(None),
    benefits: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db = Depends(get_db)
):
    """
    Dedicated Manual Branch 1-Click Preparation:
    - Updates product image (if uploaded), product name, and main benefits.
    - Composes 9:16 AI Character standing with the product.
    - Writes 1 script (2 scenes, 42 words/scene) focused on the product's benefits
      plus separate Video Creation Prompts for Scene 1 & Scene 2.
    """
    cursor = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")
    p = dict(row)
    create_project_folders(project_id)

    abs_path = p.get("original_image_path")
    char_abs = p.get("primary_character_image_path")

    if file and file.filename:
        ext = Path(file.filename).suffix.lower() or ".jpg"
        filename = f"product_original{ext}"
        dest_path = PROJECTS_DIR / project_id / "product" / filename
        content = file.file.read()
        with open(dest_path, "wb") as f:
            f.write(content)
        abs_path = str(dest_path)

        # Clear old videos & exports when new product image is supplied
        v_dir = PROJECTS_DIR / project_id / "videos"
        if v_dir.exists():
            for vf in v_dir.glob("*.mp4"):
                try:
                    vf.unlink()
                except Exception:
                    pass
        await db.execute("DELETE FROM videos WHERE project_id = ?", (project_id,))
        await db.execute("DELETE FROM exports WHERE project_id = ?", (project_id,))

    if abs_path and os.path.exists(abs_path):
        char_dest = PROJECTS_DIR / project_id / "character" / "character_primary.png"
        try:
            from backend.app.services.character_composer import compose_studio_character_with_product
            await asyncio.to_thread(compose_studio_character_with_product, abs_path, str(char_dest))
            char_abs = str(char_dest)
        except Exception:
            pass

    clean_name = (name or "").strip() or p.get("name") or "Sản phẩm chất lượng cao"
    raw_benefits = (benefits or "").strip() or p.get("benefits") or ""
    p_cat = p.get("category") or "Thương mại & Bán lẻ"
    p_high = p.get("highlights") or "Chính hãng cao cấp, thiết kế hiện đại, bền bỉ."
    s1_dlg = ""
    s2_dlg = ""

    # Always enrich from smart product profile if benefits are generic/empty or product name matches a rule
    try:
        from backend.app.services.product_analyzer import generate_smart_product_profile_from_name, is_generic_benefits
        matched = generate_smart_product_profile_from_name(clean_name, benefits_hint=raw_benefits)
        if matched:
            if is_generic_benefits(raw_benefits) or clean_name.lower() != (p.get("name") or "").strip().lower():
                raw_benefits = matched.get("benefits") or raw_benefits
            p_cat = matched.get("category") or p_cat
            p_high = matched.get("highlights") or p_high
            s1_dlg = matched.get("scene1_dialogue") or ""
            s2_dlg = matched.get("scene2_dialogue") or ""
    except Exception:
        pass

    clean_benefits = raw_benefits or f"giải quyết hiệu quả nhu cầu sử dụng hằng ngày với {clean_name}, bền bỉ và tiện lợi tối đa."

    await db.execute("""
        UPDATE projects SET
            name = ?,
            category = ?,
            benefits = ?,
            highlights = ?,
            original_image_path = COALESCE(?, original_image_path),
            primary_character_image_path = COALESCE(?, primary_character_image_path),
            status = 'scripts_created',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (clean_name, p_cat, clean_benefits, p_high, abs_path, char_abs, project_id))

    from backend.app.services.pipeline_runner import build_fallback_scripts
    new_scripts = build_fallback_scripts(
        product_name=clean_name,
        category=p_cat,
        benefits=clean_benefits,
        highlights=p_high,
        offer=p.get("offer") or "Tặng kèm ưu đãi trợ giá và miễn phí giao hàng hôm nay",
        price=p.get("price") or "Ưu đãi hôm nay",
        custom_scene1_dialogue=s1_dlg,
        custom_scene2_dialogue=s2_dlg
    )

    await db.execute("DELETE FROM scripts WHERE project_id = ?", (project_id,))
    for s in new_scripts:
        s_id = str(uuid.uuid4())[:8]
        await db.execute("""
            INSERT INTO scripts (
                id, project_id, option_label, option_title, hook_concept,
                scene1_dialogue, scene1_word_count, scene1_prompt_veo,
                scene2_dialogue, scene2_word_count, scene2_prompt_veo,
                is_selected, raw_response
            ) VALUES (?, ?, 'A', ?, ?, ?, ?, ?, ?, ?, ?, 1, 'Manual tailored script')
        """, (
            s_id, project_id, s["title"], s["hook"],
            s["scene1_dialogue"], s["scene1_words"], s["scene1_prompt_veo"],
            s["scene2_dialogue"], s["scene2_words"], s["scene2_prompt_veo"]
        ))
        await db.execute("UPDATE projects SET selected_script_id = ? WHERE id = ?", (s_id, project_id))

    await db.commit()
    return await get_project(project_id, db)

@router.post("/{project_id}/upload-character-image")
async def upload_character_image(project_id: str, file: UploadFile = File(...), db = Depends(get_db)):
    create_project_folders(project_id)
    ext = Path(file.filename or "").suffix.lower() or ".png"
    char_id = str(uuid.uuid4())[:6]
    filename = f"character_{char_id}{ext}"
    dest_path = PROJECTS_DIR / project_id / "character" / filename
    
    content = file.file.read()
    with open(dest_path, "wb") as f:
        f.write(content)
        
    abs_path = str(dest_path)
    rel_path = f"/data/projects/{project_id}/character/{filename}"
    
    asset_id = str(uuid.uuid4())[:8]
    await db.execute("DELETE FROM assets WHERE project_id = ? AND asset_type = 'ai_character'", (project_id,))
    await db.execute("""
        INSERT INTO assets (id, project_id, asset_type, file_path, file_name, file_size, is_primary)
        VALUES (?, ?, 'ai_character', ?, ?, ?, 1)
    """, (asset_id, project_id, abs_path, filename, len(content)))
    
    # Mark as primary character
    await db.execute("""
        UPDATE projects SET primary_character_image_path = ?, status = 'character_created', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (abs_path, project_id))
    await db.commit()
    
    return {
        "success": True,
        "image_path": abs_path,
        "url": rel_path,
        "file_name": filename
    }

@router.post("/{project_id}/set-primary-character")
async def set_primary_character(project_id: str, asset_id: str = Form(...), db = Depends(get_db)):
    cursor = await db.execute("SELECT * FROM assets WHERE id = ? AND project_id = ?", (asset_id, project_id))
    asset = await cursor.fetchone()
    if not asset:
        raise HTTPException(status_code=404, detail="Không tìm thấy ảnh")
        
    await db.execute("UPDATE assets SET is_primary = 0 WHERE project_id = ? AND asset_type = 'ai_character'", (project_id,))
    await db.execute("UPDATE assets SET is_primary = 1 WHERE id = ?", (asset_id,))
    await db.execute("UPDATE projects SET primary_character_image_path = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (asset["file_path"], project_id))
    await db.commit()
    
    return {"success": True, "primary_character_image_path": asset["file_path"]}

@router.post("/{project_id}/duplicate")
async def duplicate_project(project_id: str, db = Depends(get_db)):
    cursor = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    p = await cursor.fetchone()
    if not p:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")
        
    new_id = str(uuid.uuid4())[:8]
    new_name = f"{p['name']} (Bản sao)"
    create_project_folders(new_id)
    
    # Copy files if any
    src_dir = PROJECTS_DIR / project_id
    dst_dir = PROJECTS_DIR / new_id
    if src_dir.exists():
        shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
        
    await db.execute("""
        INSERT INTO projects (
            id, name, category, description, benefits, highlights, materials,
            target_customer, usage_guide, price, offer, warranty, notes,
            tiktok_url, automation_mode, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """, (
        new_id, new_name, p["category"], p["description"], p["benefits"],
        p["highlights"], p["materials"], p["target_customer"], p["usage_guide"],
        p["price"], p["offer"], p["warranty"], p["notes"], p["tiktok_url"],
        p["automation_mode"], p["status"]
    ))
    await db.commit()
    
    return {"success": True, "new_project_id": new_id}

@router.get("/{project_id}/export-zip")
async def export_project_zip(project_id: str, db = Depends(get_db)):
    cursor = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    p = await cursor.fetchone()
    if not p:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")
        
    src_dir = PROJECTS_DIR / project_id
    if not src_dir.exists():
        raise HTTPException(status_code=404, detail="Thư mục dự án rỗng")
        
    zip_filename = f"TikTokStudio_{project_id}_{p['name'].replace(' ', '_')}.zip"
    zip_dest = DATA_DIR / zip_filename
    
    # Zip project folder safely (excluding any browser session or auth data)
    with zipfile.ZipFile(zip_dest, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(src_dir):
            for file in files:
                full_path = Path(root) / file
                rel_path = full_path.relative_to(src_dir)
                zipf.write(full_path, arcname=str(rel_path))
                
    return FileResponse(
        path=str(zip_dest),
        filename=zip_filename,
        media_type="application/zip"
    )

@router.post("/{project_id}/run-full-auto")
async def run_project_full_auto(project_id: str, db = Depends(get_db)):
    """
    1-Click Full Automation Pipeline:
    From product image -> AI character -> 3 scripts -> Veo Scene 1 & 2 -> Final TikTok Video.
    """
    cursor = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    p = await cursor.fetchone()
    if not p:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")

    await db.execute("UPDATE projects SET automation_mode = 'auto', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (project_id,))
    await db.commit()

    task_id = str(uuid.uuid4())[:8]
    pipeline_runner.enqueue_batch([project_id], auto_run=True, force_regenerate=False, prioritize=True)

    return {
        "success": True,
        "task_id": task_id,
        "project_id": project_id,
        "message": "Đã đưa dự án vào hàng đợi tự động sản xuất video TikTok từ A đến Z!"
    }

@router.get("/{project_id}/pipeline-status")
async def get_project_pipeline_status(project_id: str, db = Depends(get_db)):
    cursor = await db.execute("""
        SELECT * FROM automation_tasks 
        WHERE project_id = ? AND task_type = 'full_pipeline'
        ORDER BY updated_at DESC LIMIT 1
    """, (project_id,))
    row = await cursor.fetchone()
    if not row:
        return {"has_task": False, "status": "idle", "progress_percent": 0, "message": "Chưa có tác vụ tự động"}
    
    t = dict(row)
    t["has_task"] = True
    return t

@router.get("/{project_id}/download-character")
async def download_character_image(project_id: str, db = Depends(get_db)):
    cursor = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    p = await cursor.fetchone()
    if not p:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")
    p_dict = dict(p)
    img_path = p_dict.get("primary_character_image_path")
    if not img_path or not os.path.exists(img_path):
        canonical = PROJECTS_DIR / project_id / "character" / "character_primary.png"
        if canonical.exists():
            img_path = str(canonical)
        elif p_dict.get("original_image_path") and os.path.exists(p_dict["original_image_path"]):
            img_path = p_dict["original_image_path"]
    if not img_path or not os.path.exists(img_path):
        raise HTTPException(status_code=404, detail="Chưa có ảnh nhân vật để tải về")
    ext = Path(img_path).suffix or ".png"
    return FileResponse(
        path=img_path,
        filename=f"nhan_vat_AI_{project_id}{ext}",
        media_type=f"image/{ext.lstrip('.').replace('jpg', 'jpeg')}"
    )

@router.get("/{project_id}/download-product")
async def download_product_image(project_id: str, db = Depends(get_db)):
    cursor = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    p = await cursor.fetchone()
    if not p:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")
    p_dict = dict(p)
    img_path = p_dict.get("original_image_path")
    if not img_path or not os.path.exists(img_path):
        canonical = PROJECTS_DIR / project_id / "product" / "product_original.jpg"
        if canonical.exists():
            img_path = str(canonical)
    if not img_path or not os.path.exists(img_path):
        raise HTTPException(status_code=404, detail="Chưa có ảnh sản phẩm để tải về")
    ext = Path(img_path).suffix or ".jpg"
    return FileResponse(
        path=img_path,
        filename=f"san_pham_goc_{project_id}{ext}",
        media_type=f"image/{ext.lstrip('.').replace('jpg', 'jpeg')}"
    )

@router.post("/{project_id}/copy-image-clipboard")
async def copy_image_to_clipboard(project_id: str, image_type: str = "character", db = Depends(get_db)):
    """
    Copies the character image (or product image) directly into the Windows OS Clipboard
    so the user can press Ctrl+V on any external video platform (Flow, Kling, Dreamina, Hailuo, CapCut, etc.).
    """
    cursor = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    p = await cursor.fetchone()
    if not p:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")
    p_dict = dict(p)
    if image_type == "product":
        img_path = p_dict.get("original_image_path")
    else:
        img_path = p_dict.get("primary_character_image_path") or p_dict.get("original_image_path")

    if not img_path or not os.path.exists(img_path):
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp ảnh để sao chép")

    import subprocess
    safe_path = os.path.abspath(img_path).replace("'", "''")
    ps_cmd = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "Add-Type -AssemblyName System.Drawing; "
        f"$img = [System.Drawing.Image]::FromFile('{safe_path}'); "
        "[System.Windows.Forms.Clipboard]::SetImage($img); "
        "$img.Dispose();"
    )
    try:
        await asyncio.to_thread(
            subprocess.run,
            ["powershell", "-Sta", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=10
        )
        return {"success": True, "message": "Đã sao chép ảnh vào Clipboard Windows! Bạn có thể bấm Ctrl+V trực tiếp trên nền tảng tạo video."}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.delete("/{project_id}/image/{image_type}")
async def delete_project_image(
    project_id: str,
    image_type: str,
    asset_id: Optional[str] = None,
    db = Depends(get_db)
):
    """
    Deletes the uploaded/pasted Product Image ('product') or AI Character Image ('character').
    Optionally deletes a specific character history variant when asset_id is provided.
    """
    cursor = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")
    p = dict(row)

    if asset_id:
        a_cursor = await db.execute("SELECT * FROM assets WHERE id = ? AND project_id = ?", (asset_id, project_id))
        a_row = await a_cursor.fetchone()
        if a_row:
            a_dict = dict(a_row)
            fp = a_dict.get("file_path")
            if fp and os.path.exists(fp) and fp != p.get("original_image_path"):
                try:
                    os.remove(fp)
                except Exception:
                    pass
            await db.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
            if p.get("primary_character_image_path") == fp:
                # Pick next available ai_character if any
                next_cur = await db.execute(
                    "SELECT * FROM assets WHERE project_id = ? AND asset_type = 'ai_character' ORDER BY created_at DESC LIMIT 1",
                    (project_id,)
                )
                next_row = await next_cur.fetchone()
                next_path = dict(next_row)["file_path"] if next_row else None
                await db.execute(
                    "UPDATE projects SET primary_character_image_path = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (next_path, project_id)
                )
        await db.commit()
        return {"success": True, "message": "Đã xóa ảnh nhân vật thành công!"}

    if image_type == "product":
        orig_path = p.get("original_image_path")
        if orig_path and os.path.exists(orig_path):
            try:
                os.remove(orig_path)
            except Exception:
                pass
        prod_dir = PROJECTS_DIR / project_id / "product"
        if prod_dir.exists():
            for pf in prod_dir.glob("*"):
                try:
                    pf.unlink()
                except Exception:
                    pass
        await db.execute("DELETE FROM assets WHERE project_id = ? AND asset_type = 'original_product'", (project_id,))
        await db.execute(
            "UPDATE projects SET original_image_path = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (project_id,)
        )
        await db.commit()
        return {"success": True, "message": "Đã xóa Ảnh Sản Phẩm!"}
    else:
        char_path = p.get("primary_character_image_path")
        if char_path and os.path.exists(char_path) and char_path != p.get("original_image_path"):
            try:
                os.remove(char_path)
            except Exception:
                pass
        if char_path:
            await db.execute(
                "DELETE FROM assets WHERE project_id = ? AND asset_type = 'ai_character' AND file_path = ?",
                (project_id, char_path)
            )
        # Check if another character variant exists; if user clicked main delete, clear primary_character_image_path
        await db.execute(
            "UPDATE projects SET primary_character_image_path = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (project_id,)
        )
        await db.commit()
        return {"success": True, "message": "Đã xóa Ảnh Nhân Vật AI!"}


@router.post("/{project_id}/paste-clipboard-image")
async def paste_clipboard_image(
    project_id: str,
    image_type: str = "product",
    db = Depends(get_db)
):
    """
    Reads an image bitmap or copied image file directly from the Windows Clipboard (Ctrl+C / Screenshot)
    and imports it as Product Image (auto-generating AI Character & Script) or Character Image.
    """
    import subprocess
    create_project_folders(project_id)

    uid = uuid.uuid4().hex[:6]
    if image_type == "product":
        dest_path = PROJECTS_DIR / project_id / "product" / f"product_pasted_{uid}.png"
    else:
        dest_path = PROJECTS_DIR / project_id / "character" / f"character_pasted_{uid}.png"

    safe_dest = str(dest_path.resolve()).replace("'", "''")
    ps_cmd = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "Add-Type -AssemblyName System.Drawing; "
        "$img = [System.Windows.Forms.Clipboard]::GetImage(); "
        "if ($img -ne $null) { "
        f"  $img.Save('{safe_dest}', [System.Drawing.Imaging.ImageFormat]::Png); "
        "  $img.Dispose(); "
        "  Write-Output 'SAVED_BITMAP'; "
        "} else { "
        "  $files = [System.Windows.Forms.Clipboard]::GetFileDropList(); "
        "  if ($files -and $files.Count -gt 0) { Write-Output $files[0] } "
        "}"
    )
    res_ps = await asyncio.to_thread(
        subprocess.run,
        ["powershell", "-Sta", "-NoProfile", "-Command", ps_cmd],
        capture_output=True,
        text=True,
        timeout=10
    )
    out = (res_ps.stdout or "").strip()

    if out != "SAVED_BITMAP":
        clip_file = out.strip('"').strip("'")
        if clip_file and os.path.isfile(clip_file) and clip_file.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")):
            shutil.copyfile(clip_file, str(dest_path))
        else:
            raise HTTPException(
                status_code=400,
                detail="Không tìm thấy hình ảnh trong Clipboard! Hãy bấm Copy ảnh (Ctrl+C hoặc chụp màn hình Win+Shift+S) rồi bấm Dán Ảnh."
            )

    if not dest_path.exists() or dest_path.stat().st_size < 100:
        raise HTTPException(status_code=400, detail="Không thể đọc dữ liệu ảnh từ Clipboard.")

    abs_path = str(dest_path)
    file_size = dest_path.stat().st_size

    if image_type == "product":
        # Clear old videos & exports when replacing product image
        v_dir = PROJECTS_DIR / project_id / "videos"
        if v_dir.exists():
            for vf in v_dir.glob("*.mp4"):
                try:
                    vf.unlink()
                except Exception:
                    pass
        await db.execute("DELETE FROM videos WHERE project_id = ?", (project_id,))
        await db.execute("DELETE FROM exports WHERE project_id = ?", (project_id,))

        char_dest = PROJECTS_DIR / project_id / "character" / "character_instant_preview.png"
        char_abs = ""
        try:
            from backend.app.services.character_composer import compose_studio_character_with_product
            await asyncio.to_thread(compose_studio_character_with_product, abs_path, str(char_dest))
            if char_dest.exists():
                char_abs = str(char_dest)
        except Exception:
            char_abs = ""

        asset_id = str(uuid.uuid4())[:8]
        await db.execute("""
            INSERT INTO assets (id, project_id, asset_type, file_path, file_name, file_size, is_primary)
            VALUES (?, ?, 'original_product', ?, ?, ?, 1)
        """, (asset_id, project_id, abs_path, dest_path.name, file_size))

        await db.execute("DELETE FROM assets WHERE project_id = ? AND asset_type = 'ai_character'", (project_id,))
        if char_abs and os.path.exists(char_abs):
            char_asset_id = str(uuid.uuid4())[:8]
            char_size = os.path.getsize(char_abs)
            await db.execute("""
                INSERT INTO assets (id, project_id, asset_type, file_path, file_name, file_size, is_primary)
                VALUES (?, ?, 'ai_character', ?, 'character_instant_preview.png', ?, 1)
            """, (char_asset_id, project_id, char_abs, char_size))

        from backend.app.services.product_analyzer import analyze_product_image_hybrid, is_valid_recognized_product_name
        analyzed_data = {}
        try:
            a_res = await analyze_product_image_hybrid(abs_path, hint_name="", allow_gemini_vision=False)
            if a_res.get("data"):
                analyzed_data = a_res["data"]
        except Exception:
            pass
        rec_name = analyzed_data.get("product_name", "")
        if not is_valid_recognized_product_name(rec_name):
            rec_name = "⚠️ Cần nhập tên sản phẩm"

        await db.execute("""
            UPDATE projects SET
                name = ?,
                category = ?,
                benefits = ?,
                highlights = ?,
                original_image_path = ?,
                primary_character_image_path = ?,
                status = 'character_created',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            rec_name,
            analyzed_data.get("category") or "Thương mại & Bán lẻ",
            analyzed_data.get("benefits") or "",
            analyzed_data.get("highlights") or "",
            abs_path,
            char_abs,
            project_id
        ))
        await db.commit()

        task_id = str(uuid.uuid4())[:8]
        pipeline_runner.enqueue_batch([project_id], auto_run=True, force_regenerate=True, prioritize=True)
        return {
            "success": True,
            "image_path": abs_path,
            "character_image_path": char_abs,
            "task_id": task_id,
            "message": "Đã dán Ảnh Sản Phẩm và thêm vào hàng đợi tự động chạy tới khi ra video!"
        }
    else:
        asset_id = str(uuid.uuid4())[:8]
        await db.execute("DELETE FROM assets WHERE project_id = ? AND asset_type = 'ai_character'", (project_id,))
        await db.execute("""
            INSERT INTO assets (id, project_id, asset_type, file_path, file_name, file_size, is_primary)
            VALUES (?, ?, 'ai_character', ?, ?, ?, 1)
        """, (asset_id, project_id, abs_path, dest_path.name, file_size))

        await db.execute("""
            UPDATE projects SET primary_character_image_path = ?, status = 'character_created', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (abs_path, project_id))
        await db.commit()
        return {
            "success": True,
            "image_path": abs_path,
            "message": "Đã dán Ảnh Nhân Vật từ Clipboard thành công!"
        }


@router.post("/{project_id}/clone-video-variant")
async def clone_video_variant(
    project_id: str,
    auto_run: bool = True,
    db = Depends(get_db)
):
    """
    Creates a new product video variant (Nhân bản video sản phẩm):
    - Re-uses product image (product_original.jpg) and core product info.
    - Sets project title to '[Product Name] (Bản kho xưởng #N)'.
    - Generates new warehouse character image in warehouse setting.
    - Generates new warehouse pricing scripts (≥ 42 words, 10s: quay tại tổng kho xưởng, giá xuất xưởng rẻ tận gốc).
    - Clears all previous videos/exports so brand new distinct 2 scenes are generated.
    - If auto_run=True, enqueues to pipeline_runner.enqueue_batch and immediately starts production!
    """
    import re
    import logging
    _log = logging.getLogger(__name__)

    cur = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    orig_proj = await cur.fetchone()
    if not orig_proj:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án gốc để nhân bản.")
    
    orig_dict = dict(orig_proj)
    raw_name = orig_dict.get("name") or "Sản phẩm chính hãng"
    base_name = re.sub(r"\s*\(Bản kho xưởng\s*#?\d*\)", "", raw_name).strip()
    if not base_name:
        base_name = "Sản phẩm chính hãng"

    # Count existing variants of this product
    v_cur = await db.execute("SELECT COUNT(*) FROM projects WHERE name LIKE ?", (f"{base_name} (Bản kho xưởng%",))
    count_existing = (await v_cur.fetchone())[0]
    variant_num = count_existing + 1
    new_name = f"{base_name} (Bản kho xưởng #{variant_num})"

    new_project_id = str(uuid.uuid4())[:8]
    create_project_folders(new_project_id)

    # Copy original product image with resilient search across paths, assets, and base product variants
    orig_img = orig_dict.get("original_image_path")
    if not orig_img or not os.path.exists(orig_img):
        cands = list((PROJECTS_DIR / project_id / "product").glob("*"))
        if cands and os.path.exists(str(cands[0])):
            orig_img = str(cands[0])

    if not orig_img or not os.path.exists(orig_img):
        a_cur = await db.execute("SELECT file_path FROM assets WHERE project_id = ? AND asset_type = 'original_product'", (project_id,))
        a_row = await a_cur.fetchone()
        if a_row and a_row[0] and os.path.exists(a_row[0]):
            orig_img = a_row[0]

    if not orig_img or not os.path.exists(orig_img):
        # Look for product image in other projects with matching base product name
        sim_cur = await db.execute("SELECT id, original_image_path FROM projects WHERE name LIKE ? AND id != ? ORDER BY updated_at DESC", (f"%{base_name}%", project_id))
        for sim_row in await sim_cur.fetchall():
            sim_id = sim_row[0]
            sim_path = sim_row[1]
            if sim_path and os.path.exists(sim_path):
                orig_img = sim_path
                break
            sim_cands = list((PROJECTS_DIR / sim_id / "product").glob("*"))
            if sim_cands and os.path.exists(str(sim_cands[0])):
                orig_img = str(sim_cands[0])
                break

    new_prod_path = None
    if orig_img and os.path.exists(orig_img):
        ext = Path(orig_img).suffix or ".jpg"
        dest_prod = PROJECTS_DIR / new_project_id / "product" / f"product_original{ext}"
        shutil.copyfile(orig_img, str(dest_prod))
        new_prod_path = str(dest_prod)

    # Strictly forbid creating empty ghost projects without a product image
    if not new_prod_path or not os.path.exists(new_prod_path):
        shutil.rmtree(PROJECTS_DIR / new_project_id, ignore_errors=True)
        raise HTTPException(
            status_code=400,
            detail=f"Dự án '{raw_name}' không còn tệp ảnh sản phẩm trên máy tính (tệp đã bị xóa hoặc di chuyển). Vui lòng chọn dự án có ảnh hoặc tải/dán ảnh sản phẩm (Ctrl+V) trước khi nhân bản."
        )

    # Compose new warehouse presenter image
    char_dest = PROJECTS_DIR / new_project_id / "character" / "character_primary.png"
    new_char_path = None
    if new_prod_path and os.path.exists(new_prod_path):
        try:
            from backend.app.services.character_composer import compose_studio_character_with_product
            await asyncio.to_thread(compose_studio_character_with_product, new_prod_path, str(char_dest))
            if char_dest.exists():
                new_char_path = str(char_dest)
        except Exception as e_comp:
            _log.warning(f"Error composing character for clone: {e_comp}")

    # Build warehouse script (≥ 42 words, warehouse setting & factory-direct pricing)
    from backend.app.services.pipeline_runner import build_fallback_scripts
    wh_scripts = build_fallback_scripts(
        product_name=new_name,
        category=orig_dict.get("category") or "Thương mại & Bán lẻ",
        benefits=orig_dict.get("benefits") or "",
        highlights=orig_dict.get("highlights") or "",
        offer=orig_dict.get("offer") or "Tặng kèm ưu đãi trợ giá xuất xưởng và miễn phí giao hàng",
        price=orig_dict.get("price") or "Giá xuất xưởng siêu ưu đãi",
        is_warehouse_mode=True
    )

    p_cat = orig_dict.get("category") or "Thương mại & Bán lẻ"
    p_ben = orig_dict.get("benefits") or ""
    p_high = orig_dict.get("highlights") or ""
    p_price = orig_dict.get("price") or "Giá xuất xưởng siêu ưu đãi"
    p_offer = orig_dict.get("offer") or "Tặng kèm ưu đãi trợ giá xuất xưởng và miễn phí giao hàng"

    await db.execute("""
        INSERT INTO projects (
            id, name, category, description, benefits, highlights, price, offer,
            original_image_path, primary_character_image_path,
            status, automation_mode, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'character_created', 'auto', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """, (
        new_project_id, new_name, p_cat, orig_dict.get("description") or new_name,
        p_ben, p_high, p_price, p_offer, new_prod_path, new_char_path
    ))

    # Assets
    if new_prod_path and os.path.exists(new_prod_path):
        a1_id = str(uuid.uuid4())[:8]
        await db.execute("""
            INSERT INTO assets (id, project_id, asset_type, file_path, file_name, file_size, is_primary)
            VALUES (?, ?, 'original_product', ?, ?, ?, 1)
        """, (a1_id, new_project_id, new_prod_path, Path(new_prod_path).name, os.path.getsize(new_prod_path)))

    if new_char_path and os.path.exists(new_char_path):
        a2_id = str(uuid.uuid4())[:8]
        await db.execute("""
            INSERT INTO assets (id, project_id, asset_type, file_path, file_name, file_size, is_primary)
            VALUES (?, ?, 'ai_character', ?, ?, ?, 1)
        """, (a2_id, new_project_id, new_char_path, Path(new_char_path).name, os.path.getsize(new_char_path)))

    # Scripts
    chosen_s_id = None
    for s in wh_scripts:
        s_id = str(uuid.uuid4())[:8]
        if not chosen_s_id:
            chosen_s_id = s_id
        await db.execute("""
            INSERT INTO scripts (
                id, project_id, option_label, option_title, hook_concept,
                scene1_dialogue, scene1_word_count, scene1_prompt_veo,
                scene2_dialogue, scene2_word_count, scene2_prompt_veo,
                is_selected, raw_response
            ) VALUES (?, ?, 'A', ?, ?, ?, ?, ?, ?, ?, ?, 1, 'Warehouse variant script')
        """, (
            s_id, new_project_id, s["title"], s["hook"],
            s["scene1_dialogue"], s["scene1_words"], s["scene1_prompt_veo"],
            s["scene2_dialogue"], s["scene2_words"], s["scene2_prompt_veo"]
        ))

    if chosen_s_id:
        await db.execute("UPDATE projects SET selected_script_id = ? WHERE id = ?", (chosen_s_id, new_project_id))

    await db.commit()

    if auto_run:
        pipeline_runner.enqueue_batch([new_project_id], auto_run=True, force_regenerate=True, prioritize=True)

    return {
        "success": True,
        "project_id": new_project_id,
        "name": new_name,
        "message": f"Đã nhân bản video '{new_name}' (Bối cảnh tổng kho xưởng, giá rẻ tận gốc) thành công!"
    }





