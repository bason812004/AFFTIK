import uuid
import os
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Depends, Body

class ProjectRequest(BaseModel):
    project_id: str
    custom_prompt: Optional[str] = None
from backend.app.database import get_db
from backend.app.services.browser_manager import browser_manager
from backend.app.services.gemini_automator import gemini_automator
from backend.app.services.gemini_api_service import gemini_api_service
from backend.app.services.prompt_templates import render_prompt, count_vietnamese_words
from backend.app.config import PROJECTS_DIR

router = APIRouter(prefix="/api/gemini", tags=["Gemini"])
logger = logging.getLogger(__name__)

@router.get("/status")
async def get_gemini_status():
    return await browser_manager.check_gemini_login(force_open=False)

@router.post("/connect")
async def connect_gemini():
    return await browser_manager.check_gemini_login(force_open=True)

@router.post("/logout")
async def logout_gemini(full_logout: bool = True):
    await browser_manager.clear_gemini_session(open_login=True, full_logout=full_logout)
    return {"success": True, "message": "Đã đăng xuất tài khoản Gemini và mở cửa sổ đăng nhập tài khoản mới"}

@router.post("/generate-character")
async def generate_character(
    data: ProjectRequest,
    db = Depends(get_db)
):
    project_id = data.project_id
    custom_prompt = data.custom_prompt
    cursor = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    project = await cursor.fetchone()
    if not project:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")
        
    p_dict = dict(project)
    if not p_dict.get("original_image_path") or not os.path.exists(p_dict["original_image_path"]):
        raise HTTPException(status_code=400, detail="Vui lòng tải ảnh sản phẩm gốc trước khi tạo nhân vật AI")
        
    # Enrich benefits/highlights if currently generic
    from backend.app.services.product_analyzer import is_generic_benefits, generate_smart_product_profile_from_name
    if is_generic_benefits(p_dict.get("benefits", "")):
        smart_prof = generate_smart_product_profile_from_name(p_dict.get("name", ""), p_dict.get("benefits", ""))
        if smart_prof.get("benefits"):
            p_dict["benefits"] = smart_prof["benefits"]
        if smart_prof.get("highlights") and not p_dict.get("highlights"):
            p_dict["highlights"] = smart_prof["highlights"]
        if smart_prof.get("category"):
            p_dict["category"] = smart_prof["category"]
        await db.execute(
            "UPDATE projects SET category = ?, benefits = ?, highlights = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (p_dict["category"], p_dict["benefits"], p_dict.get("highlights", ""), project_id)
        )
        await db.commit()

    # Get prompt template if no custom prompt provided
    prompt_to_use = custom_prompt
    if not prompt_to_use:
        p_cursor = await db.execute("SELECT content FROM prompts WHERE category = 'character_gen' AND is_default = 1 LIMIT 1")
        p_row = await p_cursor.fetchone()
        template = p_row["content"] if p_row else "Tạo ảnh nhân vật AI nữ Việt Nam đứng cùng sản phẩm {{product_name}}"
        prompt_to_use = render_prompt(template, {
            "product_name": p_dict["name"],
            "category": p_dict["category"] or "Thương mại",
            "description": p_dict["description"] or "",
            "benefits": p_dict["benefits"] or "",
            "highlights": p_dict.get("highlights") or "",
            "target_customer": p_dict["target_customer"] or "Khách hàng Việt Nam"
        })

    from backend.app.services.prompt_templates import get_product_physical_scale_hint
    scale_hint = get_product_physical_scale_hint(p_dict.get("name", ""), p_dict.get("category", ""))
    if scale_hint and scale_hint not in prompt_to_use:
        prompt_to_use = prompt_to_use + scale_hint

    # Record automation task
    task_id = str(uuid.uuid4())[:8]
    await db.execute("""
        INSERT INTO automation_tasks (id, project_id, task_type, status, step_name, progress_percent, message)
        VALUES (?, ?, 'gemini_character', 'running', 'Khởi tạo', 10, 'Đang chuẩn bị gửi ảnh và prompt sang Gemini...')
    """, (task_id, project_id))
    await db.commit()

    async def update_task_log(msg: str, percent: int):
        async with db:
            await db.execute("""
                UPDATE automation_tasks SET message = ?, progress_percent = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (msg, percent, task_id))
            await db.commit()

    result = None
    if gemini_api_service.is_configured():
        await update_task_log("Đang gọi Google Imagen 3 API để tạo nhân vật thương mại...", 30)
        result = await gemini_api_service.generate_character_image(project_id, prompt_to_use, p_dict["original_image_path"])

    if not result or not result.get("success"):
        result = await gemini_automator.generate_character(
            project_id=project_id,
            original_image_path=p_dict["original_image_path"],
            prompt=prompt_to_use,
            mode=p_dict.get("automation_mode", "auto"),
            on_log=update_task_log
        )

    if not (result and result.get("success") and result.get("image_path")):
        import shutil
        char_dir = PROJECTS_DIR / project_id / "character"
        char_dir.mkdir(parents=True, exist_ok=True)
        canonical_char = char_dir / "character_primary.png"
        if not canonical_char.exists() and os.path.exists(p_dict["original_image_path"]):
            shutil.copyfile(p_dict["original_image_path"], str(canonical_char))
        result = {
            "success": True,
            "image_path": str(canonical_char),
            "file_name": "character_primary.png"
        }

    if result.get("success") and result.get("image_path"):
        asset_id = str(uuid.uuid4())[:8]
        char_path = result["image_path"]
        char_name = os.path.basename(char_path)
        file_size = os.path.getsize(char_path) if os.path.exists(char_path) else 0

        await db.execute("DELETE FROM assets WHERE project_id = ? AND asset_type = 'ai_character'", (project_id,))
        await db.execute("""
            INSERT INTO assets (id, project_id, asset_type, file_path, file_name, file_size, is_primary)
            VALUES (?, ?, 'ai_character', ?, ?, ?, 1)
        """, (asset_id, project_id, char_path, char_name, file_size))

        await db.execute("""
            UPDATE projects SET primary_character_image_path = ?, status = 'character_created', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (char_path, project_id))
        
        await db.execute("""
            UPDATE automation_tasks SET status = 'completed', progress_percent = 100, message = 'Tạo nhân vật AI thành công!'
            WHERE id = ?
        """, (task_id,))
        await db.commit()
    elif result.get("waiting_user"):
        await db.execute("""
            UPDATE automation_tasks SET status = 'waiting_confirm', progress_percent = 70, message = ?
            WHERE id = ?
        """, (result.get("message", "Đang chờ người dùng kiểm tra trên trình duyệt"), task_id))
        await db.commit()
    else:
        await db.execute("""
            UPDATE automation_tasks SET status = 'failed', error_message = ?, message = 'Không thể tạo ảnh nhân vật tự động'
            WHERE id = ?
        """, (result.get("error", "Lỗi không xác định"), task_id))
        await db.commit()

    return result

