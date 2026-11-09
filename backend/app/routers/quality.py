from fastapi import APIRouter, Body
from backend.app.models import QualityCheckRequest
from backend.app.services.quality_checker import check_script_quality
from backend.app.services.prompt_templates import count_vietnamese_words

router = APIRouter(prefix="/api/quality", tags=["Quality"])

@router.post("/check")
async def check_quality(req: QualityCheckRequest):
    return check_script_quality(
        scene1_dialogue=req.scene1_dialogue,
        scene2_dialogue=req.scene2_dialogue,
        scene1_prompt=req.scene1_prompt or "",
        scene2_prompt=req.scene2_prompt or "",
        product_name=req.product_name or ""
    )

@router.post("/count-words")
async def count_words(text: str = Body(..., embed=True)):
    count = count_vietnamese_words(text)
    return {
        "count": count,
        "is_exact_42": count >= 42,
        "difference": max(0, 42 - count),
        "status": "exact" if 42 <= count <= 60 else ("under" if count < 42 else "over")
    }

