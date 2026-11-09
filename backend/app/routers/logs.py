from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from backend.app.database import get_db

router = APIRouter(prefix="/api/logs", tags=["Logs"])

@router.get("")
async def list_tasks(project_id: Optional[str] = None, limit: int = 50, db = Depends(get_db)):
    if project_id:
        cursor = await db.execute("""
            SELECT * FROM automation_tasks WHERE project_id = ? ORDER BY created_at DESC LIMIT ?
        """, (project_id, limit))
    else:
        cursor = await db.execute("""
            SELECT * FROM automation_tasks ORDER BY created_at DESC LIMIT ?
        """, (limit,))
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]

@router.get("/{task_id}")
async def get_task(task_id: str, db = Depends(get_db)):
    cursor = await db.execute("SELECT * FROM automation_tasks WHERE id = ?", (task_id,))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy tác vụ")
    return dict(row)