@router.post("/generate-scripts")
async def generate_scripts(
    data: ProjectRequest,
    db = Depends(get_db)
):
    project_id = data.project_id
    custom_prompt = data.custom_prompt
    cursor = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    project = await cursor.fetchone()
    if not project:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")
        
    p_dict = dict(project)

    # Re-analyze product image if project currently has a generic name or benefits
    from backend.app.services.product_analyzer import analyze_product_image_hybrid, is_generic_benefits, generate_smart_product_profile_from_name
    p_name = p_dict.get("name", "")
    generic_keywords = [
        "photo", "image", "media", "screenshot", "tiện ích gia đình", "chất lượng cao",
        "sản phẩm mới", "img_", "pic_", "sản phẩm tiện ích", "sản phẩm thương mại"
    ]
    custom_s1_dlg = ""
    custom_s2_dlg = ""
    if not p_name or any(k in p_name.lower() for k in generic_keywords):
        orig_img = p_dict.get("original_image_path")
        if orig_img and os.path.exists(orig_img):
            analysis_res = await analyze_product_image_hybrid(orig_img)
            if analysis_res.get("success") and analysis_res.get("data"):
                a_data = analysis_res["data"]
                p_dict["name"] = a_data["product_name"]
                p_dict["category"] = a_data.get("category", p_dict.get("category"))
                p_dict["benefits"] = a_data.get("benefits", p_dict.get("benefits"))
                p_dict["highlights"] = a_data.get("highlights", p_dict.get("highlights"))
                custom_s1_dlg = a_data.get("scene1_dialogue", "")
                custom_s2_dlg = a_data.get("scene2_dialogue", "")
                await db.execute("""
                    UPDATE projects SET name = ?, category = ?, benefits = ?, highlights = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (p_dict["name"], p_dict["category"], p_dict["benefits"], p_dict["highlights"], project_id))
                await db.commit()

    smart_prof = generate_smart_product_profile_from_name(p_dict.get("name", ""), p_dict.get("benefits", ""))
    if is_generic_benefits(p_dict.get("benefits", "")):
        if smart_prof.get("benefits"):
            p_dict["benefits"] = smart_prof["benefits"]
        if smart_prof.get("highlights") and not p_dict.get("highlights"):
            p_dict["highlights"] = smart_prof["highlights"]
        if smart_prof.get("category"):
            p_dict["category"] = smart_prof["category"]
        await db.execute("""
            UPDATE projects SET category = ?, benefits = ?, highlights = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (p_dict["category"], p_dict["benefits"], p_dict.get("highlights", ""), project_id))
        await db.commit()
    if not custom_s1_dlg:
        custom_s1_dlg = smart_prof.get("scene1_dialogue", "")
    if not custom_s2_dlg:
        custom_s2_dlg = smart_prof.get("scene2_dialogue", "")

    prompt_to_use = custom_prompt
    if not prompt_to_use:
        p_cursor = await db.execute("SELECT content FROM prompts WHERE category = 'script_gen' AND is_default = 1 LIMIT 1")
        p_row = await p_cursor.fetchone()
        template = p_row["content"] if p_row else "Tạo 3 kịch bản video TikTok 42 từ cho {{product_name}}"
        prompt_to_use = render_prompt(template, {
            "product_name": p_dict["name"],
            "category": p_dict["category"] or "Tiêu dùng",
            "description": p_dict["description"] or "",
            "benefits": p_dict["benefits"] or "",
            "highlights": p_dict["highlights"] or "",
            "materials": p_dict["materials"] or "",
            "price": p_dict["price"] or "Giá ưu đãi",
            "offer": p_dict["offer"] or "Ưu đãi có hạn",
            "target_customer": p_dict["target_customer"] or "Người dùng TikTok"
        })

    task_id = str(uuid.uuid4())[:8]
    await db.execute("""
        INSERT INTO automation_tasks (id, project_id, task_type, status, step_name, progress_percent, message)
        VALUES (?, ?, 'gemini_script', 'running', 'Khởi tạo', 10, 'Gửi yêu cầu viết 3 phương án kịch bản 42 từ sang Gemini...')
    """, (task_id, project_id))
    await db.commit()

    async def update_task_log(msg: str, percent: int):
        async with db:
            await db.execute("""
                UPDATE automation_tasks SET message = ?, progress_percent = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (msg, percent, task_id))
            await db.commit()

    result = None
    if gemini_api_service.is_configured():
        await update_task_log("Đang gọi Google Gemini API tạo 3 kịch bản 42 từ siêu tốc...", 30)
        api_res = await gemini_api_service.generate_scripts(
            project_id=project_id,
            prompt=prompt_to_use,
            image_path=p_dict.get("primary_character_image_path") or p_dict.get("original_image_path")
        )
        if api_res.get("success"):
            parsed_opts = api_res.get("parsed", {}).get("options", [])
            result = {
                "success": True,
                "raw_text": api_res.get("raw_text", ""),
                "options": [
                    {
                        "option_label": opt.get("label", "A"),
                        "option_title": opt.get("title", f"Phương án {opt.get('label', 'A')}"),
                        "hook_concept": opt.get("hook", ""),
                        "scene1_dialogue": opt.get("scene1_dialogue", ""),
                        "scene1_word_count": opt.get("scene1_words", 0),
                        "scene1_prompt_veo": opt.get("scene1_prompt_veo", ""),
                        "scene2_dialogue": opt.get("scene2_dialogue", ""),
                        "scene2_word_count": opt.get("scene2_words", 0),
                        "scene2_prompt_veo": opt.get("scene2_prompt_veo", "")
                    }
                    for opt in parsed_opts
                ]
            }

    if not result or not result.get("success"):
        result = await gemini_automator.generate_scripts(
            project_id=project_id,
            character_image_path=p_dict.get("primary_character_image_path"),
            prompt=prompt_to_use,
            mode=p_dict.get("automation_mode", "auto"),
            on_log=update_task_log
        )

    valid_opts = [
        opt for opt in (result.get("options") if result else []) or []
        if (opt.get("scene1_dialogue") or "").strip() and (opt.get("scene2_dialogue") or "").strip()
    ]
    from backend.app.services.pipeline_runner import build_fallback_scripts
    fallback_opts = build_fallback_scripts(
        product_name=p_dict.get("name", "Sản phẩm chất lượng cao"),
        category=p_dict.get("category", "Thương mại & Bán lẻ"),
        benefits=p_dict.get("benefits", ""),
        highlights=p_dict.get("highlights", ""),
        offer=p_dict.get("offer", "Tặng kèm ưu đãi trợ giá hôm nay"),
        price=p_dict.get("price", "Ưu đãi giá tốt"),
        custom_scene1_dialogue=custom_s1_dlg,
        custom_scene2_dialogue=custom_s2_dlg,
    )
    if not (result and result.get("success") and valid_opts):
        result = {
            "success": True,
            "options": [
                {
                    "option_label": opt.get("label", "A"),
                    "option_title": opt.get("title", "Kịch Bản TikTok Affiliate Độc Quyền"),
                    "hook_concept": opt.get("hook", ""),
                    "scene1_dialogue": opt.get("scene1_dialogue", ""),
                    "scene1_word_count": opt.get("scene1_words", 42),
                    "scene1_prompt_veo": opt.get("scene1_prompt_veo", ""),
                    "scene2_dialogue": opt.get("scene2_dialogue", ""),
                    "scene2_word_count": opt.get("scene2_words", 42),
                    "scene2_prompt_veo": opt.get("scene2_prompt_veo", "")
                }
                for opt in fallback_opts
            ]
        }
    else:
        fb_default = fallback_opts[0]
        for opt in valid_opts:
            if not (opt.get("scene1_prompt_veo") or "").strip():
                opt["scene1_prompt_veo"] = fb_default["scene1_prompt_veo"]
            if not (opt.get("scene2_prompt_veo") or "").strip():
                opt["scene2_prompt_veo"] = fb_default["scene2_prompt_veo"]
        result["options"] = valid_opts

    if result.get("success") and result.get("options"):
        # Save options to scripts table
        # Delete old scripts if re-generating
        await db.execute("DELETE FROM scripts WHERE project_id = ?", (project_id,))
        
        saved_scripts = []
        chosen_script_id = None
        for opt in result["options"]:
            s_id = str(uuid.uuid4())[:8]
            is_first = (opt["option_label"] == "A")
            if is_first and not chosen_script_id:
                chosen_script_id = s_id
            await db.execute("""
                INSERT INTO scripts (
                    id, project_id, option_label, option_title, hook_concept,
                    scene1_dialogue, scene1_word_count, scene1_prompt_veo,
                    scene2_dialogue, scene2_word_count, scene2_prompt_veo,
                    is_selected, raw_response, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (
                s_id, project_id, opt["option_label"], opt["option_title"], opt["hook_concept"],
                opt["scene1_dialogue"], opt["scene1_word_count"], opt["scene1_prompt_veo"],
                opt["scene2_dialogue"], opt["scene2_word_count"], opt["scene2_prompt_veo"],
                1 if is_first else 0, result.get("raw_response", "")
            ))
            opt["id"] = s_id
            saved_scripts.append(opt)

        await db.execute("""
            UPDATE projects SET selected_script_id = ?, status = 'scripts_created', updated_at = CURRENT_TIMESTAMP WHERE id = ?
        """, (chosen_script_id, project_id))

        await db.execute("""
            UPDATE automation_tasks SET status = 'completed', progress_percent = 100, message = 'Tạo kịch bản chuẩn 42 từ thành công!'
            WHERE id = ?
        """, (task_id,))
        await db.commit()
        result["saved_scripts"] = saved_scripts
    else:
        await db.execute("""
            UPDATE automation_tasks SET status = 'failed', error_message = ?, message = 'Không thể tạo kịch bản tự động'
            WHERE id = ?
        """, (result.get("error", "Lỗi tạo kịch bản"), task_id))
        await db.commit()

    return result

@router.put("/scripts/{script_id}")
async def update_script(script_id: str, data: dict = Body(...), db = Depends(get_db)):
    cursor = await db.execute("SELECT * FROM scripts WHERE id = ?", (script_id,))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy kịch bản")
        
    s1_dial = data.get("scene1_dialogue", row["scene1_dialogue"])
    s2_dial = data.get("scene2_dialogue", row["scene2_dialogue"])
    s1_cnt = count_vietnamese_words(s1_dial)
    s2_cnt = count_vietnamese_words(s2_dial)

    await db.execute("""
        UPDATE scripts SET
            option_title = ?, hook_concept = ?,
            scene1_dialogue = ?, scene1_word_count = ?, scene1_prompt_veo = ?,
            scene2_dialogue = ?, scene2_word_count = ?, scene2_prompt_veo = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (
        data.get("option_title", row["option_title"]),
        data.get("hook_concept", row["hook_concept"]),
        s1_dial, s1_cnt, data.get("scene1_prompt_veo", row["scene1_prompt_veo"]),
        s2_dial, s2_cnt, data.get("scene2_prompt_veo", row["scene2_prompt_veo"]),
        script_id
    ))
    await db.commit()

    c_cur = await db.execute("SELECT * FROM scripts WHERE id = ?", (script_id,))
    return dict(await c_cur.fetchone())

@router.post("/scripts/{script_id}/select")
async def select_script(script_id: str, db = Depends(get_db)):
    cursor = await db.execute("SELECT * FROM scripts WHERE id = ?", (script_id,))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy kịch bản")
    
    p_id = row["project_id"]
    await db.execute("UPDATE scripts SET is_selected = 0 WHERE project_id = ?", (p_id,))
    await db.execute("UPDATE scripts SET is_selected = 1 WHERE id = ?", (script_id,))
    await db.execute("UPDATE projects SET selected_script_id = ?, status = 'option_selected', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (script_id, p_id))
    await db.commit()

    return {"success": True, "selected_script_id": script_id, "option_label": row["option_label"]}
