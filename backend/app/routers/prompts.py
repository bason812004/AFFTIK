import uuid
import json
from fastapi import APIRouter, HTTPException, Depends, Body
from typing import Optional
from backend.app.database import get_db, seed_default_prompts
from backend.app.models import PromptCreate, PromptUpdate, RenderPromptRequest
from backend.app.services.prompt_templates import render_prompt, DEFAULT_SYSTEM_PROMPTS

router = APIRouter(prefix="/api/prompts", tags=["Prompts"])

@router.get("")
async def list_prompts(category: Optional[str] = None, db = Depends(get_db)):
    if category:
        cursor = await db.execute("SELECT * FROM prompts WHERE category = ? ORDER BY is_system DESC, updated_at DESC", (category,))
    else:
        cursor = await db.execute("SELECT * FROM prompts ORDER BY category, is_system DESC, updated_at DESC")
    rows = await cursor.fetchall()
    prompts = []
    for r in rows:
        p = dict(r)
        p["variables"] = json.loads(p["variables_json"]) if p.get("variables_json") else []
        prompts.append(p)
    return prompts

@router.post("")
async def create_prompt(data: PromptCreate, db = Depends(get_db)):
    p_id = str(uuid.uuid4())[:8]
    vars_json = json.dumps(data.variables or [])
    await db.execute("""
        INSERT INTO prompts (id, project_id, category, title, content, variables_json, is_default, is_system)
        VALUES (?, ?, ?, ?, ?, ?, 0, 0)
    """, (p_id, data.project_id, data.category, data.title, data.content, vars_json))
    await db.commit()

    cursor = await db.execute("SELECT * FROM prompts WHERE id = ?", (p_id,))
    p = dict(await cursor.fetchone())
    p["variables"] = data.variables or []
    return p

@router.put("/{prompt_id}")
async def update_prompt(prompt_id: str, data: PromptUpdate, db = Depends(get_db)):
    cursor = await db.execute("SELECT * FROM prompts WHERE id = ?", (prompt_id,))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy mẫu prompt")

    title = data.title if data.title is not None else row["title"]
    content = data.content if data.content is not None else row["content"]
    vars_json = json.dumps(data.variables) if data.variables is not None else row["variables_json"]

    await db.execute("""
        UPDATE prompts SET title = ?, content = ?, variables_json = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (title, content, vars_json, prompt_id))
    await db.commit()

    cursor = await db.execute("SELECT * FROM prompts WHERE id = ?", (prompt_id,))
    p = dict(await cursor.fetchone())
    p["variables"] = json.loads(p["variables_json"]) if p.get("variables_json") else []
    return p

@router.delete("/{prompt_id}")
async def delete_prompt(prompt_id: str, db = Depends(get_db)):
    cursor = await db.execute("SELECT * FROM prompts WHERE id = ?", (prompt_id,))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy prompt")
    if row["is_system"]:
        raise HTTPException(status_code=400, detail="Không thể xóa mẫu prompt mặc định của hệ thống")

    await db.execute("DELETE FROM prompts WHERE id = ?", (prompt_id,))
    await db.commit()
    return {"success": True, "message": "Đã xóa prompt"}

@router.post("/{prompt_id}/duplicate")
async def duplicate_prompt(prompt_id: str, db = Depends(get_db)):
    cursor = await db.execute("SELECT * FROM prompts WHERE id = ?", (prompt_id,))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy prompt")

    new_id = str(uuid.uuid4())[:8]
    new_title = f"{row['title']} (Bản sao)"
    await db.execute("""
        INSERT INTO prompts (id, project_id, category, title, content, variables_json, is_default, is_system)
        VALUES (?, ?, ?, ?, ?, ?, 0, 0)
    """, (new_id, row["project_id"], row["category"], new_title, row["content"], row["variables_json"]))
    await db.commit()

    cursor = await db.execute("SELECT * FROM prompts WHERE id = ?", (new_id,))
    p = dict(await cursor.fetchone())
    p["variables"] = json.loads(p["variables_json"]) if p.get("variables_json") else []
    return p

@router.post("/reset-defaults")
async def reset_default_prompts(db = Depends(get_db)):
    await db.execute("DELETE FROM prompts WHERE is_system = 1")
    await db.commit()
    await seed_default_prompts()
    return {"success": True, "message": "Đã khôi phục các mẫu prompt gốc thành công"}

@router.post("/render")
async def render_prompt_template(req: RenderPromptRequest, db = Depends(get_db)):
    p_cursor = await db.execute("SELECT * FROM projects WHERE id = ?", (req.project_id,))
    project = await p_cursor.fetchone()
    if not project:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")

    p_dict = dict(project)

    template_content = req.custom_content
    if not template_content and req.prompt_id:
        pr_cursor = await db.execute("SELECT content FROM prompts WHERE id = ?", (req.prompt_id,))
        pr_row = await pr_cursor.fetchone()
        if pr_row:
            template_content = pr_row["content"]

    if not template_content:
        raise HTTPException(status_code=400, detail="Không có nội dung mẫu prompt")

    # Interpolate
    rendered = render_prompt(template_content, {
        "product_name": p_dict.get("name", ""),
        "category": p_dict.get("category", ""),
        "description": p_dict.get("description", ""),
        "benefits": p_dict.get("benefits", ""),
        "highlights": p_dict.get("highlights", ""),
        "materials": p_dict.get("materials", ""),
        "target_customer": p_dict.get("target_customer", ""),
        "price": p_dict.get("price", ""),
        "offer": p_dict.get("offer", ""),
        "warranty": p_dict.get("warranty", ""),
        "character_description": "Nhân vật nữ Việt Nam trẻ trung, thân thiện"
    })

    return {"rendered": rendered}

